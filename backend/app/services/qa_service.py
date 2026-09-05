"""Grounded RAG Q&A service (07-feature-spec-comparison-search.md §4).

Flow: verify access → embed question → vector retrieval scoped to the document
→ similarity threshold check (before the LLM call) → structured LLM answer
with sentence-level citations → grounding validation (drop + strip citations
whose quote isn't verbatim in the cited chunk) → Redis conversation history.

Answers stream to the client as SSE events (citations → deltas → done).
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import CurrentUser
from app.db.redis import get_redis
from app.llm import get_llm_provider
from app.llm.prompts import PROMPT_VERSION, QA_PROMPT
from app.models.models import Chunk, Document, DocumentStatus
from app.pipelines.ai.extraction import QaAnswerResult
from app.providers.embeddings import get_embedding_provider
from app.schemas.search import (
    AskCitation,
    AskCitationsEvent,
    AskDeltaEvent,
    AskDoneEvent,
)
from app.services.document_service import get_document
from app.services.vector_store import get_vector_store

logger = logging.getLogger(__name__)

QA_STATUSES = {
    DocumentStatus.INGESTION_READY,
    DocumentStatus.AI_PIPELINE_PROCESSING,
    DocumentStatus.ANALYSIS_READY,
}

_CONVERSATION_KEY = "qa:conversation:{conversation_id}"
_MARKER_RE = re.compile(r"\[(\d+)\]")


def _conversation_key(conversation_id: str) -> str:
    return _CONVERSATION_KEY.format(conversation_id=conversation_id)


def verify_askable(doc_status: str) -> None:
    """Raise 409 if the document hasn't reached a text-available status."""
    if DocumentStatus(doc_status) not in QA_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "document_not_ready",
                "message": f"Document text is not available yet (status: {doc_status}).",
            },
        )


async def _load_history(conversation_id: str) -> list[dict]:
    try:
        redis = await get_redis()
        raw = await redis.lrange(_conversation_key(conversation_id), 0, -1)
        return [json.loads(item) for item in raw]
    except Exception:
        logger.warning("qa.history_unavailable", exc_info=True)
        return []


async def _append_history(conversation_id: str, question: str, answer: str) -> None:
    try:
        redis = await get_redis()
        key = _conversation_key(conversation_id)
        await redis.rpush(key, json.dumps({"question": question, "answer": answer}))
        await redis.ltrim(key, -settings.rag_history_turns * 2, -1)
        await redis.expire(key, settings.rag_conversation_ttl_seconds)
    except Exception:
        logger.warning("qa.history_write_failed", exc_info=True)


async def _retrieve_chunks(
    session: AsyncSession, *, document_id: UUID, org_id: str, question: str
) -> list[tuple[Chunk, float]]:
    provider = get_embedding_provider()
    vectors = await provider.embed_texts([question])
    if not vectors:
        return []
    hits = await get_vector_store().search(
        vectors[0],
        organization_id=org_id,
        document_ids=[str(document_id)],
        limit=settings.rag_top_k,
    )
    if not hits:
        return []
    scores = {hit.chunk_id: hit.score for hit in hits}
    # Org-scoped re-hydration from Postgres (authoritative over vector payloads)
    stmt = (
        select(Chunk)
        .join(Document, Chunk.document_id == Document.id)
        .where(
            Chunk.id.in_([UUID(hit.chunk_id) for hit in hits]),
            Document.organization_id == UUID(org_id),
        )
    )
    rows = (await session.execute(stmt)).scalars().all()
    return sorted(
        ((chunk, scores.get(str(chunk.id), 0.0)) for chunk in rows),
        key=lambda pair: pair[1],
        reverse=True,
    )


