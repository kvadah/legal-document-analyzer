"""AI pipeline orchestrator (Phase 3, spec 05-ai-pipeline.md).

Stage order: metadata (full pass) → clause detection → entity extraction →
obligation extraction → risk detection (rules then LLM judgment) → summary →
scores → store. Status transitions: ingestion_ready → ai_pipeline_processing
→ analysis_ready (or error).

LLM call budget: clause detection and risk judgment are each ONE batched
call covering all types (10 clause types in one, the LLM-judgment risk
checks in one), keeping a document at ~6 calls total. The original
one-call-per-type design was better isolated per decision, but free-tier
LLM quotas (e.g. Gemini: 20 requests/day/model) make 15+ calls per document
unworkable — batching is the documented tradeoff (05-ai-pipeline.md §4);
revisit against the golden eval set when it exists.

Anti-hallucination: every extraction is validated against the cited chunk —
verbatim spans that do not appear in the referenced chunk text are dropped
and logged, never persisted.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.llm import get_llm_provider
from app.llm.base import LLMProvider
from app.llm.prompts import (
    ENTITY_PROMPT,
    METADATA_PROMPT,
    OBLIGATION_PROMPT,
    PROMPT_VERSION,
    RISK_JUDGMENT_PROMPTS,
    SEVERITY_RUBRIC,
    SUMMARY_PROMPT,
    all_clauses_prompt,
    risk_judgments_prompt,
)
from app.models.models import (
    Chunk,
    Clause,
    ClauseType,
    DeadlineType,
    Document,
    DocumentStatus,
    DocumentSummary,
    DocumentType,
    Entity,
    EntityType,
    Obligation,
    Risk,
    RiskSeverity,
    RiskStatus,
    RiskType,
)
from app.pipelines.ai.clause_types import CLAUSE_TYPE_DESCRIPTIONS
from app.pipelines.ai.extraction import (
    AllClausesResult,
    EntityListResult,
    MetadataExtraction,
    ObligationListResult,
    RiskJudgmentListResult,
    RiskJudgmentResult,
    SummaryExtraction,
)
from app.pipelines.ai.risk_rules import run_rule_checks
from app.pipelines.ai.scoring import (
    SCORES_VERSION,
    compute_ai_confidence,
    compute_contract_score,
)
from app.pipelines.status import transition_document_status
from app.repositories.analysis_repo import AnalysisRepository
from app.repositories.chunk_repo import ChunkRepository
from app.services.relationship_service import infer_relationship_suggestions

logger = logging.getLogger(__name__)

_LLM_JUDGMENT_TYPES = (
    RiskType.UNLIMITED_LIABILITY,
    RiskType.AMBIGUOUS_LANGUAGE,
    RiskType.HIGH_PENALTY,
)

_MAX_ENTITY_CONTEXT_CHUNKS = 30
_PREAMBLE_TAIL_CHUNKS = 3


async def run_ai_pipeline(document_id: str) -> None:
    async with AsyncSessionLocal() as session:
        doc = await _load_document(session, UUID(document_id))
        if doc is None:
            logger.error("ai_pipeline.document_not_found", extra={"document_id": document_id})
            return
        if doc.status != DocumentStatus.INGESTION_READY:
            logger.info(
                "ai_pipeline.skipped_not_ready",
                extra={"document_id": document_id, "status": doc.status.value},
            )
            return
        try:
            await _run_stages(session, doc)
        except Exception as exc:
            logger.exception("ai_pipeline.failed", extra={"document_id": document_id})
            await transition_document_status(
                session,
                organization_id=doc.organization_id,
                document_id=doc.id,
                status=DocumentStatus.ERROR,
                status_detail=f"AI pipeline: {exc}",
            )


async def _load_document(session: AsyncSession, document_id: UUID) -> Document | None:
    stmt = select(Document).where(Document.id == document_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _run_stages(session: AsyncSession, doc: Document) -> None:
    org_id = doc.organization_id
    doc_id = doc.id

    await transition_document_status(
        session,
        organization_id=org_id,
        document_id=doc_id,
        status=DocumentStatus.AI_PIPELINE_PROCESSING,
    )

    chunks = await ChunkRepository(session).list_for_document(doc_id)
    provider = get_llm_provider()

    metadata = await _extract_metadata(provider, chunks)
    clauses = await _detect_clauses(provider, chunks)
    entities = await _extract_entities(provider, chunks)
    obligations = await _extract_obligations(provider, chunks)
    risks = await _detect_risks(provider, chunks, clauses, doc.document_type, metadata)
    summary = await _generate_summary(provider, metadata, clauses, risks, entities)

    low_quality_ocr = "low quality" in (doc.status_detail or "").lower()
    contract_score, _breakdown = compute_contract_score(risks)
    llm_risks = [r for r in risks if r.confidence_score is not None]
    ai_confidence = compute_ai_confidence(
        clauses, llm_risks, entities, low_quality_ocr=low_quality_ocr
    )

    await _store(
        session,
        doc,
        clauses=clauses,
        risks=risks,
        entities=entities,
        obligations=obligations,
        metadata=metadata,
        summary=summary,
        contract_score=contract_score,
        ai_confidence=ai_confidence,
    )

    await transition_document_status(
        session,
        organization_id=org_id,
        document_id=doc_id,
        status=DocumentStatus.ANALYSIS_READY,
    )

    await infer_relationship_suggestions(session, doc)


def _format_chunk(chunk: Chunk) -> str:
    return f"[{chunk.id} | page {chunk.page_number}]\n{chunk.text}"


def _chunk_map(chunks: list[Chunk]) -> dict[str, Chunk]:
    return {str(chunk.id): chunk for chunk in chunks}


async def _extract_metadata(
    provider: LLMProvider, chunks: list[Chunk]
) -> MetadataExtraction:
    selected = chunks[:_PREAMBLE_TAIL_CHUNKS] + chunks[-_PREAMBLE_TAIL_CHUNKS:]
    if not selected:
        selected = chunks
    result = await provider.generate_structured(
        METADATA_PROMPT,
        MetadataExtraction,
        [_format_chunk(c) for c in selected],
        "fast",
        prompt_version=PROMPT_VERSION,
    )
    return result.typed(MetadataExtraction)


async def _detect_clauses(provider: LLMProvider, chunks: list[Chunk]) -> list[Clause]:
    by_id = _chunk_map(chunks)
    entries = [(t.value, CLAUSE_TYPE_DESCRIPTIONS[t]) for t in ClauseType]
    result = await provider.generate_structured(
        all_clauses_prompt(entries),
        AllClausesResult,
        [_format_chunk(c) for c in chunks],
        "capable",
        prompt_version=PROMPT_VERSION,
    )
    clauses: list[Clause] = []
    for instance in result.typed(AllClausesResult).clauses:
        chunk = by_id.get(instance.chunk_id)
        if chunk is None or instance.extracted_text not in (chunk.text or ""):
            logger.warning(
                "ai_pipeline.clause_grounding_failed",
                extra={
                    "clause_type": instance.clause_type,
                    "chunk_id": instance.chunk_id,
                },
            )
            continue
        clauses.append(
            Clause(
                id=uuid.uuid4(),
                document_id=chunk.document_id,
                clause_type=ClauseType(instance.clause_type),
                extracted_text=instance.extracted_text,
                summary=instance.summary,
                page_number=chunk.page_number,
                paragraph_index=chunk.paragraph_index,
                confidence_score=round(instance.confidence, 2),
                source_chunk_ids=[chunk.id],
            )
        )
    return clauses


async def _extract_entities(provider: LLMProvider, chunks: list[Chunk]) -> list[Entity]:
    by_id = _chunk_map(chunks)
    result = await provider.generate_structured(
        ENTITY_PROMPT,
        EntityListResult,
        [_format_chunk(c) for c in chunks[:_MAX_ENTITY_CONTEXT_CHUNKS]],
        "fast",
        prompt_version=PROMPT_VERSION,
    )
    entities: list[Entity] = []
    for item in result.typed(EntityListResult).entities:
        chunk = by_id.get(item.chunk_id)
        if chunk is None or item.raw_text not in (chunk.text or ""):
            logger.warning(
                "ai_pipeline.entity_grounding_failed",
                extra={"entity_type": item.entity_type, "chunk_id": item.chunk_id},
            )
            continue
        entities.append(
            Entity(
                id=uuid.uuid4(),
                document_id=chunk.document_id,
                entity_type=EntityType(item.entity_type),
                value=item.value[:512],
                raw_text=item.raw_text,
                page_number=chunk.page_number,
                confidence_score=round(item.confidence, 2),
            )
        )
    return entities


async def _extract_obligations(
    provider: LLMProvider, chunks: list[Chunk]
) -> list[Obligation]:
    by_id = _chunk_map(chunks)
    result = await provider.generate_structured(
        OBLIGATION_PROMPT,
        ObligationListResult,
        [_format_chunk(c) for c in chunks[:_MAX_ENTITY_CONTEXT_CHUNKS]],
        "fast",
        prompt_version=PROMPT_VERSION,
    )
    obligations: list[Obligation] = []
    for item in result.typed(ObligationListResult).obligations:
        chunk = by_id.get(item.chunk_id)
        if chunk is None or item.description not in (chunk.text or ""):
            logger.warning(
                "ai_pipeline.obligation_grounding_failed",
                extra={"chunk_id": item.chunk_id},
            )
            continue
        obligations.append(
            Obligation(
                id=uuid.uuid4(),
                document_id=chunk.document_id,
                obligated_party=item.obligated_party[:255],
                description=item.description,
                deadline_date=_parse_date(item.deadline_date),
                deadline_type=DeadlineType(item.deadline_type),
                page_number=chunk.page_number,
            )
        )
    return obligations


def _judgment_context(
    clauses: list[Clause], chunks: list[Chunk], metadata: MetadataExtraction
) -> list[str]:
    """Combined context for the batched risk-judgment call.

    Union of the material any individual check would have reviewed: liability
    + payment/termination clause texts, the contract value, and the document
    opening (where vague-effort language lives).
    """
    related_types = (ClauseType.LIABILITY, ClauseType.PAYMENT, ClauseType.TERMINATION)
    context: list[str] = [c.extracted_text for c in clauses if c.clause_type in related_types]
    if metadata.contract_value is not None:
        currency = metadata.contract_currency or ""
        context.append(f"Contract value: {metadata.contract_value} {currency}")
    context.extend(chunk.text for chunk in chunks[:5])
    seen: set[str] = set()
    deduped: list[str] = []
    for item in context:
        if item and item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped


async def _detect_risks(
    provider: LLMProvider,
    chunks: list[Chunk],
    clauses: list[Clause],
    document_type: DocumentType,
    metadata: MetadataExtraction,
) -> list[Risk]:
    risks: list[Risk] = []
    doc_id = chunks[0].document_id if chunks else None
    if doc_id is None:
        return risks

    rule_risks = run_rule_checks(clauses, document_type, metadata.governing_law)
    for rule in rule_risks:
        if rule.risk_type == RiskType.AUTO_RENEWAL:
            confirmed = await _confirm_auto_renewal(provider, clauses)
            if not confirmed:
                continue
        risks.append(
            Risk(
                id=uuid.uuid4(),
                document_id=doc_id,
                clause_id=_clause_id_for_rule(rule.risk_type, clauses),
                risk_type=rule.risk_type,
                severity=rule.severity,
                description=rule.description,
                recommendation=rule.recommendation,
                confidence_score=None,
                status=RiskStatus.FLAGGED,
            )
        )

    checks = [(rt.value, RISK_JUDGMENT_PROMPTS[rt.value]) for rt in _LLM_JUDGMENT_TYPES]
    context = _judgment_context(clauses, chunks, metadata)
    result = await provider.generate_structured(
        risk_judgments_prompt(checks) + SEVERITY_RUBRIC,
        RiskJudgmentListResult,
        context,
        "capable",
        prompt_version=PROMPT_VERSION,
    )
    for judgment in result.typed(RiskJudgmentListResult).judgments:
        if not judgment.flagged or not judgment.description:
            continue
        risks.append(
            Risk(
                id=uuid.uuid4(),
                document_id=doc_id,
                clause_id=_clause_id_for_rule(RiskType(judgment.risk_type), clauses),
                risk_type=RiskType(judgment.risk_type),
                severity=RiskSeverity(judgment.severity),
                description=judgment.description,
                recommendation=judgment.recommendation,
                confidence_score=round(judgment.confidence, 2),
                status=RiskStatus.FLAGGED,
            )
        )
    return risks


async def _confirm_auto_renewal(
    provider: LLMProvider, clauses: list[Clause]
) -> bool:
    renewal_texts = [c.extracted_text for c in clauses if c.clause_type == ClauseType.RENEWAL]
    if not renewal_texts:
        return False
    result = await provider.generate_structured(
        "Confirm whether the renewal clause provides for automatic renewal "
        "without an explicit opt-out right.",
        RiskJudgmentResult,
        renewal_texts,
        "capable",
        prompt_version=PROMPT_VERSION,
    )
    return result.typed(RiskJudgmentResult).flagged


def _clause_id_for_rule(risk_type: RiskType, clauses: list[Clause]) -> UUID | None:
    related_by_type: dict[RiskType, ClauseType | None] = {
        RiskType.UNLIMITED_LIABILITY: ClauseType.LIABILITY,
        RiskType.MISSING_TERMINATION: None,
        RiskType.MISSING_NDA: None,
        RiskType.AMBIGUOUS_LANGUAGE: None,
        RiskType.NO_GOVERNING_LAW: ClauseType.JURISDICTION,
        RiskType.AUTO_RENEWAL: ClauseType.RENEWAL,
        RiskType.HIGH_PENALTY: ClauseType.PAYMENT,
    }
    clause_type = related_by_type.get(risk_type)
    if clause_type is None:
        return None
    for clause in clauses:
        if clause.clause_type == clause_type:
            return clause.id
    return None


async def _generate_summary(
    provider: LLMProvider,
    metadata: MetadataExtraction,
    clauses: list[Clause],
    risks: list[Risk],
    entities: list[Entity],
) -> SummaryExtraction:
    context: list[str] = []
    party_names = ", ".join(p.name for p in metadata.parties) or "unknown"
    meta_line = (
        f"[metadata] parties={party_names}; governing_law={metadata.governing_law}; "
        f"effective_date={metadata.effective_date}; "
        f"contract_value={metadata.contract_value}"
    )
    context.append(meta_line)
    for clause in clauses:
        context.append(f"[clause:{clause.clause_type.value}] {clause.summary}")
    for risk in risks:
        context.append(f"[risk:{risk.risk_type.value}|{risk.severity.value}] {risk.description}")
    money_values = [e.value for e in entities if e.entity_type == EntityType.MONEY]
    if money_values:
        context.append(f"[financial] amounts referenced: {', '.join(money_values[:10])}")
    result = await provider.generate_structured(
        SUMMARY_PROMPT,
        SummaryExtraction,
        context,
        "capable",
        prompt_version=PROMPT_VERSION,
    )
    return result.typed(SummaryExtraction)


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(value.strip(), fmt)
        except ValueError:
            continue
    return None


def _parse_model_date(value: str | None) -> date | None:
    parsed = _parse_date(value)
    return parsed.date() if parsed else None


async def _store(
    session: AsyncSession,
    doc: Document,
    *,
    clauses: list[Clause],
    risks: list[Risk],
    entities: list[Entity],
    obligations: list[Obligation],
    metadata: MetadataExtraction,
    summary: SummaryExtraction,
    contract_score: float,
    ai_confidence: float | None,
) -> None:
    analysis_repo = AnalysisRepository(session, doc.organization_id)
    await analysis_repo.delete_for_document(doc.id)

    summary_row = DocumentSummary(
        id=uuid.uuid4(),
        document_id=doc.id,
        parties=_parties_json(metadata),
        purpose=summary.purpose,
        duration=summary.duration,
        termination_conditions=summary.termination_summary,
        key_risks=summary.key_risks_summary,
        financial_terms=summary.financial_terms_summary,
        governing_law=metadata.governing_law,
        effective_date=_parse_model_date(metadata.effective_date),
        expiration_date=_parse_model_date(metadata.expiration_date),
        contract_value=metadata.contract_value,
        contract_currency=metadata.contract_currency,
        source_data={
            "prompt_version": PROMPT_VERSION,
            "scores_version": SCORES_VERSION,
            "clause_ids": [str(c.id) for c in clauses],
            "risk_ids": [str(r.id) for r in risks],
        },
    )
    session.add_all(clauses)
    session.add_all(risks)
    session.add_all(entities)
    session.add_all(obligations)
    session.add(summary_row)

    doc.contract_score = contract_score
    doc.ai_confidence_score = ai_confidence
    session.add(doc)
    await session.commit()


def _parties_json(metadata: MetadataExtraction) -> str | None:
    if not metadata.parties:
        return None
    return json.dumps([p.model_dump() for p in metadata.parties])
