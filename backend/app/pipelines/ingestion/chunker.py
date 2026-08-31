"""Structural chunking for parsed document paragraphs."""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.config import settings
from app.pipelines.ingestion.ocr import TextBlock


@dataclass
class ChunkDraft:
    text: str
    page_number: int
    paragraph_index: int | None
    section_heading: str | None
    token_count: int
    chunk_index: int


_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def estimate_tokens(text: str) -> int:
    return max(1, int(len(text.split()) * 1.3))


def chunk_paragraphs(blocks: list[TextBlock]) -> list[ChunkDraft]:
    target = settings.chunk_target_tokens
    hard_max = settings.chunk_max_tokens
    overlap_ratio = settings.chunk_overlap_ratio

    drafts: list[ChunkDraft] = []
    current_parts: list[str] = []
    current_tokens = 0
    current_meta: TextBlock | None = None
    current_heading: str | None = None
    chunk_index = 0

    def flush() -> None:
        nonlocal chunk_index, current_parts, current_tokens
        if not current_parts:
            return
        text = "\n\n".join(current_parts).strip()
        if not text:
            return
        meta = current_meta or (blocks[0] if blocks else TextBlock("", 1, 0))
        drafts.append(
            ChunkDraft(
                text=text,
                page_number=meta.page_number,
                paragraph_index=meta.paragraph_index,
                section_heading=current_heading,
                token_count=estimate_tokens(text),
                chunk_index=chunk_index,
            )
        )
        chunk_index += 1
        if overlap_ratio > 0:
            overlap_len = max(1, int(len(text) * overlap_ratio))
            overlap_text = text[-overlap_len:]
            current_parts = [overlap_text]
            current_tokens = estimate_tokens(overlap_text)
        else:
            current_parts = []
            current_tokens = 0

    def add_text(piece: str, block: TextBlock) -> None:
        nonlocal current_tokens, current_meta
        piece = piece.strip()
        if not piece:
            return
        piece_tokens = estimate_tokens(piece)
        if piece_tokens > hard_max:
            for sentence in _SENTENCE_RE.split(piece):
                add_text(sentence, block)
            return
        if current_tokens + piece_tokens > target and current_parts:
            flush()
        current_meta = block
        current_parts.append(piece)
        current_tokens += piece_tokens
        if current_tokens >= hard_max:
            flush()

    for block in blocks:
        if not block.text.strip():
            continue
        if block.text.isupper() and len(block.text.split()) <= 8:
            current_heading = block.text.strip()
        for para in [p.strip() for p in block.text.split("\n\n") if p.strip()]:
            add_text(para, block)

    flush()
    return drafts
