"""Clause type catalog: descriptions for prompts, keywords for candidate retrieval.

Candidate retrieval for clause detection is implemented as keyword-overlap
scoring over the document's own chunks rather than a Qdrant similarity
query: it is deterministic, testable, and robust regardless of the embedding
provider (including the mock used in dev). Semantic retrieval can be layered
in behind the same interface once real embeddings are enabled.
"""
from __future__ import annotations

from app.models.models import Chunk, ClauseType

CLAUSE_TYPE_DESCRIPTIONS: dict[ClauseType, str] = {
    ClauseType.TERMINATION: (
        "how the agreement can be ended, notice periods, termination for cause or convenience"
    ),
    ClauseType.CONFIDENTIALITY: (
        "protection of confidential information, non-disclosure obligations"
    ),
    ClauseType.INDEMNIFICATION: (
        "one party compensating the other for losses or damages, hold-harmless provisions"
    ),
    ClauseType.LIABILITY: (
        "limitation or exclusion of liability, liability caps, consequential damages waivers"
    ),
    ClauseType.ARBITRATION: "dispute resolution via arbitration rather than courts",
    ClauseType.PAYMENT: "fees, payment amounts, invoicing and payment timing",
    ClauseType.IP: "intellectual property ownership, licenses, patents, copyrights, trademarks",
    ClauseType.JURISDICTION: "governing law, choice of forum, venue, jurisdiction",
    ClauseType.RENEWAL: "term renewal, automatic renewal, extension of the agreement",
    ClauseType.FORCE_MAJEURE: "excuse of performance for events beyond a party's control",
}

CLAUSE_KEYWORDS: dict[str, list[str]] = {
    "termination": ["terminat", "cancel", "end of the agreement"],
    "confidentiality": ["confidential"],
    "indemnification": ["indemnif", "hold harmless"],
    "liability": ["liab"],
    "arbitration": ["arbitrat"],
    "payment": ["payment", "shall pay", "invoice", "fee"],
    "ip": ["intellectual property", "patent", "copyright", "trademark"],
    "jurisdiction": ["jurisdiction", "governing law", "governed by", "venue"],
    "renewal": ["renew"],
    "force_majeure": ["force majeure", "act of god"],
}

MAX_CANDIDATE_CHUNKS = 5


def retrieve_candidates(
    chunks: list[Chunk], clause_type: ClauseType
) -> list[Chunk]:
    """Return the top chunks most likely to contain the given clause type."""
    keywords = CLAUSE_KEYWORDS.get(clause_type.value, [])
    if not keywords:
        return chunks[:MAX_CANDIDATE_CHUNKS]

    scored: list[tuple[int, int, Chunk]] = []
    for chunk in chunks:
        text = (chunk.text or "").lower()
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scored.append((score, chunk.chunk_index, chunk))
    scored.sort(key=lambda item: (-item[0], item[1]))
    candidates = [entry[2] for entry in scored]
    if not candidates:
        candidates = chunks[:2]
    return candidates[:MAX_CANDIDATE_CHUNKS]
