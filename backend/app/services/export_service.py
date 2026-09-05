"""Single-document analysis export (09-api-spec.md §8).

Formats: PDF, DOCX, JSON. PDF and DOCX are rendered with the standard library
only (a minimal but valid PDF writer and a minimal OOXML word-processing
package) so exports carry no extra dependencies; every export includes the
persistent AI disclaimer per 11-security-compliance.md §8.
"""
from __future__ import annotations

import io
import re
import zipfile
from datetime import date, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser
from app.models.models import DocumentStatus
from app.schemas.analysis import (
    ClauseListResponse,
    EntityListResponse,
    ObligationListResponse,
    RiskListResponse,
    ScoreOut,
    SummaryOut,
)
from app.services import analysis_service

DISCLAIMER = "AI-generated analysis — not legal advice."

EXPORT_FORMATS = {"pdf": "application/pdf", "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "json": "application/json"}


async def _build_payload(
    session: AsyncSession, *, current_user: CurrentUser, document_id: UUID
) -> dict[str, Any]:
    """Assemble the full analysis payload (org-scoped reads)."""
    from app.services.document_service import get_document

    doc = await get_document(session, current_user=current_user, document_id=document_id)
    if doc.status != DocumentStatus.ANALYSIS_READY:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "document_not_ready",
                "message": f"Analysis is not ready yet (status: {doc.status}).",
            },
        )
    summary: SummaryOut = await analysis_service.get_summary(
        session, current_user, document_id
    )
    clauses: ClauseListResponse = await analysis_service.list_clauses(
        session, current_user, document_id
    )
    risks: RiskListResponse = await analysis_service.list_risks(
        session, current_user, document_id
    )
    entities: EntityListResponse = await analysis_service.list_entities(
        session, current_user, document_id
    )
    obligations: ObligationListResponse = await analysis_service.list_obligations(
        session, current_user, document_id
    )
    score: ScoreOut = await analysis_service.get_score(session, current_user, document_id)

    return {
        "document": {
            "id": doc.id,
            "filename": doc.filename,
            "document_type": doc.document_type,
            "page_count": doc.page_count,
            "uploaded_at": doc.created_at.isoformat(),
            "analysis_generated_at": doc.updated_at.isoformat(),
        },
        "summary": summary.model_dump(mode="json"),
        "clauses": clauses.model_dump(mode="json"),
        "risks": risks.model_dump(mode="json"),
        "obligations": obligations.model_dump(mode="json"),
        "entities": entities.model_dump(mode="json"),
        "score": score.model_dump(mode="json"),
        "disclaimer": DISCLAIMER,
    }


# ── Plain-text outline (shared by PDF & DOCX renderers) ──────────────────────


