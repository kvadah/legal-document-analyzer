"""Pure diff engine for clause comparison (07-feature-spec-comparison-search.md §1).

Deterministic and stdlib-only (difflib): clause alignment by type first then
textual similarity, word-level diffs for aligned pairs, and paragraph-level
"Other Changes" diffing for content outside the tracked clause types.

No DB, LLM, or framework access — fully unit-testable pure functions.
Inputs are duck-typed: clauses need ``clause_type``, ``extracted_text``,
``page_number``, ``summary`` and ``confidence_score`` attributes; chunks need
``text`` and ``page_number``.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

# Similarity threshold for pairing paragraphs inside a "replace" block:
# above it, a removed/added pair is reported as one "modified" entry;
# below it, as separate "removed" + "added" entries.
_PARAGRAPH_PAIR_THRESHOLD = 0.35
# A non-clause paragraph whose best counterpart on the other side is
# clause-covered is skipped, so clause changes are not duplicated in
# "Other Changes" (e.g. a reworded termination clause whose counterpart
# was detected as a clause only on one side).
_COUNTERPART_THRESHOLD = 0.4
# Hard cap on "other changes" entries to keep payloads bounded.
_MAX_OTHER_CHANGES = 200

_STATUS_ORDER = {"modified": 0, "added": 1, "removed": 2, "unchanged": 3}


def normalize_text(text: str) -> str:
    """Collapse all whitespace runs to single spaces (spec: immaterial
    whitespace/formatting differences count as unchanged)."""
    return " ".join((text or "").split())


def _similarity(text_a: str, text_b: str) -> float:
    matcher = SequenceMatcher(
        a=normalize_text(text_a), b=normalize_text(text_b), autojunk=False
    )
    return matcher.ratio()


def word_diff(text_a: str, text_b: str) -> list[dict[str, Any]]:
    """Word-level diff between two texts as a list of op segments.

    Each segment is ``{op, text_a, text_b}`` where ``op`` is one of
    ``equal`` / ``replace`` / ``delete`` / ``insert``; ``delete`` carries
    only ``text_a`` and ``insert`` only ``text_b``.
    """
    a_words = (text_a or "").split()
    b_words = (text_b or "").split()
    matcher = SequenceMatcher(a=a_words, b=b_words, autojunk=False)
    ops: list[dict[str, Any]] = []
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            ops.append(
                {
                    "op": "equal",
                    "text_a": " ".join(a_words[i1:i2]),
                    "text_b": " ".join(a_words[i1:i2]),
                }
            )
        elif op == "replace":
            ops.append(
                {
                    "op": "replace",
                    "text_a": " ".join(a_words[i1:i2]),
                    "text_b": " ".join(b_words[j1:j2]),
                }
            )
        elif op == "delete":
            ops.append({"op": "delete", "text_a": " ".join(a_words[i1:i2]), "text_b": None})
        else:  # insert
            ops.append({"op": "insert", "text_a": None, "text_b": " ".join(b_words[j1:j2])})
    return ops


def _greedy_pair(texts_a: list[str], texts_b: list[str]) -> list[tuple[int, int]]:
    """Greedy best-similarity assignment between two text lists.

    Returns ``(i, j)`` index pairs into *texts_a* / *texts_b*.
    """
    scored: list[tuple[float, int, int]] = []
    for i, text_a in enumerate(texts_a):
        for j, text_b in enumerate(texts_b):
            scored.append((_similarity(text_a, text_b), i, j))
    scored.sort(key=lambda entry: (-entry[0], entry[1], entry[2]))
    used_a: set[int] = set()
    used_b: set[int] = set()
    pairs: list[tuple[int, int]] = []
    for _, i, j in scored:
        if i in used_a or j in used_b:
            continue
        used_a.add(i)
        used_b.add(j)
        pairs.append((i, j))
    return pairs


def align_clauses(clauses_a: list[Any], clauses_b: list[Any]) -> list[dict[str, Any]]:
    """Align clauses by type, then by textual similarity within a type.

    Returns a list of diff entries ``{clause_type, status, text_a, text_b,
    word_diff, page_a, page_b, summary_a, summary_b, confidence_a,
    confidence_b}`` classified as added / removed / modified / unchanged.
    """
    def _key(clause: Any) -> str:
        value = clause.clause_type
        return value.value if hasattr(value, "value") else str(value)

    def _conf(clause: Any) -> float | None:
        return float(clause.confidence_score) if clause.confidence_score is not None else None

    by_type_a: dict[str, list[Any]] = {}
    for clause in clauses_a:
        by_type_a.setdefault(_key(clause), []).append(clause)
    by_type_b: dict[str, list[Any]] = {}
    for clause in clauses_b:
        by_type_b.setdefault(_key(clause), []).append(clause)

    entries: list[dict[str, Any]] = []
    for clause_type in sorted(set(by_type_a) | set(by_type_b)):
        a_list = by_type_a.get(clause_type, [])
        b_list = by_type_b.get(clause_type, [])
        pairs = _greedy_pair(
            [c.extracted_text for c in a_list],
            [c.extracted_text for c in b_list],
        )
        paired_a = {i for i, _ in pairs}
        paired_b = {j for _, j in pairs}
        for i, j in pairs:
            clause_a, clause_b = a_list[i], b_list[j]
            identical = normalize_text(clause_a.extracted_text) == normalize_text(
                clause_b.extracted_text
            )
            entries.append(
                {
                    "clause_type": clause_type,
                    "status": "unchanged" if identical else "modified",
                    "text_a": clause_a.extracted_text,
                    "text_b": clause_b.extracted_text,
                    "word_diff": (
                        []
                        if identical
                        else word_diff(clause_a.extracted_text, clause_b.extracted_text)
                    ),
                    "page_a": clause_a.page_number,
                    "page_b": clause_b.page_number,
                    "summary_a": clause_a.summary,
                    "summary_b": clause_b.summary,
                    "confidence_a": _conf(clause_a),
                    "confidence_b": _conf(clause_b),
                }
            )
        for i, clause_a in enumerate(a_list):
            if i in paired_a:
                continue
            entries.append(
                {
                    "clause_type": clause_type,
                    "status": "removed",
                    "text_a": clause_a.extracted_text,
                    "text_b": None,
                    "word_diff": None,
                    "page_a": clause_a.page_number,
                    "page_b": None,
                    "summary_a": clause_a.summary,
                    "summary_b": None,
                    "confidence_a": _conf(clause_a),
                    "confidence_b": None,
                }
            )
        for j, clause_b in enumerate(b_list):
            if j in paired_b:
                continue
            entries.append(
                {
                    "clause_type": clause_type,
                    "status": "added",
                    "text_a": None,
                    "text_b": clause_b.extracted_text,
                    "word_diff": None,
                    "page_a": None,
                    "page_b": clause_b.page_number,
                    "summary_a": None,
                    "summary_b": clause_b.summary,
                    "confidence_a": None,
                    "confidence_b": _conf(clause_b),
                }
            )

    entries.sort(
        key=lambda e: (e["clause_type"], _STATUS_ORDER.get(e["status"], 99))
    )
    return entries


def _paragraphs(chunks: list[Any]) -> list[tuple[str, int]]:
    """Flatten chunks into (paragraph_text, page_number) pairs."""
    paragraphs: list[tuple[str, int]] = []
    for chunk in chunks:
        for paragraph in re.split(r"\n\s*\n", chunk.text or ""):
            stripped = paragraph.strip()
            if stripped:
                paragraphs.append((stripped, chunk.page_number))
    return paragraphs


def _clause_texts(clauses: list[Any]) -> list[str]:
    return [normalize_text(c.extracted_text) for c in clauses]


def _is_clause_covered(paragraph: str, clause_texts: list[str]) -> bool:
    normalized = normalize_text(paragraph)
    return any(clause and (clause in normalized or normalized in clause) for clause in clause_texts)


def _counterpart_exclusions(
    paras_x: list[tuple[str, int]],
    covered_x: list[bool],
    paras_y: list[tuple[str, int]],
    covered_y: list[bool],
) -> set[int]:
    """Indices in *paras_y* to exclude because their best counterpart in X
    is clause-covered in X (prevents duplicating clause changes in
    "Other Changes")."""
    excluded: set[int] = set()
    for i, (text_x, _) in enumerate(paras_x):
        if not covered_x[i]:
            continue
        best_j: int | None = None
        best_sim = 0.0
        for j, (text_y, _) in enumerate(paras_y):
            if covered_y[j]:
                continue
            sim = _similarity(text_x, text_y)
            if sim > best_sim:
                best_j, best_sim = j, sim
        if best_j is not None and best_sim >= _COUNTERPART_THRESHOLD:
            excluded.add(best_j)
    return excluded


def diff_other_changes(
    chunks_a: list[Any], chunks_b: list[Any], clauses_a: list[Any], clauses_b: list[Any]
) -> list[dict[str, Any]]:
    """Paragraph-level diff of content outside the tracked clause types.

    Clause-covered paragraphs (and their closest counterparts on the other
    side) are excluded — those changes are already reported in the
    clause-scoped section.
    """
    paras_a = _paragraphs(chunks_a)
    paras_b = _paragraphs(chunks_b)
    covered_a = [_is_clause_covered(text, _clause_texts(clauses_a)) for text, _ in paras_a]
    covered_b = [_is_clause_covered(text, _clause_texts(clauses_b)) for text, _ in paras_b]
    # skip_a: indices in paras_a whose counterpart in B is clause-covered in B
    # (and symmetric for skip_b).
    skip_a = _counterpart_exclusions(paras_b, covered_b, paras_a, covered_a)
    skip_b = _counterpart_exclusions(paras_a, covered_a, paras_b, covered_b)

    kept_a = [i for i in range(len(paras_a)) if not covered_a[i] and i not in skip_a]
    kept_b = [j for j in range(len(paras_b)) if not covered_b[j] and j not in skip_b]

    norm_a = [normalize_text(paras_a[i][0]) for i in kept_a]
    norm_b = [normalize_text(paras_b[j][0]) for j in kept_b]
    matcher = SequenceMatcher(a=norm_a, b=norm_b, autojunk=False)

    def _removed(i: int) -> dict[str, Any]:
        text, page = paras_a[kept_a[i]]
        return {
            "status": "removed",
            "text_a": text,
            "text_b": None,
            "word_diff": None,
            "page_a": page,
            "page_b": None,
        }

    def _added(j: int) -> dict[str, Any]:
        text, page = paras_b[kept_b[j]]
        return {
            "status": "added",
            "text_a": None,
            "text_b": text,
            "word_diff": None,
            "page_a": None,
            "page_b": page,
        }

    def _modified(i: int, j: int) -> dict[str, Any]:
        text_a, page_a = paras_a[kept_a[i]]
        text_b, page_b = paras_b[kept_b[j]]
        return {
            "status": "modified",
            "text_a": text_a,
            "text_b": text_b,
            "word_diff": word_diff(text_a, text_b),
            "page_a": page_a,
            "page_b": page_b,
        }

    entries: list[dict[str, Any]] = []
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            continue
        if op == "delete":
            entries.extend(_removed(i) for i in range(i1, i2))
        elif op == "insert":
            entries.extend(_added(j) for j in range(j1, j2))
        else:  # replace — pair up by similarity, leftovers stay added/removed
            block_a = list(range(i1, i2))
            block_b = list(range(j1, j2))
            # _greedy_pair works on the block's texts; translate its
            # block-local indices back to paragraph indices.
            local_pairs = _greedy_pair(
                [norm_a[i] for i in block_a],
                [norm_b[j] for j in block_b],
            )
            pairs = [(block_a[pi], block_b[pj]) for pi, pj in local_pairs]
            paired_a = {i for i, _ in pairs}
            paired_b = {j for _, j in pairs}
            for i, j in pairs:
                if _similarity(norm_a[i], norm_b[j]) >= _PARAGRAPH_PAIR_THRESHOLD:
                    entries.append(_modified(i, j))
                else:
                    entries.append(_removed(i))
                    entries.append(_added(j))
            entries.extend(_removed(i) for i in block_a if i not in paired_a)
            entries.extend(_added(j) for j in block_b if j not in paired_b)
        if len(entries) >= _MAX_OTHER_CHANGES:
            break

    return entries[:_MAX_OTHER_CHANGES]
