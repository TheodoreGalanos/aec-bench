# ABOUTME: Tests for the local evolution solve backend.
# ABOUTME: Covers workspace setup, snapshot injection, and artifact collection.

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aec_bench.contracts.evolution import SkillEntry, WorkspaceSnapshot

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_snapshot(
    prompt: str = "You are an engineering agent.",
    skills: list[SkillEntry] | None = None,
    version: str = "evo-0",
) -> WorkspaceSnapshot:
    return WorkspaceSnapshot(
        system_prompt=prompt,
        skills=skills or [],
        workspace_version=version,
    )


def _make_skill(name: str = "cable-sizing", body: str = "I_z >= I_b") -> SkillEntry:
    return SkillEntry(
        name=name,
        description="Cable sizing reference",
        discipline="electrical",
        body=body,
    )


def _write_agent_result(workspace_dir: Path, status: str = "ok") -> None:
    agent_result = {
        "status": status,
        "model": "claude-sonnet-4-6",
        "input_tokens": 1200,
        "output_tokens": 340,
        "turns_used": 7,
        "max_turns": 20,
    }
    (workspace_dir / "agent_result.json").write_text(json.dumps(agent_result))


def _write_verifier_artifacts(
    workspace_dir: Path,
    reward: float = 0.85,
) -> None:
    logs_dir = workspace_dir / "logs" / "verifier"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "reward.json").write_text(json.dumps({"reward": reward}))
    details = {
        "voltage_drop": 0.9,
        "conductor_size": 0.8,
    }
    (logs_dir / "details.json").write_text(json.dumps(details))


# ---------------------------------------------------------------------------
# TestInjectSnapshotIntoWorkspace
# ---------------------------------------------------------------------------


class TestInjectSnapshotIntoWorkspace:
    def test_writes_system_prompt_md(self, tmp_path: Path) -> None:
        from aec_bench.evolution.backends.local import inject_snapshot_into_workspace

        skill = _make_skill(name="voltage-formulas", body="V = I * R")
        snapshot = _make_snapshot(
            prompt="You are an electrical engineer.",
            skills=[skill],
        )

        inject_snapshot_into_workspace(snapshot, tmp_path)

        prompt_file = tmp_path / "system_prompt.md"
        assert prompt_file.exists()
        content = prompt_file.read_text()
        assert "You are an electrical engineer." in content
        assert "voltage-formulas" in content
        assert "V = I * R" in content

    def test_overwrites_existing_prompt(self, tmp_path: Path) -> None:
        from aec_bench.evolution.backends.local import inject_snapshot_into_workspace

        prompt_file = tmp_path / "system_prompt.md"
        prompt_file.write_text("old content that should be replaced")

        snapshot = _make_snapshot(prompt="New system prompt.")
        inject_snapshot_into_workspace(snapshot, tmp_path)

        content = prompt_file.read_text()
        assert "New system prompt." in content
        assert "old content" not in content


# ---------------------------------------------------------------------------
# TestCollectLocalTrialRecord
# ---------------------------------------------------------------------------


class TestCollectLocalTrialRecord:
    def test_builds_record_from_artifacts(self, tmp_path: Path) -> None:
        from aec_bench.evolution.backends.local import collect_local_trial_record

        _write_agent_result(tmp_path)
        _write_verifier_artifacts(tmp_path, reward=0.85)
        # Write a system_prompt.md for provenance
        (tmp_path / "system_prompt.md").write_text("You are an agent.")

        record = collect_local_trial_record(
            workspace_dir=tmp_path,
            trial_id="trial-001",
            experiment_id="exp-001",
            task_id="electrical/voltage-drop",
            model="claude-sonnet-4-6",
            instruction="Calculate the voltage drop for the given circuit.",
        )

        assert record.trial_id == "trial-001"
        assert record.experiment_id == "exp-001"
        assert record.task.task_id == "electrical/voltage-drop"
        assert record.task.task_revision == "local"
        assert record.agent.model == "claude-sonnet-4-6"
        assert record.agent.adapter == "rlm"
        assert record.evaluation.reward == pytest.approx(0.85)
        assert record.evaluation.validity.verifier_completed is True
        assert record.evaluation.breakdown is not None
        assert "voltage_drop" in record.evaluation.breakdown
        assert record.outputs.agent_result is not None
        assert record.outputs.agent_result["status"] == "ok"
        assert record.cost is not None
        assert record.cost.tokens_in == 1200
        assert record.cost.tokens_out == 340

    def test_reads_advisor_stats_into_cost_record(self, tmp_path: Path) -> None:
        """Advisor fields in agent_result.json populate TrialRecord.cost."""
        from aec_bench.evolution.backends.local import collect_local_trial_record

        agent_result = {
            "status": "ok",
            "model": "gpt-4.1-mini",
            "input_tokens": 500,
            "output_tokens": 200,
            "advisor_calls": 2,
            "advisor_input_tokens": 800,
            "advisor_output_tokens": 300,
        }
        (tmp_path / "agent_result.json").write_text(json.dumps(agent_result))
        _write_verifier_artifacts(tmp_path, reward=0.9)

        record = collect_local_trial_record(
            workspace_dir=tmp_path,
            trial_id="trial-adv",
            experiment_id="exp-001",
            task_id="electrical/voltage-drop",
            model="gpt-4.1-mini",
            instruction="Calculate the voltage drop.",
        )

        assert record.cost is not None
        assert record.cost.advisor_calls == 2
        assert record.cost.advisor_input_tokens == 800
        assert record.cost.advisor_output_tokens == 300

    def test_handles_missing_verifier(self, tmp_path: Path) -> None:
        from aec_bench.evolution.backends.local import collect_local_trial_record

        _write_agent_result(tmp_path, status="ok")
        # No verifier output written

        record = collect_local_trial_record(
            workspace_dir=tmp_path,
            trial_id="trial-002",
            experiment_id="exp-001",
            task_id="electrical/cable-sizing",
            model="claude-sonnet-4-6",
            instruction="Select the correct cable size for the load.",
        )

        assert record.evaluation.reward == pytest.approx(0.0)
        assert record.evaluation.validity.verifier_completed is False
        assert record.evaluation.validity.output_parseable is True


