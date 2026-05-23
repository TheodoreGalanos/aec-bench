# ABOUTME: Integration tests for run-local normalisation pass.
# ABOUTME: Verifies canonical_refs in task.toml drive output cleanup before verifier.

import json
from pathlib import Path

from aec_bench.cli.commands.run_local import (
    apply_normalisation,
    load_canonical_refs,
)


def test_load_canonical_refs_from_task_toml(tmp_path: Path) -> None:
    task_toml = tmp_path / "task.toml"
    task_toml.write_text(
        """
[metadata]
difficulty = "hard"

[canonical_refs]
project_id = "EST11221"
base_name = "RAAF Base East Sale"
"""
    )
    refs = load_canonical_refs(task_toml)
    assert len(refs.refs) == 2
    by_name = {r.name: r.value for r in refs.refs}
    assert by_name["project_id"] == "EST11221"


def test_load_canonical_refs_returns_empty_when_table_absent(tmp_path: Path) -> None:
    task_toml = tmp_path / "task.toml"
    task_toml.write_text(
        """
[metadata]
difficulty = "hard"
"""
    )
    refs = load_canonical_refs(task_toml)
    assert refs.refs == ()


def test_load_canonical_refs_returns_empty_when_file_missing(tmp_path: Path) -> None:
    refs = load_canonical_refs(tmp_path / "nonexistent.toml")
    assert refs.refs == ()


def test_apply_normalisation_fixes_output_and_writes_report(tmp_path: Path) -> None:
    output_md = tmp_path / "output.md"
    output_md.write_text("Per cost estimate EST112211 Revision D, scope set.")
    report_path = tmp_path / "normalisation_report.json"

    from aec_bench.contracts.canonical_refs import CanonicalRef, CanonicalRefSet

    refs = CanonicalRefSet(refs=(CanonicalRef(name="project_id", value="EST11221"),))
    result = apply_normalisation(output_md, refs, report_path)

    assert "EST112211" not in output_md.read_text()
    assert "EST11221" in output_md.read_text()
    report = json.loads(report_path.read_text())
    assert report["substitutions_count"] == 1
    assert len(report["audit_log"]) == 1
    assert report["audit_log"][0]["matched_text"] == "EST112211"
    assert result.substitutions_count == 1


def test_apply_normalisation_skips_when_refs_empty(tmp_path: Path) -> None:
    """No canonical refs -> no substitutions, no report file written, output unchanged."""
    output_md = tmp_path / "output.md"
    original = "Per cost estimate EST112211, scope set."
    output_md.write_text(original)
    report_path = tmp_path / "normalisation_report.json"

    from aec_bench.contracts.canonical_refs import CanonicalRefSet

    result = apply_normalisation(output_md, CanonicalRefSet(), report_path)
    assert output_md.read_text() == original
    assert not report_path.exists()
    assert result.substitutions_count == 0


def test_apply_normalisation_skips_report_when_no_substitutions(tmp_path: Path) -> None:
    """Refs declared but no near-misses -> no report file written."""
    output_md = tmp_path / "output.md"
    original = "Project EST11221 - no near-misses anywhere."
    output_md.write_text(original)
    report_path = tmp_path / "normalisation_report.json"

    from aec_bench.contracts.canonical_refs import CanonicalRef, CanonicalRefSet

    refs = CanonicalRefSet(refs=(CanonicalRef(name="project_id", value="EST11221"),))
    result = apply_normalisation(output_md, refs, report_path)
    assert output_md.read_text() == original
    assert not report_path.exists()
    assert result.substitutions_count == 0
