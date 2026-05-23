# ABOUTME: Tests for triage annotation persistence in the ledger package.
# ABOUTME: Covers save/load/delete round-trips and edge cases.

from __future__ import annotations

from pathlib import Path

from aec_bench.ledger.annotations import (
    TriageAnnotation,
    delete_annotation,
    load_annotations,
    save_annotation,
)


def test_create_produces_correct_verdict_and_timestamp() -> None:
    """TriageAnnotation.create() sets verdict and a non-empty timestamp."""
    ann = TriageAnnotation.create(verdict="pass", notes="looks good")
    assert ann.verdict == "pass"
    assert ann.notes == "looks good"
    assert ann.timestamp != ""
    # Timestamp should look like an ISO-ish UTC string
    assert ann.timestamp.endswith("Z")


def test_create_default_notes_empty() -> None:
    """TriageAnnotation.create() defaults notes to empty string."""
    ann = TriageAnnotation.create(verdict="fail")
    assert ann.verdict == "fail"
    assert ann.notes == ""
    assert ann.timestamp != ""


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    """save_annotation + load_annotations produces the same data."""
    ann = TriageAnnotation.create(verdict="pass", notes="all clear")
    save_annotation(tmp_path, "trial-001", ann)

    loaded = load_annotations(tmp_path)
    assert "trial-001" in loaded
    result = loaded["trial-001"]
    assert result.verdict == ann.verdict
    assert result.notes == ann.notes
    assert result.timestamp == ann.timestamp


def test_save_multiple_and_load(tmp_path: Path) -> None:
    """Multiple annotations are all loaded correctly."""
    ann_a = TriageAnnotation.create(verdict="pass")
    ann_b = TriageAnnotation.create(verdict="fail", notes="wrong answer")
    save_annotation(tmp_path, "trial-a", ann_a)
    save_annotation(tmp_path, "trial-b", ann_b)

    loaded = load_annotations(tmp_path)
    assert len(loaded) == 2
    assert loaded["trial-a"].verdict == "pass"
    assert loaded["trial-b"].verdict == "fail"
    assert loaded["trial-b"].notes == "wrong answer"


def test_load_annotations_empty_directory(tmp_path: Path) -> None:
    """load_annotations returns empty dict when _annotations/ dir exists but is empty."""
    (tmp_path / "_annotations").mkdir()
    loaded = load_annotations(tmp_path)
    assert loaded == {}


def test_load_annotations_missing_directory(tmp_path: Path) -> None:
    """load_annotations returns empty dict when _annotations/ dir does not exist."""
    loaded = load_annotations(tmp_path)
    assert loaded == {}


def test_delete_annotation_removes_file(tmp_path: Path) -> None:
    """delete_annotation removes the annotation file."""
    ann = TriageAnnotation.create(verdict="defer", notes="need review")
    save_annotation(tmp_path, "trial-x", ann)

    # Confirm it exists
    assert (tmp_path / "_annotations" / "trial-x.json").exists()

    delete_annotation(tmp_path, "trial-x")

    # File should be gone
    assert not (tmp_path / "_annotations" / "trial-x.json").exists()

    # Loading should return empty
    loaded = load_annotations(tmp_path)
    assert "trial-x" not in loaded


def test_delete_annotation_missing_file_no_error(tmp_path: Path) -> None:
    """delete_annotation on a missing file is a no-op (no error raised)."""
    # No _annotations/ dir at all — should not raise
    delete_annotation(tmp_path, "nonexistent")

    # With an empty _annotations/ dir — should also not raise
    (tmp_path / "_annotations").mkdir()
    delete_annotation(tmp_path, "nonexistent")
