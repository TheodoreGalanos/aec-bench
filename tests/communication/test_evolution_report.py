# ABOUTME: Tests the communication-owned evolution report writer.
# ABOUTME: Proves the CLI callback writes one self-contained report from a workspace.

from pathlib import Path

from aec_bench.communication.evolution_report import write_evolution_report


def test_write_evolution_report_writes_the_workspace_report(tmp_path: Path) -> None:
    (tmp_path / "manifest.yaml").write_text(
        "schema_version: 1\nname: report-demo\nagent_adapter: rlm\nevolvable_layers: [prompts, skills]\n",
        encoding="utf-8",
    )
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "system.md").write_text("Report prompt\n", encoding="utf-8")

    report_path = write_evolution_report(tmp_path)

    assert report_path == tmp_path / "evolution-report.html"
    assert report_path.is_file()
    assert "report-demo" in report_path.read_text(encoding="utf-8")
