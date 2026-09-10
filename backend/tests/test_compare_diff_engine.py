"""Phase 6 diff engine unit tests — alignment, classification, word diff.

Pure-function tests (no DB): the hand-annotated classification acceptance
from 13-roadmap-build-order.md Phase 6.
"""
from types import SimpleNamespace

from app.models.models import ClauseType
from app.pipelines.compare.diff_engine import (
    align_clauses,
    diff_other_changes,
    normalize_text,
    word_diff,
)


def clause(clause_type: str, text: str, page: int = 1) -> SimpleNamespace:
    return SimpleNamespace(
        clause_type=ClauseType(clause_type),
        extracted_text=text,
        page_number=page,
        summary=None,
        confidence_score=None,
    )


def chunk(text: str, page: int = 1) -> SimpleNamespace:
    return SimpleNamespace(text=text, page_number=page)


def test_word_diff_segments_replace_and_keep():
    diff = word_diff(
        "The Client shall pay $50,000 within 30 days",
        "The Client shall pay $75,000 within 45 days",
    )
    assert diff[0]["op"] == "equal"
    replaces = [seg for seg in diff if seg["op"] == "replace"]
    assert len(replaces) == 2
    assert replaces[0]["text_a"] == "$50,000"
    assert replaces[0]["text_b"] == "$75,000"
    assert replaces[1]["text_a"] == "30"
    assert replaces[1]["text_b"] == "45"


def test_word_diff_insert_and_delete():
    diff = word_diff("Alpha Beta Delta", "Alpha Beta Gamma Delta")
    ops = [seg["op"] for seg in diff]
    assert ops == ["equal", "insert", "equal"]
    assert diff[1]["text_b"] == "Gamma"
    assert diff[1]["text_a"] is None

    diff = word_diff("Alpha Beta Delta", "Alpha Delta")
    ops = [seg["op"] for seg in diff]
    assert ops == ["equal", "delete", "equal"]
    assert diff[1]["text_a"] == "Beta"


def test_align_clauses_added_removed_modified_unchanged():
    clauses_a = [
        clause("payment", "The Client shall pay $50,000 within 30 days."),
        clause("confidentiality", "Each party shall keep information confidential."),
        clause("termination", "Either party may terminate on 30 days notice."),
    ]
    clauses_b = [
        clause("payment", "The Client shall pay $75,000 within 45 days."),
        clause("confidentiality", "Each party shall keep information confidential."),
        clause("arbitration", "Disputes shall be resolved by binding arbitration."),
    ]

    entries = align_clauses(clauses_a, clauses_b)
    by_type = {entry["clause_type"]: entry for entry in entries}

    assert by_type["payment"]["status"] == "modified"
    assert by_type["payment"]["word_diff"]  # word-level diff attached
    assert by_type["payment"]["page_a"] == 1
    assert by_type["payment"]["page_b"] == 1

    assert by_type["confidentiality"]["status"] == "unchanged"
    assert by_type["confidentiality"]["word_diff"] == []

    assert by_type["termination"]["status"] == "removed"
    assert by_type["termination"]["text_a"]
    assert by_type["termination"]["text_b"] is None

    assert by_type["arbitration"]["status"] == "added"
    assert by_type["arbitration"]["text_b"]
    assert by_type["arbitration"]["text_a"] is None


def test_align_clauses_whitespace_only_difference_is_unchanged():
    clauses_a = [clause("payment", "The Client shall pay\nthe fee within 30 days.")]
    clauses_b = [clause("payment", "The Client shall pay the fee within 30 days.")]
    entries = align_clauses(clauses_a, clauses_b)
    assert entries[0]["status"] == "unchanged"


def test_align_clauses_multiple_instances_pair_by_similarity():
    clauses_a = [
        clause("payment", "The Client shall pay the license fee of $10,000."),
        clause("payment", "The Client shall pay travel expenses of $500."),
    ]
    clauses_b = [
        clause("payment", "The Client shall pay travel expenses of $750."),
        clause("payment", "The Client shall pay the license fee of $12,000."),
    ]
    entries = align_clauses(clauses_a, clauses_b)
    assert len(entries) == 2
    assert all(entry["status"] == "modified" for entry in entries)
    # License pairs with license, travel with travel.
    by_a_text = {entry["text_a"]: entry["text_b"] for entry in entries}
    assert (
        "license fee of $12,000."
        in by_a_text["The Client shall pay the license fee of $10,000."]
    )
    assert (
        "travel expenses of $750."
        in by_a_text["The Client shall pay travel expenses of $500."]
    )


def test_align_clauses_extra_instance_classified():
    clauses_a = [clause("payment", "The Client shall pay the fee.")]
    clauses_b = [
        clause("payment", "The Client shall pay the fee."),
        clause("payment", "The Client shall also pay late charges of 5%."),
    ]
    entries = align_clauses(clauses_a, clauses_b)
    statuses = sorted(entry["status"] for entry in entries)
    assert statuses == ["added", "unchanged"]


def test_diff_other_changes_excludes_clause_content_and_identical_paragraphs():
    chunks_a = [
        chunk(
            "ACME AGREEMENT\n\n"
            "This Agreement is entered into between Acme Corp and Beta LLC.\n\n"
            "Either party may terminate with thirty days notice.\n\n"
            "Appendix I attached."
        )
    ]
    clauses_a = [clause("termination", "Either party may terminate with thirty days notice.")]
    chunks_b = [
        chunk(
            "ACME AGREEMENT (REVISED)\n\n"
            "This Agreement is entered into between Acme Corp and Beta LLC.\n\n"
            "Either party may terminate with sixty days notice.\n\n"
            "Signature block follows."
        )
    ]
    # Simulates a missed clause detection on side B — the counterpart
    # exclusion must still hide the near-identical paragraph.
    clauses_b = []

    entries = diff_other_changes(chunks_a, chunks_b, clauses_a, clauses_b)

    # Title modified; party sentence identical (skipped); termination
    # paragraphs clause-excluded; appendix removed; signature added.
    assert len(entries) == 3
    assert entries[0]["status"] == "modified"
    assert "REVISED" in entries[0]["text_b"]
    assert entries[1]["status"] == "removed"
    assert entries[1]["text_a"] == "Appendix I attached."
    assert entries[2]["status"] == "added"
    assert entries[2]["text_b"] == "Signature block follows."


def test_diff_other_changes_empty_when_identical():
    text = "Title\n\nBody paragraph one.\n\nBody paragraph two."
    chunks = [chunk(text)]
    entries = diff_other_changes(chunks, [chunk(text)], [], [])
    assert entries == []


def test_normalize_text_collapses_whitespace():
    assert normalize_text("  a \n\n b \t c  ") == "a b c"
