"""Deterministic mock LLM provider for dev/test without API keys.

Implements the same heuristic quality as the mock embedding provider: it
parses the bracketed chunk headers (`[chunk_id | page N]`) from the context
and extracts grounded results with regex heuristics. Every extracted span is
copied verbatim from the context so grounding validation passes.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from pydantic import BaseModel

from app.llm.base import ModelTier, StructuredResult
from app.pipelines.ai.clause_types import CLAUSE_KEYWORDS
from app.pipelines.ai.extraction import (
    ClauseDetectionResult,
    ClauseInstance,
    EntityInstance,
    EntityListResult,
    MetadataExtraction,
    ObligationInstance,
    ObligationListResult,
    PartyInfo,
    QaAnswerResult,
    QaCitation,
    RiskJudgmentResult,
    SummaryExtraction,
)

_CHUNK_HEADER = re.compile(r"^\[([0-9a-fA-F-]{36}) \| page (\d+)\]$", re.MULTILINE)

_CAP_PHRASES = [
    "shall not exceed",
    "aggregate liability",
    "limited to",
    "liability shall be limited",
]
_AMBIGUOUS_PHRASES = [
    "reasonable efforts",
    "as soon as practicable",
    "commercially reasonable",
    "best efforts",
    "in a timely manner",
]
_AUTO_RENEW_RE = re.compile(r"automat\w+ renew|auto-renew", re.IGNORECASE)
_OPT_OUT_RE = re.compile(r"terminat|cancel|opt.?(out|down)|written notice", re.IGNORECASE)

_MONTHS = (
    "january|february|march|april|may|june|july|august|september|october|november|december"
)
_DATE_RE = re.compile(rf"\b({_MONTHS}) (\d{{1,2}},? \d{{4}})\b", re.IGNORECASE)
_ISO_DATE_RE = re.compile(r"\b(\d{{4}})-(\d{{2}})-(\d{{2}})\b")
_MONEY_RE = re.compile(r"\$\s?([\d,]+(?:\.\d{1,2})?)")
_COMPANY_RE = re.compile(
    r"\b([A-Z][A-Za-z0-9&'’.\-]*(?: [A-Z][A-Za-z0-9&'’.\-]*){0,3} "
    r"(?:Inc|LLC|Ltd|Corp|Corporation|Company|GmbH|LLP)\.?)\b"
)
_GOVERNING_LAW_RE = re.compile(
    r"governed by (?:the )?(?:laws|law) of ((?:the )?[A-Z][A-Za-z .]{2,40}?)(?=[.,;\n]|$)"
)
_PARTIES_RE = re.compile(
    r"between ([A-Z][A-Za-z0-9&'’.\- ]{1,60}?) and ([A-Z][A-Za-z0-9&'’.\- ]{1,60}?)(?=[.,;\n]|$)"
)
_WITHIN_DAYS_RE = re.compile(r"within (\d{1,4}) (?:\(| )?(business )?days", re.IGNORECASE)


@dataclass
class _Chunk:
    chunk_id: str
    page: int
    text: str


@dataclass
class MockLLMProvider:
    """Heuristic, deterministic provider used when MOCK_LLM=true."""

    call_count: int = 0
    calls: list[str] = field(default_factory=list)

    def _chunks(self, context: list[str]) -> list[_Chunk]:
        chunks: list[_Chunk] = []
        for block in context:
            match = _CHUNK_HEADER.search(block)
            if match is None:
                chunks.append(_Chunk("", 1, block))
                continue
            text = block[match.end() :].strip()
            chunks.append(_Chunk(match.group(1), int(match.group(2)), text))
        return chunks

    async def generate_structured(
        self,
        prompt: str,
        schema: type[BaseModel],
        context: list[str],
        model_tier: ModelTier,
        prompt_version: str = "unversioned",
    ) -> StructuredResult:
        self.call_count += 1
        self.calls.append(schema.__name__)
        chunks = self._chunks(context)
        result: BaseModel
        if schema is MetadataExtraction:
            result = self._metadata(chunks, prompt)
        elif schema is ClauseDetectionResult:
            result = self._clause_detection(chunks, prompt)
        elif schema is EntityListResult:
            result = self._entities(chunks)
        elif schema is ObligationListResult:
            result = self._obligations(chunks)
        elif schema is RiskJudgmentResult:
            result = self._risk_judgment(chunks, prompt)
        elif schema is SummaryExtraction:
            result = self._summary(context)
        elif schema is QaAnswerResult:
            result = self._qa(chunks, prompt)
        else:
            raise ValueError(f"MockLLMProvider cannot handle schema {schema.__name__}")
        return StructuredResult(
            result=result,
            model_version=f"mock-{model_tier}",
            prompt_version=prompt_version,
            latency_ms=0,
            token_usage={"input": 0, "output": 0},
        )

    def _qa(self, chunks: list[_Chunk], prompt: str) -> QaAnswerResult:
        """Heuristic grounded Q&A: pick sentences sharing keywords with the question.

        The question itself is embedded in the prompt after the template; pull it
        out, tokenize it, and cite verbatim sentences from the context chunks
        that contain those keywords — so grounding validation always passes.
        """
        question = prompt.split("Question:")[-1].split("Context:")[0].strip()
        advisory = re.search(
            r"\b(should|shall) (i|we)\b|\badvise\b|\brecommend\b", question, re.IGNORECASE
        )
        if advisory:
            return QaAnswerResult(
                found_in_document=True,
                answer=(
                    "I can't provide legal advice or a recommendation on that decision. "
                    "I can tell you what the document says about the relevant subject — "
                    "whether to proceed is a decision for you and your legal counsel."
                ),
                citations=[],
            )

        stop = {
            "what", "which", "who", "whom", "whose", "when", "where", "why", "how",
            "is", "are", "was", "were", "does", "do", "did", "the", "a", "an",
            "of", "in", "on", "for", "to", "and", "or", "it", "this", "that",
            "there", "any", "clause", "document", "agreement", "contract",
        }
        keywords = {
            w for w in re.findall(r"[a-zA-Z$][a-zA-Z0-9'-]*", question.lower())
            if w not in stop and len(w) > 2
        }
        if not keywords:
            keywords = {question.lower().strip()}

        cited: list[QaCitation] = []
        parts: list[str] = []
        for chunk in chunks:
            if not chunk.chunk_id:
                continue
            for sentence in self._sentences(chunk.text):
                lower = sentence.lower()
                if any(kw in lower for kw in keywords):
                    cited.append(
                        QaCitation(chunk_id=chunk.chunk_id, supporting_sentence=sentence)
                    )
                    parts.append(f"{sentence} [{len(cited)}]")
                    if len(cited) >= 4:
                        break
            if len(cited) >= 4:
                break

        if not cited:
            return QaAnswerResult(
                found_in_document=False,
                answer=(
                    "I couldn't find information about this in the document."
                ),
                citations=[],
            )
        return QaAnswerResult(
            found_in_document=True,
            answer=(
                "Based on the document: " + " ".join(parts)
            ),
            citations=cited,
        )

    def _sentences(self, text: str) -> list[str]:
        return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]

    def _clause_type(self, prompt: str) -> str:
        prompt_lower = prompt.lower()
        for clause_type, keywords in CLAUSE_KEYWORDS.items():
            if any(kw in prompt_lower for kw in keywords):
                return clause_type
        return "other"

    def _metadata(self, chunks: list[_Chunk], prompt: str) -> MetadataExtraction:
        full_text = "\n".join(c.text for c in chunks)
        parties: list[PartyInfo] = []
        party_match = _PARTIES_RE.search(full_text)
        if party_match:
            parties.append(PartyInfo(name=party_match.group(1).strip()))
            parties.append(PartyInfo(name=party_match.group(2).strip()))
        governing_law = None
        law_match = _GOVERNING_LAW_RE.search(full_text)
        if law_match:
            governing_law = law_match.group(1).strip()
        date_matches = [m.group(0) for m in _DATE_RE.finditer(full_text)]
        effective = self._normalize_date(date_matches[0]) if date_matches else None
        expiration = self._normalize_date(date_matches[-1]) if len(date_matches) > 1 else None
        money_matches = _MONEY_RE.findall(full_text)
        contract_value = None
        if money_matches:
            amounts = [float(m.replace(",", "")) for m in money_matches]
            contract_value = max(amounts)
        return MetadataExtraction(
            parties=parties,
            governing_law=governing_law,
            effective_date=effective,
            expiration_date=expiration,
            contract_value=contract_value,
            contract_currency="USD" if contract_value is not None else None,
        )

    def _clause_detection(self, chunks: list[_Chunk], prompt: str) -> ClauseDetectionResult:
        clause_type = self._clause_type(prompt)
        keywords = CLAUSE_KEYWORDS.get(clause_type, [])
        instances: list[ClauseInstance] = []
        for chunk in chunks:
            if not chunk.chunk_id:
                continue
            for sentence in self._sentences(chunk.text):
                lower = sentence.lower()
                if any(kw in lower for kw in keywords):
                    instances.append(
                        ClauseInstance(
                            chunk_id=chunk.chunk_id,
                            extracted_text=sentence,
                            summary=(
                                f"{clause_type.replace('_', ' ').title()} "
                                f"provision: {sentence[:120]}"
                            ),
                            confidence=0.85,
                        )
                    )
        return ClauseDetectionResult(found=bool(instances), instances=instances)

    def _entities(self, chunks: list[_Chunk]) -> EntityListResult:
        entities: list[EntityInstance] = []
        seen: set[tuple[str, str]] = set()
        for chunk in chunks:
            if not chunk.chunk_id:
                continue
            for match in _COMPANY_RE.finditer(chunk.text):
                raw = match.group(0).strip()
                if (raw, chunk.chunk_id) not in seen:
                    seen.add((raw, chunk.chunk_id))
                    entities.append(
                        EntityInstance(
                            entity_type="company",
                            value=raw,
                            raw_text=raw,
                            chunk_id=chunk.chunk_id,
                            confidence=0.85,
                        )
                    )
            for match in _DATE_RE.finditer(chunk.text):
                raw = match.group(0)
                if (raw, chunk.chunk_id) not in seen:
                    seen.add((raw, chunk.chunk_id))
                    normalized = self._normalize_date(raw)
                    entities.append(
                        EntityInstance(
                            entity_type="date",
                            value=normalized,
                            raw_text=raw,
                            chunk_id=chunk.chunk_id,
                            confidence=0.85,
                        )
                    )
            for match in _MONEY_RE.finditer(chunk.text):
                raw = match.group(0)
                if (raw, chunk.chunk_id) not in seen:
                    seen.add((raw, chunk.chunk_id))
                    entities.append(
                        EntityInstance(
                            entity_type="money",
                            value=str(float(match.group(1).replace(",", ""))),
                            raw_text=raw,
                            chunk_id=chunk.chunk_id,
                            confidence=0.85,
                        )
                    )
        return EntityListResult(entities=entities)

    def _normalize_date(self, raw: str) -> str:
        try:
            parsed = datetime.strptime(raw.replace(",", ", ").replace("  ", " "), "%B %d, %Y")
            return parsed.date().isoformat()
        except ValueError:
            return raw

    def _obligations(self, chunks: list[_Chunk]) -> ObligationListResult:
        obligations: list[ObligationInstance] = []
        for chunk in chunks:
            if not chunk.chunk_id:
                continue
            for sentence in self._sentences(chunk.text):
                if "shall" not in sentence.lower():
                    continue
                within = _WITHIN_DAYS_RE.search(sentence)
                pay_words = "pay" in sentence.lower() or "payment" in sentence.lower()
                if within is None and not pay_words:
                    continue
                deadline_type = "payment_date" if pay_words else "other"
                obligations.append(
                    ObligationInstance(
                        obligated_party="All parties",
                        description=sentence,
                        deadline_date=None,
                        deadline_type=deadline_type,
                        chunk_id=chunk.chunk_id,
                        confidence=0.8,
                    )
                )
        return ObligationListResult(obligations=obligations)

    def _risk_judgment(self, chunks: list[_Chunk], prompt: str) -> RiskJudgmentResult:
        prompt_lower = prompt.lower()
        full_text = "\n".join(c.text for c in chunks)
        if "unlimited liability" in prompt_lower:
            has_liability = "liab" in full_text.lower()
            has_cap = any(p in full_text.lower() for p in _CAP_PHRASES)
            if has_liability and not has_cap:
                return RiskJudgmentResult(
                    flagged=True,
                    severity="high",
                    description="Liability provisions do not state a monetary cap.",
                    recommendation="Consider clarifying the liability cap with the counterparty.",
                    confidence=0.8,
                )
        elif "vague or undefined" in prompt_lower or "ambiguous" in prompt_lower:
            hits = [p for p in _AMBIGUOUS_PHRASES if p in full_text.lower()]
            if hits:
                return RiskJudgmentResult(
                    flagged=True,
                    severity="low",
                    description=f"Vague term(s) used without definition: {', '.join(hits)}.",
                    recommendation="Consider defining the standard of effort explicitly.",
                    confidence=0.75,
                )
        elif "automatic renewal" in prompt_lower:
            has_auto_renew = _AUTO_RENEW_RE.search(full_text) is not None
            has_opt_out = _OPT_OUT_RE.search(full_text) is not None
            if has_auto_renew and not has_opt_out:
                return RiskJudgmentResult(
                    flagged=True,
                    severity="medium",
                    description=(
                        "The agreement renews automatically without an explicit "
                        "opt-out right."
                    ),
                    recommendation="Consider negotiating an opt-out window for automatic renewal.",
                    confidence=0.75,
                )
        elif "penalt" in prompt_lower:
            return RiskJudgmentResult(flagged=False, severity="low", description="", confidence=0.7)
        return RiskJudgmentResult(flagged=False, severity="low", description="", confidence=0.7)

    def _summary(self, context: list[str]) -> SummaryExtraction:
        parties: list[str] = []
        purpose_sentences: list[str] = []
        termination = ""
        risks: list[str] = []
        financial: list[str] = []
        for line in "\n".join(context).splitlines():
            stripped = line.strip()
            if stripped.startswith("[metadata]"):
                tail = stripped.split("parties=", 1)[-1].split(";", 1)[0]
                parties = [p.strip() for p in tail.split(",") if p.strip()]
            elif stripped.startswith("[clause:termination]"):
                termination = stripped.split("] ", 1)[-1]
            elif stripped.startswith("[risk:"):
                risks.append(stripped.split("] ", 1)[-1])
            elif stripped.startswith("[clause:payment]"):
                financial.append(stripped.split("] ", 1)[-1])
            elif stripped.startswith("[purpose:"):
                purpose_sentences.append(stripped.split("] ", 1)[-1])
        purpose = (
            f"Agreement between {', '.join(parties)}."
            if parties
            else (purpose_sentences[0] if purpose_sentences else None)
        )
        return SummaryExtraction(
            purpose=purpose,
            duration=None,
            termination_summary=termination or None,
            key_risks_summary=(" ".join(risks) if risks else None),
            financial_terms_summary=(" ".join(financial) if financial else None),
        )
