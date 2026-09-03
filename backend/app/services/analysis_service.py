"""Analysis service — org-scoped reads of AI pipeline outputs."""
from __future__ import annotations

import json
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser
from app.models.models import ClauseType, DocumentStatus, RiskStatus
from app.pipelines.ai.scoring import SCORES_VERSION, SEVERITY_WEIGHTS
from app.repositories.analysis_repo import AnalysisRepository
from app.schemas.analysis import (
    ClauseListResponse,
    ClauseOut,
    EntityGroup,
    EntityListResponse,
    EntityOut,
    ObligationListResponse,
    ObligationOut,
    PartyOut,
    RiskDeduction,
    RiskListResponse,
    RiskOut,
    ScoreOut,
    SummaryOut,
)
from app.services import document_service


async def _verify_document(
    session: AsyncSession, current_user: CurrentUser, document_id: UUID
) -> None:
    await document_service.get_document(session, current_user=current_user, document_id=document_id)


async def _require_analysis(
    session: AsyncSession, current_user: CurrentUser, document_id: UUID
) -> None:
    doc = await document_service.get_document(
        session, current_user=current_user, document_id=document_id
    )
    if doc.status != DocumentStatus.ANALYSIS_READY:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "analysis_not_ready",
                "message": f"Document analysis is not ready (status: {doc.status}).",
            },
        )


async def get_summary(
    session: AsyncSession, current_user: CurrentUser, document_id: UUID
) -> SummaryOut:
    await _require_analysis(session, current_user, document_id)
    repo = AnalysisRepository(session, UUID(current_user.org_id))
    summary = await repo.get_summary(document_id)
    if summary is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Summary not found."},
        )
    parties: list[PartyOut] = []
    if summary.parties:
        try:
            parties = [PartyOut(**p) for p in json.loads(summary.parties)]
        except (json.JSONDecodeError, TypeError):
            parties = []
    return SummaryOut(
        document_id=str(document_id),
        parties=parties,
        purpose=summary.purpose,
        duration=summary.duration,
        termination_conditions=summary.termination_conditions,
        key_risks=summary.key_risks,
        financial_terms=summary.financial_terms,
        governing_law=summary.governing_law,
        effective_date=summary.effective_date,
        expiration_date=summary.expiration_date,
        contract_value=(
            float(summary.contract_value) if summary.contract_value is not None else None
        ),
        contract_currency=summary.contract_currency,
    )


async def list_clauses(
    session: AsyncSession, current_user: CurrentUser, document_id: UUID
) -> ClauseListResponse:
    await _require_analysis(session, current_user, document_id)
    repo = AnalysisRepository(session, UUID(current_user.org_id))
    clauses = await repo.list_clauses(document_id)
    found_types = {clause.clause_type for clause in clauses}
    not_found = [
        clause_type.value
        for clause_type in ClauseType
        if clause_type not in found_types
    ]
    return ClauseListResponse(
        items=[
            ClauseOut(
                id=str(clause.id),
                clause_type=clause.clause_type.value,
                extracted_text=clause.extracted_text,
                summary=clause.summary,
                page_number=clause.page_number,
                paragraph_index=clause.paragraph_index,
                confidence_score=(
                    float(clause.confidence_score)
                    if clause.confidence_score is not None
                    else None
                ),
                source_chunk_ids=(
                    [str(cid) for cid in clause.source_chunk_ids]
                    if clause.source_chunk_ids
                    else None
                ),
                created_at=clause.created_at,
            )
            for clause in clauses
        ],
        not_found=not_found,
        total=len(clauses),
    )


async def list_risks(
    session: AsyncSession, current_user: CurrentUser, document_id: UUID
) -> RiskListResponse:
    await _require_analysis(session, current_user, document_id)
    repo = AnalysisRepository(session, UUID(current_user.org_id))
    risks = await repo.list_risks(document_id)
    return RiskListResponse(
        items=[
            RiskOut(
                id=str(risk.id),
                risk_type=risk.risk_type.value,
                severity=risk.severity.value,
                description=risk.description,
                recommendation=risk.recommendation,
                page_number=risk.page_number,
                confidence_score=(
                    float(risk.confidence_score)
                    if risk.confidence_score is not None
                    else None
                ),
                status=risk.status.value,
                clause_id=str(risk.clause_id) if risk.clause_id else None,
                created_at=risk.created_at,
            )
            for risk in risks
        ],
        total=len(risks),
    )


