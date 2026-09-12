"""Report generation pipeline — async worker job that aggregates analysis
data, renders it in the requested format, and stores the result
(08-feature-spec-collaboration.md §7, 09-api-spec.md §8).

Reports are deterministic aggregations (no LLM calls), so generation is
fast and cheap; the async job exists because rendering large portfolios
and writing to object storage shouldn't block the API request.
"""
from __future__ import annotations

import json
import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.models import Report
from app.pipelines.reports.aggregation import (
    build_obligation_calendar_data,
    build_portfolio_risk_data,
)
from app.services.storage_service import get_storage

logger = logging.getLogger(__name__)

RUNNABLE_STATUSES = {"pending"}

REPORT_EXPORT_FORMATS = {
    "json": "application/json",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


async def run_report_pipeline(report_id: str) -> None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Report).where(Report.id == UUID(report_id)))
        report = result.scalar_one_or_none()
        if report is None:
            logger.error("report_pipeline.not_found", extra={"report_id": report_id})
            return
        if report.status not in RUNNABLE_STATUSES:
            logger.info(
                "report_pipeline.skipped_not_pending",
                extra={"report_id": report_id, "status": report.status},
            )
            return

        report.status = "processing"
        await session.commit()

        try:
            document_ids = (
                [UUID(doc_id) for doc_id in report.document_ids]
                if report.document_ids
                else None
            )
            if report.report_type == "portfolio_risk":
                data = await build_portfolio_risk_data(
                    session,
                    organization_id=report.organization_id,
                    document_ids=document_ids,
                )
            else:
                data = await build_obligation_calendar_data(
                    session,
                    organization_id=report.organization_id,
                    document_ids=document_ids,
                )

            content = _render(report.report_type, report.export_format, data)
            storage = get_storage()
            key = (
                f"org/{report.organization_id}/reports/{report.id}.{report.export_format}"
            )
            await storage.put_bytes(
                key, content, REPORT_EXPORT_FORMATS[report.export_format]
            )

            report.data = data
            report.storage_path = key
            report.status = "completed"
            await session.commit()
            logger.info(
                "report_pipeline.completed",
                extra={
                    "report_id": report_id,
                    "report_type": report.report_type,
                    "format": report.export_format,
                },
            )
        except Exception as exc:
            logger.exception("report_pipeline.failed", extra={"report_id": report_id})
            report.status = "error"
            report.error = f"Report generation failed: {exc}"
            await session.commit()


def _render(report_type: str, export_format: str, data: dict) -> bytes:
    # Imported lazily: export_service pulls in document_service, which imports
    # the worker pool — importing it at module scope creates a circular import
    # when the worker process starts from app.workers.jobs.
    from app.services.export_service import render_docx, render_pdf, render_xlsx

    if export_format == "json":
        return json.dumps(data, indent=2).encode("utf-8")
    if export_format == "xlsx":
        sheets = (
            _risk_sheets(data) if report_type == "portfolio_risk" else _calendar_sheets(data)
        )
        return render_xlsx(sheets)
    outline = _outline(data)
    return render_pdf(outline) if export_format == "pdf" else render_docx(outline)


# ── PDF/DOCX outline (reuses the export renderer contract) ────────────────────


def _outline(data: dict) -> list[tuple[str, str]]:
    lines: list[tuple[str, str]] = [
        ("h1", "Portfolio Risk Report" if data["report_type"] == "portfolio_risk"
         else "Obligation Calendar Report"),
        ("p", f"Generated: {data['generated_at']}"),
        ("p", f"Documents in scope: {data['scope']['document_count']}"),
    ]
    if data["report_type"] == "portfolio_risk":
        lines += _risk_outline(data)
    else:
        lines += _calendar_outline(data)
    lines += [("h3", "Disclaimer"), ("p", data["disclaimer"])]
    return lines