def _fmt(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, (datetime, date)):
        return value.strftime("%b %d, %Y")
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def _outline(payload: dict[str, Any]) -> list[tuple[str, str]]:
    """Render the payload as a (heading|paragraph, text) outline."""
    doc = payload["document"]
    score = payload["score"]
    summary = payload["summary"]

    lines: list[tuple[str, str]] = [
        ("h1", f"Analysis Report — {doc['filename']}"),
        ("p", f"Document type: {doc['document_type'].replace('_', ' ').title()}"),
        ("p", f"Pages: {_fmt(doc['page_count'])} · Uploaded: {doc['uploaded_at'][:10]}"),
        ("p", (
            f"Contract score: {_fmt(score['contract_score'])}/100 · "
            f"AI confidence: {round((score['ai_confidence_score'] or 0) * 100)}% "
            f"(scores v{score['scores_version']})"
        )),
        ("h2", "Summary"),
    ]
    parties = ", ".join(p["name"] + (f" ({p['role']})" if p.get("role") else "")
                        for p in summary["parties"]) or "—"
    lines.append(("p", f"Parties: {parties}"))
    for label, key in (
        ("Purpose", "purpose"),
        ("Duration", "duration"),
        ("Effective date", "effective_date"),
        ("Expiration date", "expiration_date"),
        ("Contract value", "contract_value"),
        ("Financial terms", "financial_terms"),
        ("Governing law", "governing_law"),
        ("Termination conditions", "termination_conditions"),
        ("Key risks", "key_risks"),
    ):
        lines.append(("p", f"{label}: {_fmt(summary.get(key))}"))

    lines.append(("h2", "Risks"))
    if payload["risks"]["items"]:
        for risk in payload["risks"]["items"]:
            lines.append(("h3", f"{risk['risk_type'].replace('_', ' ').title()} — {risk['severity'].title()} ({risk['status']})"))
            lines.append(("p", risk["description"]))
            if risk.get("recommendation"):
                lines.append(("p", f"Recommendation: {risk['recommendation']}"))
            if risk.get("page_number"):
                lines.append(("p", f"Source: page {risk['page_number']}"))
    else:
        lines.append(("p", "No risks were flagged."))

    lines.append(("h2", "Clauses"))
    if payload["clauses"]["items"]:
        for clause in payload["clauses"]["items"]:
            lines.append(("h3", f"{clause['clause_type'].replace('_', ' ').title()} (page {clause['page_number']})"))
            if clause.get("summary"):
                lines.append(("p", clause["summary"]))
            lines.append(("p", clause["extracted_text"]))
    else:
        lines.append(("p", "No clauses were detected."))
    if payload["clauses"]["not_found"]:
        lines.append(("p", "Not found: " + ", ".join(t.replace('_', ' ') for t in payload["clauses"]["not_found"])))

    lines.append(("h2", "Obligations"))
    if payload["obligations"]["items"]:
        for obligation in payload["obligations"]["items"]:
            deadline = f" · due {obligation['deadline_date'][:10]}" if obligation.get("deadline_date") else ""
            lines.append(("h3", f"{obligation['obligated_party']}{deadline}"))
            lines.append(("p", obligation["description"]))
    else:
        lines.append(("p", "No obligations were extracted."))

    lines.append(("h2", "Entities"))
    if payload["entities"]["groups"]:
        for group in payload["entities"]["groups"]:
            values = ", ".join(item["value"] for item in group["items"])
            lines.append(("p", f"{group['entity_type'].replace('_', ' ').title()}: {values}"))
    else:
        lines.append(("p", "No entities were extracted."))

    lines.append(("h2", "Disclaimer"))
    lines.append(("p", DISCLAIMER))
    return lines


# ── PDF renderer (stdlib) ─────────────────────────────────────────────────────


def _pdf_escape(text: str) -> str:
    out = []
    for char in text:
        if char in "()\\":
            out.append("\\" + char)
        elif ord(char) < 32 or ord(char) > 255:
            out.append("?")
        else:
            out.append(char)
    return "".join(out)


