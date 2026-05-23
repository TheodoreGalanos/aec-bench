# ABOUTME: Integration tests for aec-bench remediate — wires proposer/verifier/loop end-to-end.
# ABOUTME: Uses stubs for the LLM client and a fake verify.py to avoid network calls.

import json
from pathlib import Path

from aec_bench.cli.commands.remediate import run_remediate


def _setup_task_and_run(tmp_path: Path) -> tuple[Path, Path]:
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    (task_dir / "documents").mkdir()
    (task_dir / "report_template.toml").write_text("[[sections]]\nid = 'x'\ntitle = 'X'\n")
    (task_dir / "tests").mkdir()
    (task_dir / "tests" / "verify.py").write_text(
        """
import json
import sys
from pathlib import Path
WORKSPACE = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/workspace")
REWARD = WORKSPACE / "logs" / "verifier" / "reward.json"
DETAILS = WORKSPACE / "logs" / "verifier" / "details.json"
REWARD.parent.mkdir(parents=True, exist_ok=True)
text = (WORKSPACE / "output.md").read_text()
reward = 0.9 if "FIXED" in text else 0.5
REWARD.write_text(json.dumps({"reward": reward}))
DETAILS.write_text(json.dumps({
    "reward": reward,
    "d": {
        "score": 5,
        "max_score": 10,
        "unsatisfied": ["c"] if reward < 0.7 else [],
        "evidence": "e",
    },
}))
"""
    )

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "output.md").write_text("# D\n\nInitial body that needs patching.")
    (run_dir / "logs" / "verifier").mkdir(parents=True)
    (run_dir / "logs" / "verifier" / "details.json").write_text(
        json.dumps(
            {
                "reward": 0.5,
                "d": {"score": 5, "max_score": 10, "unsatisfied": ["c"], "evidence": "e"},
            }
        )
    )
    return task_dir, run_dir


def test_remediate_command_writes_report_and_hitl(tmp_path: Path, monkeypatch) -> None:
    task_dir, run_dir = _setup_task_and_run(tmp_path)

    # Stub the proposer to always return an APPLY patch that inserts "FIXED"
    def stub_propose(*, section_id, section_excerpt, criterion, evidence, client, model):
        from aec_bench.contracts.remediation import Patch, PatchProposal, PatchStatus

        return PatchProposal(
            patch=Patch(
                section_id="d",
                locator_phrase="Initial body that needs patching",
                replacement="FIXED: body",
                occurrence=1,
            ),
            criterion=criterion,
            evidence=evidence,
            rationale="Test patch",
            confidence="high",
            status=PatchStatus.APPLY,
        )

    monkeypatch.setattr("aec_bench.cli.commands.remediate.propose_patch", stub_propose)

    # Stub the LLM client factory to avoid Bedrock init
    class _NullClient:
        def generate(self, **_kwargs):
            raise AssertionError("should not be called (propose_patch is stubbed)")

    monkeypatch.setattr(
        "aec_bench.cli.commands.remediate._build_client",
        lambda _model: _NullClient(),
    )

    run_remediate(
        run_dir=run_dir,
        task_dir=task_dir,
        model="stub-model",
        max_iterations=3,
        plateau_threshold=0.02,
        target_reward=None,
        interactive=False,
        output_dir=None,
    )

    rem_dir = run_dir / "remediation"
    assert (rem_dir / "remediation_report.json").exists()
    assert (rem_dir / "hitl_items.json").exists()
    assert (rem_dir / "output.final.md").exists()
    final_text = (rem_dir / "output.final.md").read_text()
    assert "FIXED" in final_text

    report = json.loads((rem_dir / "remediation_report.json").read_text())
    assert report["final_reward"] == 0.9
    assert report["total_patches_applied"] >= 1


def test_remediate_refuses_when_task_config_disables(tmp_path: Path, monkeypatch) -> None:
    task_dir, run_dir = _setup_task_and_run(tmp_path)
    task_dir_task_toml = task_dir / "task.toml"
    existing = task_dir_task_toml.read_text() if task_dir_task_toml.exists() else ""
    task_dir_task_toml.write_text(existing + "\n[remediation]\nenabled = false\n")

    monkeypatch.setattr(
        "aec_bench.cli.commands.remediate._build_client",
        lambda _model: None,
    )

    result = run_remediate(
        run_dir=run_dir,
        task_dir=task_dir,
        model="x",
        max_iterations=3,
        plateau_threshold=0.02,
        target_reward=None,
        interactive=False,
        output_dir=None,
        force=False,
    )
    assert result is None

    rem_dir = run_dir / "remediation"
    assert not (rem_dir / "remediation_report.json").exists()