def _validate_citations(
    answer: QaAnswerResult, chunks: dict[str, Chunk]
) -> tuple[str, list[tuple[str, Chunk, str]]]:
    """Drop citations whose quote isn't verbatim in the cited chunk, renumber
    the surviving markers in the answer text accordingly, and return
    (answer_text, valid_citations) in citation order.
    """
    valid: list[tuple[str, Chunk, str]] = []
    renumber: dict[int, int] = {}
    for original_index, citation in enumerate(answer.citations, start=1):
        chunk = chunks.get(citation.chunk_id)
        if chunk is None or citation.supporting_sentence not in (chunk.text or ""):
            logger.warning(
                "qa.citation_grounding_failed", extra={"chunk_id": citation.chunk_id}
            )
            continue
        renumber[original_index] = len(valid) + 1
        valid.append((citation.chunk_id, chunk, citation.supporting_sentence))

    def _replace_marker(match: re.Match[str]) -> str:
        original = int(match.group(1))
        if original in renumber:
            return f"[{renumber[original]}]"
        return ""

    text = _MARKER_RE.sub(_replace_marker, answer.answer)
    text = re.sub(r"  +", " ", text).strip()
    return text, valid


def _split_deltas(text: str) -> list[str]:
    """Split the answer into sentence-level deltas for SSE streaming."""
    return [part for part in re.split(r"(?<=[.!?])\s+", text) if part]


async def ask(
    session: AsyncSession,
    *,
    current_user: CurrentUser,
    document_id: UUID,
    question: str,
    conversation_id: str | None,
):
    """Async generator yielding SSE-ready event dicts for one Q&A turn."""
    doc = await get_document(session, current_user=current_user, document_id=document_id)
    verify_askable(doc.status)

    conversation_id = conversation_id or str(uuid.uuid4())
    history = await _load_history(conversation_id) if conversation_id else []
    history = history[-settings.rag_history_turns:]

    retrieved = await _retrieve_chunks(
        session, document_id=document_id, org_id=current_user.org_id, question=question
    )

    # Threshold check BEFORE the LLM call — don't force a generation on
    # un-groundable questions (spec §4 failure-mode handling).
    threshold = settings.rag_similarity_threshold
    if threshold > 0 and (
        not retrieved or max(score for _chunk, score in retrieved) < threshold
    ):
        not_found = (
            "I couldn't find information about this in the document."
        )
        await _append_history(conversation_id, question, not_found)
        yield {"event": "citations", "data": AskCitationsEvent(citations=[]).model_dump_json()}
        yield {"event": "delta", "data": AskDeltaEvent(text=not_found).model_dump_json()}
        yield {
            "event": "done",
            "data": AskDoneEvent(
                conversation_id=conversation_id,
                found_in_document=False,
                answer=not_found,
            ).model_dump_json(),
        }
        return

    chunks_by_id = {str(chunk.id): chunk for chunk, _score in retrieved}
    context_blocks = [
        f"[{chunk.id} | page {chunk.page_number}]\n{chunk.text}"
        for chunk, _score in retrieved
    ]

    history_lines = [
        f"Earlier turn — Q: {turn['question']} A: {turn['answer'][:300]}"
        for turn in history
    ]
    prompt = (
        QA_PROMPT
        + ("\nConversation history (for context only):\n"
           + "\n".join(history_lines) + "\n\n" if history_lines else "")
        + f"Question: {question}\n\nContext:\n"
        + "\n\n".join(context_blocks)
    )

    provider = get_llm_provider()
    result = await provider.generate_structured(
        prompt,
        QaAnswerResult,
        context_blocks,
        "capable",
        prompt_version=PROMPT_VERSION,
    )
    answer = result.typed(QaAnswerResult)

    text, valid = _validate_citations(answer, chunks_by_id)
    citations = [
        AskCitation(
            index=i + 1,
            chunk_id=chunk_id,
            page_number=chunk.page_number,
            quote=quote,
        )
        for i, (chunk_id, chunk, quote) in enumerate(valid)
    ]

    yield {"event": "citations", "data": AskCitationsEvent(citations=citations).model_dump_json()}
    for delta in _split_deltas(text):
        yield {"event": "delta", "data": AskDeltaEvent(text=delta + " ").model_dump_json()}
    await _append_history(conversation_id, question, text)
    yield {
        "event": "done",
        "data": AskDoneEvent(
            conversation_id=conversation_id,
            found_in_document=answer.found_in_document,
            answer=text,
        ).model_dump_json(),
    }