def _wrap(text: str, width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def render_pdf(outline: list[tuple[str, str]]) -> bytes:
    """Minimal single-font-family PDF: Helvetica body, Helvetica-Bold headings."""
    page_w, page_h = 595, 842  # A4 points
    margin_left, margin_top, margin_bottom = 56, 64, 56
    line_height = 14
    max_width = 80

    styles = {
        "h1": {"font": "F2", "size": 16, "leading": 22, "gap_before": 0, "gap_after": 8},
        "h2": {"font": "F2", "size": 12.5, "leading": 18, "gap_before": 14, "gap_after": 5},
        "h3": {"font": "F2", "size": 10.5, "leading": 15, "gap_before": 8, "gap_after": 3},
        "p": {"font": "F1", "size": 9.5, "leading": line_height, "gap_before": 0, "gap_after": 2},
    }

    pages: list[list[str]] = []
    current: list[str] = []
    y = page_h - margin_top

    def new_page() -> None:
        nonlocal current, y
        pages.append(current)
        current = []
        y = page_h - margin_top

    for kind, text in outline:
        style = styles[kind]
        wrapped = _wrap(text, max_width)
        block_height = style["gap_before"] + len(wrapped) * style["leading"] + style["gap_after"]
        if y - block_height < margin_bottom and current:
            new_page()
        y -= style["gap_before"]
        for line in wrapped:
            if y - style["leading"] < margin_bottom:
                new_page()
            y -= style["leading"]
            current.append(
                f"BT /{style['font']} {style['size']} Tf {margin_left} {y:.1f} Td ({_pdf_escape(line)}) Tj ET"
            )
        y -= style["gap_after"]
    if current:
        pages.append(current)

    objects: list[bytes] = []
    # 1: catalog, 2: pages tree, 3: Helvetica, 4: Helvetica-Bold
    pages_kids = " ".join(f"{5 + 2 * i} 0 R" for i in range(len(pages)))
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [{pages_kids}] /Count {len(pages)} >>".encode())
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")
    for i, content in enumerate(pages):
        page_number = 5 + 2 * i
        content_number = page_number + 1
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_w} {page_h}] "
            f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {content_number} 0 R >>".encode()
        )
        stream = "\n".join(content).encode("latin-1", errors="replace")
        objects.append(f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream")

    buffer = io.BytesIO()
    buffer.write(b"%PDF-1.4\n")
    offsets = [0]
    for number, obj in enumerate(objects, start=1):
        offsets.append(buffer.tell())
        buffer.write(f"{number} 0 obj\n".encode())
        buffer.write(obj)
        buffer.write(b"\nendobj\n")
    xref_at = buffer.tell()
    buffer.write(f"xref\n0 {len(objects) + 1}\n".encode())
    buffer.write(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        buffer.write(f"{offset:010d} 00000 n \n".encode())
    buffer.write(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n".encode()
    )
    return buffer.getvalue()


# ── DOCX renderer (stdlib zipfile + OOXML) ────────────────────────────────────


def _xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def render_docx(outline: list[tuple[str, str]]) -> bytes:
    """Minimal valid .docx: document.xml + styles.xml in a zip package."""
    styles = {
        "h1": "Heading1",
        "h2": "Heading2",
        "h3": "Heading3",
        "p": "BodyText",
    }
    paragraphs = []
    for kind, text in outline:
        style = styles[kind]
        paragraphs.append(
            f'<w:p><w:pPr><w:pStyle w:val="{style}"/></w:pPr>'
            f'<w:r><w:t xml:space="preserve">{_xml_escape(text)}</w:t></w:r></w:p>'
        )
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body>"
        + "".join(paragraphs)
        + "</w:body></w:document>"
    )
    styles_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:style w:type="paragraph" w:styleId="Heading1">'
        '<w:name w:val="heading 1"/><w:pPr><w:outlineLvl w:val="0"/></w:pPr>'
        '<w:rPr><w:b/><w:sz w:val="36"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Heading2">'
        '<w:name w:val="heading 2"/><w:pPr><w:outlineLvl w:val="1"/></w:pPr>'
        '<w:rPr><w:b/><w:sz w:val="28"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Heading3">'
        '<w:name w:val="heading 3"/><w:pPr><w:outlineLvl w:val="2"/></w:pPr>'
        '<w:rPr><w:b/><w:sz w:val="23"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="BodyText">'
        '<w:name w:val="Body Text"/><w:rPr><w:sz w:val="21"/></w:rPr></w:style>'
        "</w:styles>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
        "</Types>"
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        "</Relationships>"
    )
    document_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        "</Relationships>"
    )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", root_rels)
        archive.writestr("word/document.xml", document_xml)
        archive.writestr("word/_rels/document.xml.rels", document_rels)
        archive.writestr("word/styles.xml", styles_xml)
    return buffer.getvalue()


# ── Public API ────────────────────────────────────────────────────────────────


async def export_document(
    session: AsyncSession,
    *,
    current_user: CurrentUser,
    document_id: UUID,
    export_format: str,
) -> StreamingResponse:
    if export_format not in EXPORT_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "validation_error",
                "message": f"Unsupported format {export_format!r}. Allowed: pdf, docx, json",
            },
        )

    payload = await _build_payload(session, current_user=current_user, document_id=document_id)
    stem = re.sub(r"[^\w.-]", "_", payload["document"]["filename"].rsplit(".", 1)[0])

    if export_format == "json":
        import json

        content = json.dumps(payload, indent=2).encode("utf-8")
    else:
        outline = _outline(payload)
        content = render_pdf(outline) if export_format == "pdf" else render_docx(outline)

    media_type = EXPORT_FORMATS[export_format]
    return StreamingResponse(
        io.BytesIO(content),
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{stem}-analysis.{export_format}"'
        },
    )