def _risk_outline(data: dict) -> list[tuple[str, str]]:
    summary = data["summary"]
    avg_score = summary["average_contract_score"]
    lines: list[tuple[str, str]] = [
        ("h2", "Summary"),
        ("p", f"Documents analyzed: {summary['documents_analyzed']}"),
        ("p", f"Total risks: {summary['total_risks']}"),
        ("p", f"Critical risks: {summary['critical_risk_count']} "
              f"across {summary['documents_with_critical_risks']} documents"),
        ("p", f"Average contract score: "
              f"{avg_score if avg_score is not None else 'n/a'}"),
        ("h2", "Risks by Severity"),
    ]
    for sev, count in data["risks_by_severity"].items():
        lines.append(("p", f"{sev.title()}: {count}"))
    if data["risks_by_type"]:
        lines.append(("h2", "Risks by Type"))
        for rtype, count in data["risks_by_type"].items():
            lines.append(("p", f"{rtype}: {count}"))
    lines.append(("h2", "Documents"))
    for doc in data["documents"]:
        score = f"{doc['contract_score']}" if doc["contract_score"] is not None else "n/a"
        lines.append(
            ("p", f"{doc['filename']} — score {score}, {doc['risk_count']} risk(s)")
        )
    return lines


def _calendar_outline(data: dict) -> list[tuple[str, str]]:
    summary = data["summary"]
    lines: list[tuple[str, str]] = [
        ("h2", "Summary"),
        ("p", f"Total obligations: {summary['total_obligations']}"),
        ("p", f"Overdue: {summary['overdue']}  Due soon: {summary['due_soon']}  "
              f"Upcoming: {summary['upcoming']}"),
    ]
    for section in ("overdue", "due_soon", "upcoming"):
        entries = data[section]
        if not entries:
            continue
        lines.append(("h2", section.replace("_", " ").title()))
        for entry in entries:
            deadline = entry["deadline_date"] or "no deadline"
            lines.append(
                ("p", f"{deadline} — {entry['filename']}: {entry['description']} "
                      f"(party: {entry['obligated_party']})")
            )
    return lines


# ── XLSX sheets ────────────────────────────────────────────────────────────────


def _risk_sheets(data: dict) -> list[tuple[str, list[list[str]]]]:
    summary = data["summary"]
    return [
        (
            "Summary",
            [
                ["Metric", "Value"],
                ["Documents analyzed", str(summary["documents_analyzed"])],
                ["Total risks", str(summary["total_risks"])],
                ["Critical risks", str(summary["critical_risk_count"])],
                ["Documents with critical risks", str(summary["documents_with_critical_risks"])],
                ["Average contract score", str(summary["average_contract_score"] or "n/a")],
            ],
        ),
        (
            "Risks by Severity",
            [["Severity", "Count"]]
            + [[sev, str(count)] for sev, count in data["risks_by_severity"].items()],
        ),
        (
            "Risks by Type",
            [["Type", "Count"]]
            + [[rtype, str(count)] for rtype, count in data["risks_by_type"].items()],
        ),
        (
            "Score Distribution",
            [["Score range", "Documents"]]
            + [[rng, str(count)] for rng, count in data["score_distribution"].items()],
        ),
        (
            "Documents",
            [["Filename", "Type", "Contract score", "Risk count", "Critical risks"]]
            + [
                [
                    doc["filename"],
                    doc["document_type"],
                    str(doc["contract_score"]) if doc["contract_score"] is not None else "",
                    str(doc["risk_count"]),
                    "; ".join(
                        f"{r['risk_type']} (p.{r['page_number']})"
                        for r in doc["critical_risks"]
                    ),
                ]
                for doc in data["documents"]
            ],
        ),
    ]


def _calendar_sheets(data: dict) -> list[tuple[str, list[list[str]]]]:
    header = ["Deadline", "Status", "Document", "Obligated party", "Description", "Page"]
    sheets = [
        (
            "Summary",
            [
                ["Metric", "Value"],
                ["Documents analyzed", str(data["summary"]["documents_analyzed"])],
                ["Total obligations", str(data["summary"]["total_obligations"])],
                ["Overdue", str(data["summary"]["overdue"])],
                ["Due soon", str(data["summary"]["due_soon"])],
                ["Upcoming", str(data["summary"]["upcoming"])],
                ["No deadline", str(data["summary"]["no_deadline"])],
                ["Completed", str(data["summary"]["completed"])],
            ],
        ),
    ]
    for section in ("overdue", "due_soon", "upcoming", "no_deadline"):
        rows = [header] + [
            [
                entry["deadline_date"] or "",
                entry["status"],
                entry["filename"],
                entry["obligated_party"],
                entry["description"],
                str(entry["page_number"]),
            ]
            for entry in data[section]
        ]
        sheets.append((section.replace("_", " ").title()[:31], rows))
    return sheets