async def update_risk_status(
    session: AsyncSession,
    current_user: CurrentUser,
    document_id: UUID,
    risk_id: UUID,
    new_status: RiskStatus,
) -> RiskOut:
    await _verify_document(session, current_user, document_id)
    repo = AnalysisRepository(session, UUID(current_user.org_id))
    risk = await repo.get_risk(document_id, risk_id)
    if risk is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Risk not found."},
        )
    updated = await repo.update_risk_status(risk, new_status)
    await session.commit()
    return RiskOut(
        id=str(updated.id),
        risk_type=updated.risk_type.value,
        severity=updated.severity.value,
        description=updated.description,
        recommendation=updated.recommendation,
        page_number=updated.page_number,
        confidence_score=(
            float(updated.confidence_score)
            if updated.confidence_score is not None
            else None
        ),
        status=updated.status.value,
        clause_id=str(updated.clause_id) if updated.clause_id else None,
        created_at=updated.created_at,
    )


async def list_entities(
    session: AsyncSession, current_user: CurrentUser, document_id: UUID
) -> EntityListResponse:
    await _require_analysis(session, current_user, document_id)
    repo = AnalysisRepository(session, UUID(current_user.org_id))
    entities = await repo.list_entities(document_id)
    by_type: dict[str, list[EntityOut]] = {}
    for entity in entities:
        out = EntityOut(
            id=str(entity.id),
            entity_type=entity.entity_type.value,
            value=entity.value,
            raw_text=entity.raw_text,
            page_number=entity.page_number,
            confidence_score=(
                float(entity.confidence_score)
                if entity.confidence_score is not None
                else None
            ),
            created_at=entity.created_at,
        )
        by_type.setdefault(entity.entity_type.value, []).append(out)
    groups = [
        EntityGroup(entity_type=entity_type, items=items) for entity_type, items in by_type.items()
    ]
    return EntityListResponse(groups=groups, total=len(entities))


async def list_obligations(
    session: AsyncSession, current_user: CurrentUser, document_id: UUID
) -> ObligationListResponse:
    await _require_analysis(session, current_user, document_id)
    repo = AnalysisRepository(session, UUID(current_user.org_id))
    obligations = await repo.list_obligations(document_id)
    return ObligationListResponse(
        items=[
            ObligationOut(
                id=str(obligation.id),
                obligated_party=obligation.obligated_party,
                description=obligation.description,
                deadline_date=obligation.deadline_date,
                deadline_type=obligation.deadline_type.value,
                status=obligation.status.value,
                page_number=obligation.page_number,
                created_at=obligation.created_at,
            )
            for obligation in obligations
        ],
        total=len(obligations),
    )


async def get_score(
    session: AsyncSession, current_user: CurrentUser, document_id: UUID
) -> ScoreOut:
    await _require_analysis(session, current_user, document_id)
    doc = await document_service.get_document(
        session, current_user=current_user, document_id=document_id
    )
    repo = AnalysisRepository(session, UUID(current_user.org_id))
    risks = await repo.list_risks(document_id)
    breakdown = [
        RiskDeduction(
            risk_id=str(risk.id),
            risk_type=risk.risk_type.value,
            severity=risk.severity.value,
            deduction=SEVERITY_WEIGHTS[risk.severity],
        )
        for risk in risks
    ]
    return ScoreOut(
        document_id=str(document_id),
        contract_score=(
            float(doc.contract_score) if doc.contract_score is not None else None
        ),
        ai_confidence_score=(
            float(doc.ai_confidence_score)
            if doc.ai_confidence_score is not None
            else None
        ),
        scores_version=SCORES_VERSION,
        breakdown=breakdown,
        total_deduction=sum(item.deduction for item in breakdown),
    )