# ---------------------------------------------------------------------------
# TestExtractTaskId
# ---------------------------------------------------------------------------


class TestExtractTaskId:
    def test_extracts_from_tasks_path(self, tmp_path: Path) -> None:
        task_dir = tmp_path / "projects" / "aec-bench" / "tasks" / "electrical" / "voltage-drop" / "instance"
        task_dir.mkdir(parents=True)
        from aec_bench.evolution.backends.local import _extract_task_id

        result = _extract_task_id(task_dir)
        assert result == "electrical/voltage-drop/instance"

    def test_fallback_for_no_tasks_dir(self, tmp_path: Path) -> None:
        task_dir = tmp_path / "some" / "random" / "path"
        task_dir.mkdir(parents=True)
        from aec_bench.evolution.backends.local import _extract_task_id

        result = _extract_task_id(task_dir)
        assert "path" in result


# ---------------------------------------------------------------------------
# TestMakeLocalSolveFn
# ---------------------------------------------------------------------------


class TestInjectWorkspaceConfig:
    """tool_loop.toml from the evolution workspace root should be copied into per-trial workspaces."""

    def test_copy_tool_loop_toml_copies_when_present(self, tmp_path: Path) -> None:
        from aec_bench.evolution.backends.local import copy_adapter_config

        evolution_root = tmp_path / "evo"
        evolution_root.mkdir()
        (evolution_root / "tool_loop.toml").write_text('[advisor]\nmodel = "claude-sonnet-4-6"\nmax_uses = 5\n')

        trial_workspace = tmp_path / "trial"
        trial_workspace.mkdir()

        copy_adapter_config(evolution_root, trial_workspace)

        copied = trial_workspace / "tool_loop.toml"
        assert copied.exists()
        assert "claude-sonnet-4-6" in copied.read_text()

    def test_copy_tool_loop_toml_noop_when_absent(self, tmp_path: Path) -> None:
        """When no tool_loop.toml is at the workspace root, nothing is copied."""
        from aec_bench.evolution.backends.local import copy_adapter_config

        evolution_root = tmp_path / "evo"
        evolution_root.mkdir()

        trial_workspace = tmp_path / "trial"
        trial_workspace.mkdir()

        copy_adapter_config(evolution_root, trial_workspace)

        assert not (trial_workspace / "tool_loop.toml").exists()


class TestMakeLocalSolveFn:
    def test_returns_callable(self) -> None:
        from aec_bench.evolution.backends.local import make_local_solve_fn

        solve_fn = make_local_solve_fn(
            task_dirs=[],
            model="claude-haiku-4-5-20251001",
            experiment_id="evo-test",
        )
        assert callable(solve_fn)

    def test_returns_empty_for_no_tasks(self) -> None:
        from aec_bench.contracts.evolution import WorkspaceSnapshot
        from aec_bench.evolution.backends.local import make_local_solve_fn

        snapshot = WorkspaceSnapshot(
            system_prompt="Test prompt.",
            workspace_version="evo-0",
        )
        solve_fn = make_local_solve_fn(
            task_dirs=[],
            model="claude-haiku-4-5-20251001",
            experiment_id="evo-test",
        )
        result = solve_fn(snapshot, batch_size=5)
        assert result == []
