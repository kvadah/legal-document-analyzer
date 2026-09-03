"""Rule-based risk checks (deterministic baseline, run before LLM judgment).

Spec 05-ai-pipeline.md §6: rules provide deterministic, auditable coverage;
the LLM handles nuance. Absence of a protective clause is itself a risk flag.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.models.models import Clause, ClauseType, DocumentType, RiskSeverity, RiskType

_AUTO_RENEW_RE = re.compile(r"automat\w+ renew|auto-renew", re.IGNORECASE)
_OPT_OUT_RE = re.compile(r"terminat|cancel|opt.?(out|down)|written notice", re.IGNORECASE)
_NOTICE_DAYS_RE = re.compile(r"(\d{1,4})\s*(?:\(| )?(?:business\s+)?days?", re.IGNORECASE)

CONFIDENTIALITY_EXPECTED_TYPES = {
    DocumentType.NDA,
    DocumentType.EMPLOYMENT_AGREEMENT,
}


@dataclass
class RuleRisk:
    risk_type: RiskType
    severity: RiskSeverity
    description: str
    recommendation: str


def check_missing_termination(clauses: list[Clause]) -> RuleRisk | None:
    if any(c.clause_type == ClauseType.TERMINATION for c in clauses):
        return None
    return RuleRisk(
        risk_type=RiskType.MISSING_TERMINATION,
        severity=RiskSeverity.HIGH,
        description="No termination clause was detected in the document.",
        recommendation="Consider adding an explicit termination provision with notice terms.",
    )


def check_missing_confidentiality(
    clauses: list[Clause], document_type: DocumentType
) -> RuleRisk | None:
    if document_type not in CONFIDENTIALITY_EXPECTED_TYPES:
        return None
    if any(c.clause_type == ClauseType.CONFIDENTIALITY for c in clauses):
        return None
    return RuleRisk(
        risk_type=RiskType.MISSING_NDA,
        severity=RiskSeverity.HIGH,
        description=(
            f"No confidentiality clause detected, which is expected for a "
            f"{document_type.value.replace('_', ' ')} document."
        ),
        recommendation=(
            "Consider adding confidentiality obligations appropriate to this "
            "document type."
        ),
    )


def check_no_governing_law(governing_law: str | None) -> RuleRisk | None:
    if governing_law:
        return None
    return RuleRisk(
        risk_type=RiskType.NO_GOVERNING_LAW,
        severity=RiskSeverity.MEDIUM,
        description="The document does not state a governing law or jurisdiction.",
        recommendation="Consider specifying the governing jurisdiction to avoid dispute ambiguity.",
    )


def check_auto_renewal(clauses: list[Clause]) -> RuleRisk | None:
    renewal_clauses = [c for c in clauses if c.clause_type == ClauseType.RENEWAL]
    for clause in renewal_clauses:
        text = clause.extracted_text or ""
        if not _AUTO_RENEW_RE.search(text):
            continue
        if _OPT_OUT_RE.search(text):
            continue
        days = _NOTICE_DAYS_RE.findall(text)
        if any(int(d) < 30 for d in days):
            return RuleRisk(
                risk_type=RiskType.AUTO_RENEWAL,
                severity=RiskSeverity.MEDIUM,
                description=(
                    "Renewal clause renews automatically with a notice period "
                    "shorter than 30 days and no stated opt-out."
                ),
                recommendation="Consider negotiating an opt-out window for automatic renewal.",
            )
        return RuleRisk(
            risk_type=RiskType.AUTO_RENEWAL,
            severity=RiskSeverity.MEDIUM,
            description=(
                "Renewal clause renews automatically without an explicit opt-out right."
            ),
            recommendation="Consider negotiating an opt-out window for automatic renewal.",
        )
    return None


def run_rule_checks(
    clauses: list[Clause],
    document_type: DocumentType,
    governing_law: str | None,
) -> list[RuleRisk]:
    checks = [
        check_missing_termination(clauses),
        check_missing_confidentiality(clauses, document_type),
        check_no_governing_law(governing_law),
        check_auto_renewal(clauses),
    ]
    return [risk for risk in checks if risk is not None]
