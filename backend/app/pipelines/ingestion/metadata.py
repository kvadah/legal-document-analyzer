"""Lightweight metadata extraction during ingestion."""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.models.models import DocumentType


@dataclass
class IngestionMetadata:
    document_type: DocumentType
    language: str
    parties: str | None = None


_TYPE_KEYWORDS: list[tuple[DocumentType, tuple[str, ...]]] = [
    (DocumentType.NDA, ("non-disclosure", "confidentiality agreement", "nda")),
    (DocumentType.EMPLOYMENT_AGREEMENT, ("employment agreement", "offer letter", "employee")),
    (DocumentType.LEASE, ("lease agreement", "landlord", "tenant", "premises")),
    (DocumentType.PROCUREMENT, ("procurement", "purchase order", "vendor agreement")),
    (DocumentType.INSURANCE, ("insurance policy", "insured", "premium", "coverage")),
    (DocumentType.GOVERNMENT_FORM, ("government form", "permit", "regulatory filing")),
    (DocumentType.POLICY, ("policy", "code of conduct")),
    (DocumentType.TOS, ("terms of service", "terms and conditions", "end user license")),
    (DocumentType.CONTRACT, ("agreement", "contract", "master services")),
]


def extract_metadata(text: str, *, page_count: int) -> IngestionMetadata:  # noqa: ARG001
    lowered = text.lower()
    doc_type = DocumentType.OTHER
    for candidate, keywords in _TYPE_KEYWORDS:
        if any(keyword in lowered for keyword in keywords):
            doc_type = candidate
            break

    language = _detect_language(text)
    parties = _extract_parties(text)
    return IngestionMetadata(document_type=doc_type, language=language, parties=parties)


def _detect_language(text: str) -> str:
    # Lightweight heuristic until langdetect is added as a dependency.
    if re.search(r"[\u0600-\u06FF]", text):
        return "ar"
    if re.search(r"[\u4e00-\u9fff]", text):
        return "zh"
    return "en"


def _extract_parties(text: str) -> str | None:
    match = re.search(
        r"(?:between|by and between)\s+(.{3,120}?)(?:\s+and\s+|\s*,)",
        text,
        flags=re.IGNORECASE,
    )
    return match.group(1).strip() if match else None
