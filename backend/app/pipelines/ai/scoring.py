"""Contract Score and AI Confidence Score computation.

Contract Score v1 — a deterministic, auditable document-health score (NOT an
LLM output), per spec 05-ai-pipeline.md §8:

    score = clamp(100 - sum(severity_weight(r.severity) for r in risks), 0, 100)

with weights: critical=25, high=15, medium=8, low=3.

Absence of standard protective clauses (termination, confidentiality,
liability cap, governing law) is captured by the rule-based risk flags in
risk_rules.py, so the risk sum alone encodes both dimensions — there is no
separate deduction to avoid double-counting.

AI Confidence Score v1 — weighted mean of individual extraction confidence
scores, communicating how much to trust the analysis:

    confidence = (0.5 * mean(clause confidences)
                + 0.25 * mean(LLM-judgment risk confidences)
                + 0.25 * mean(entity confidences)) / weight_total

multiplied by 0.9 when the OCR pass flagged low quality (poor scan quality
degrades every downstream extraction). Obligations carry no persisted
confidence column and are excluded from v1. Null when no extractions exist.

Both formulas are versioned (SCORES_VERSION) because users rely on these
numbers to triage a portfolio; any change must bump the version.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.models.models import Clause, Entity, Risk, RiskSeverity

SCORES_VERSION = 1

SEVERITY_WEIGHTS: dict[RiskSeverity, int] = {
    RiskSeverity.CRITICAL: 25,
    RiskSeverity.HIGH: 15,
    RiskSeverity.MEDIUM: 8,
    RiskSeverity.LOW: 3,
}

_OCR_QUALITY_FACTOR = 0.9


@dataclass
class ScoreBreakdown:
    """Per-risk deductions for the score endpoint's breakdown payload."""

    risk_deductions: list[dict[str, object]] = field(default_factory=list)
    total_deduction: int = 0


def compute_contract_score(risks: list[Risk]) -> tuple[float, ScoreBreakdown]:
    breakdown = ScoreBreakdown()
    for risk in risks:
        weight = SEVERITY_WEIGHTS[risk.severity]
        breakdown.risk_deductions.append(
            {
                "risk_id": str(risk.id),
                "risk_type": risk.risk_type.value,
                "severity": risk.severity.value,
                "deduction": weight,
            }
        )
        breakdown.total_deduction += weight
    score = float(max(0, min(100, 100 - breakdown.total_deduction)))
    return score, breakdown


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def compute_ai_confidence(
    clauses: list[Clause],
    llm_risks: list[Risk],
    entities: list[Entity],
    *,
    low_quality_ocr: bool = False,
) -> float | None:
    clause_conf = _mean(
        [float(c.confidence_score) for c in clauses if c.confidence_score is not None]
    )
    risk_conf = _mean(
        [float(r.confidence_score) for r in llm_risks if r.confidence_score is not None]
    )
    entity_conf = _mean(
        [float(e.confidence_score) for e in entities if e.confidence_score is not None]
    )

    weighted_sum = 0.0
    weight_total = 0.0
    for value, weight in (
        (clause_conf, 0.5),
        (risk_conf, 0.25),
        (entity_conf, 0.25),
    ):
        if value is not None:
            weighted_sum += value * weight
            weight_total += weight
    if weight_total == 0.0:
        return None
    confidence = weighted_sum / weight_total
    if low_quality_ocr:
        confidence *= _OCR_QUALITY_FACTOR
    return round(confidence, 2)
