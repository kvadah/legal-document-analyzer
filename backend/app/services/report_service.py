"""Report service — API-facing create/get/list/download for portfolio reports."""
from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser
from app.models.models import Document, DocumentStatus, Report
from app.repositories.report_repo import ReportRepository
from app.schemas.report import (
    ReportCreateRequest,
    ReportCreatedResponse,
    ReportListResponse,
    ReportOut,
)
from app.services.storage_service import get_storage
from app.workers.pool import enqueue_report


async def create_report(
    session: AsyncSession,
    *,
    current_user: CurrentUser,
    request: ReportCreateRequest,
) -> ReportCreatedResponse:
    """Validate scope and queue the report job (async, 202)."""
    org_id = UUID(current_user.org_id)

    if request.document_ids:
        from sqlalchemy import select

        result = await session.execute(
            select(Document).where(
                Document.id.in_(request.document_ids),
                Document.organization_id == org_id,
            )
        )
        documents = {doc.id: doc for doc in result.scalars().all()}
        for doc_id in request.document_ids:
            doc = documents.get(doc_id)
            if doc is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "code": "not_found",
                        "message": f"Document {doc_id} not found",
                    },
                )
            if doc.status != DocumentStatus.ANALYSIS_READY:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "code": "analysis_not_ready",
                        "message": (
                            f"Reports aggregate analysis output. '{doc.filename}' "
                            f"has status: {doc.status}."
                        ),
                    },
                )

    repo = ReportRepository(session, org_id)
    report = await repo.save(
        Report(
            id=uuid4(),
            organization_id=org_id,
            generated_by=UUID(current_user.id),
            report_type=request.report_type,
            status="pending",
            document_ids=[str(d) for d in request.document_ids] if request.document_ids else None,
            export_format=request.export_format,
        )
    )
    await session.commit()
    await enqueue_report(str(report.id))
    return ReportCreatedResponse(report_id=str(report.id), status="pending")


async def get_report(
    session: AsyncSession,
    *,
    current_user: CurrentUser,
    report_id: UUID,
) -> ReportOut:
    repo = ReportRepository(session, UUID(current_user.org_id))
    report = await repo.get_by_id(report_id)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": f"Report {report_id} not found"},
        )
    return _to_out(report)


async def list_reports(
    session: AsyncSession,
    *,
    current_user: CurrentUser,
    limit: int = 50,
    offset: int = 0,
) -> ReportListResponse:
    repo = ReportRepository(session, UUID(current_user.org_id))
    reports = await repo.list_reports(limit=limit, offset=offset)
    total = await repo.count()
    return ReportListResponse(
        reports=[_to_out(r) for r in reports],
        total=total,
    )


async def download_report(
    session: AsyncSession,
    *,
    current_user: CurrentUser,
    report_id: UUID,
) -> StreamingResponse:
    """Stream the generated report file (org-scoped, completed reports only)."""
    import io

    repo = ReportRepository(session, UUID(current_user.org_id))
    report = await repo.get_by_id(report_id)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": f"Report {report_id} not found"},
        )
    if report.status != "completed" or not report.storage_path:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "report_not_ready",
                "message": f"Report is {report.status}; only completed reports can be downloaded.",
            },
        )

    storage = get_storage()
    content = await storage.get_bytes(report.storage_path)
    type_by_format = {
        "json": "application/json",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    filename = f"{report.report_type}-{report.id}.{report.export_format}"
    return StreamingResponse(
        io.BytesIO(content),
        media_type=type_by_format[report.export_format],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _to_out(report: Report) -> ReportOut:
    return ReportOut(
        report_id=str(report.id),
        report_type=report.report_type,
        status=report.status,
        export_format=report.export_format,
        document_ids=report.document_ids,
        created_at=report.created_at,
        completed_at=report.updated_at if report.status == "completed" else None,
        error=report.error,
        generated_by=str(report.generated_by) if report.generated_by else None,
    )