def test_remediate_force_overrides_task_disable(tmp_path: Path, monkeypatch) -> None:
    """--force bypasses the task-config disable."""
    task_dir, run_dir = _setup_task_and_run(tmp_path)
    task_dir_task_toml = task_dir / "task.toml"
    existing = task_dir_task_toml.read_text() if task_dir_task_toml.exists() else ""
    task_dir_task_toml.write_text(existing + "\n[remediation]\nenabled = false\n")

    def stub_propose(*, section_id, section_excerpt=None, criterion, evidence, client, model, **_):
        from aec_bench.contracts.remediation import Patch, PatchProposal, PatchStatus

        return PatchProposal(
            patch=Patch(
                section_id="d",
                locator_phrase="Initial body that needs patching",
                replacement="FIXED: body",
                occurrence=1,
            ),
            criterion=criterion,
            evidence=evidence,
            rationale="r",
            confidence="high",
            status=PatchStatus.APPLY,
        )

    monkeypatch.setattr("aec_bench.cli.commands.remediate.propose_patch", stub_propose)
    monkeypatch.setattr(
        "aec_bench.cli.commands.remediate._build_client",
        lambda _model: None,
    )

    result = run_remediate(
        run_dir=run_dir,
        task_dir=task_dir,
        model="x",
        max_iterations=3,
        plateau_threshold=0.02,
        target_reward=None,
        interactive=False,
        output_dir=None,
        force=True,
    )
    assert result is not None  # force bypasses the disable
    assert (run_dir / "remediation" / "remediation_report.json").exists()


def test_remediate_applies_task_level_iterations_override(tmp_path: Path, monkeypatch) -> None:
    """When CLI max_iterations is at default (3) and task declares 1, task wins."""
    task_dir, run_dir = _setup_task_and_run(tmp_path)
    task_dir_task_toml = task_dir / "task.toml"
    existing = task_dir_task_toml.read_text() if task_dir_task_toml.exists() else ""
    task_dir_task_toml.write_text(existing + "\n[remediation]\nmax_iterations = 1\n")

    def stub_propose(**kwargs):
        from aec_bench.contracts.remediation import Patch, PatchProposal, PatchStatus

        return PatchProposal(
            patch=Patch(
                section_id="d",
                locator_phrase="Initial",
                replacement="FIXED",
                occurrence=1,
            ),
            criterion=kwargs["criterion"],
            evidence=kwargs["evidence"],
            rationale="r",
            confidence="high",
            status=PatchStatus.APPLY,
        )

    monkeypatch.setattr("aec_bench.cli.commands.remediate.propose_patch", stub_propose)
    monkeypatch.setattr(
        "aec_bench.cli.commands.remediate._build_client",
        lambda _model: None,
    )

    result = run_remediate(
        run_dir=run_dir,
        task_dir=task_dir,
        model="x",
        max_iterations=3,
        plateau_threshold=0.02,
        target_reward=None,
        interactive=False,
        output_dir=None,
        force=False,
    )
    assert result is not None
    assert len(result.iterations) <= 1  # task override capped at 1


def test_remediate_preserves_canonical_section_ids(tmp_path: Path, monkeypatch) -> None:
    """sections.final.json keys must match canonical IDs from sections.json verbatim.

    The remediation loop uses heading-derived IDs internally (e.g. "assumptions"
    from "# Assumptions"), but the proposer's sections.json owns the canonical IDs
    (e.g. "aie"). The write step must translate back so downstream consumers
    (export overlay) merge the delta under the correct key.
    """
    task_dir, run_dir = _setup_task_and_run(tmp_path)
    canonical = {"aie": {"content": "# Assumptions\n\nInitial body that needs patching."}}
    (run_dir / "sections.json").write_text(json.dumps(canonical))
    (run_dir / "output.md").write_text(canonical["aie"]["content"])

    def stub_propose(*, section_id, section_excerpt, criterion, evidence, client, model, **_):
        from aec_bench.contracts.remediation import Patch, PatchProposal, PatchStatus

        return PatchProposal(
            patch=Patch(
                section_id="assumptions",  # heading-derived (loop's internal id)
                locator_phrase="Initial body that needs patching",
                replacement="FIXED: body",
                occurrence=1,
            ),
            criterion=criterion,
            evidence=evidence,
            rationale="r",
            confidence="high",
            status=PatchStatus.APPLY,
        )

    monkeypatch.setattr("aec_bench.cli.commands.remediate.propose_patch", stub_propose)
    monkeypatch.setattr(
        "aec_bench.cli.commands.remediate._build_client",
        lambda _model: None,
    )

    run_remediate(
        run_dir=run_dir,
        task_dir=task_dir,
        model="x",
        max_iterations=3,
        plateau_threshold=0.02,
        target_reward=None,
        interactive=False,
        output_dir=None,
    )

    sections_final = json.loads((run_dir / "remediation" / "sections.final.json").read_text())
    extra = set(sections_final) - set(canonical)
    assert not extra, f"sections.final.json has non-canonical keys: {extra}"
    assert "aie" in sections_final
    assert "FIXED" in sections_final["aie"]["content"]
