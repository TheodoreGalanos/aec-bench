# ABOUTME: Tests isolated one-attempt execution for ordinary artifact tasks.
# ABOUTME: Proves task privacy, workspace fidelity, parent isolation, and output-path handling.

import json
from pathlib import Path

import pytest

from aec_bench.adapters.base import AdapterRequest, AdapterResult
from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig
from aec_bench.contracts.task_definition import EnvironmentSpec, VerifierSpec
from aec_bench.harness.artifact_tasks import (
    AttemptSelection,
    AttemptSelectionEvidence,
    BestOfSpec,
    LocalTaskRuntime,
    SelectorDecision,
    best_of,
    build_attempt_recipe,
    run_experiment,
    run_trial,
    run_trial_with_verifier_feedback,
    self_select,
    single_attempt,
)
from aec_bench.harness.trial import PlannedTrial
from aec_bench.tasks.instance import resolve_instance_paths
from tests.support.task_factories import make_task_definition


class _WorkspaceAdapter:
    def __init__(self, workspace: Path, requests: list[AdapterRequest]) -> None:
        self._workspace = workspace
        self._requests = requests

    def execute(self, request: AdapterRequest) -> AdapterResult:
        self._requests.append(request)
        assert not (self._workspace / "tests").exists()
        output = self._workspace / "deliverables" / "result.md"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("Complete\n", encoding="utf-8")
        (self._workspace / "deliverables" / "support.json").write_text('{"kept": true}\n', encoding="utf-8")
        stale = self._workspace / "remove-me.txt"
        if stale.exists():
            stale.unlink()
        return AdapterResult(
            adapter_name="direct",
            resolved_model="test-model",
            configuration_record={},
            agent_output=AgentOutput(
                status=AgentOutputStatus.COMPLETED,
                output_path=request.output_path,
                output_format=request.output_format,
            ),
            transcript=[],
            usage_model_calls=1,
            usage_input_tokens=10,
            usage_output_tokens=4,
        )

    def adapter_name(self) -> str:
        return "direct"

    def resolved_model(self) -> str:
        return "test-model"


class _FeedbackAdapter:
    def __init__(self, workspace: Path, requests: list[AdapterRequest]) -> None:
        self._workspace = workspace
        self._requests = requests

    def execute(self, request: AdapterRequest) -> AdapterResult:
        assert not (self._workspace / "tests").exists()
        self._requests.append(request)
        output = self._workspace / "deliverables" / "result.md"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("draft\n" if len(self._requests) == 1 else "repaired\n", encoding="utf-8")
        return AdapterResult(
            adapter_name="direct",
            resolved_model="test-model",
            configuration_record={},
            agent_output=AgentOutput(
                status=AgentOutputStatus.COMPLETED,
                output_path=request.output_path,
                output_format=request.output_format,
            ),
            transcript=[],
            usage_model_calls=1,
            usage_input_tokens=10,
            usage_output_tokens=4,
        )


class _MissingOutputAdapter:
    def execute(self, request: AdapterRequest) -> AdapterResult:
        return AdapterResult(
            adapter_name="direct",
            resolved_model="test-model",
            configuration_record={},
            agent_output=AgentOutput(
                status=AgentOutputStatus.FAILED,
                output_path=request.output_path,
                output_format=request.output_format,
            ),
            transcript=[],
            usage_model_calls=1,
            usage_input_tokens=3,
            usage_output_tokens=1,
        )


def _resolved_task(tmp_path: Path):  # noqa: ANN202
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    (task_dir / "instruction.md").write_text("Write /workspace/deliverables/result.md\n", encoding="utf-8")
    (task_dir / "remove-me.txt").write_text("stale\n", encoding="utf-8")
    environment = task_dir / "environment"
    environment.mkdir()
    (environment / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    tests = task_dir / "tests"
    tests.mkdir()
    (tests / "verify.py").write_text("# private\n", encoding="utf-8")
    task = make_task_definition(
        task_id="test/artifact/one",
        environment=EnvironmentSpec(dockerfile="environment/Dockerfile"),
        verifier=VerifierSpec(
            script="tests/verify.py",
            expected_output_path="/workspace/deliverables/result.md",
            reward_path="logs/verifier/reward.json",
            details_path="logs/verifier/details.json",
        ),
    )
    return resolve_instance_paths(task, task_dir)


def _planned_trial() -> PlannedTrial:
    return PlannedTrial(
        trial_id="trial-1",
        experiment_id="experiment-1",
        task_id="test/artifact/one",
        agent=AgentConfig(name="agent", adapter="direct", model="test-model"),
        compute=ComputeConfig(backend="local", resource_limits={"memory_mb": 512}, timeout_override=17),
        repetition=1,
    )


def test_run_once_preserves_complete_workspace_without_private_verifier(tmp_path: Path) -> None:
    task = _resolved_task(tmp_path)
    requests: list[AdapterRequest] = []
    runtime = LocalTaskRuntime(
        work_root=tmp_path / "attempts",
        adapter_builder=lambda **kwargs: _WorkspaceAdapter(Path(kwargs["workspace"]), requests),
    )

    attempt = runtime.run_once(task, _planned_trial(), attempt_id="attempt-0")

    assert attempt.attempt_id == "attempt-0"
    assert attempt.parent_attempt_id is None
    assert attempt.status is AgentOutputStatus.COMPLETED
    assert (attempt.workspace / "deliverables" / "result.md").read_bytes() == b"Complete\n"
    assert (attempt.workspace / "deliverables" / "support.json").is_file()
    assert not (attempt.workspace / "remove-me.txt").exists()
    assert not (attempt.workspace / "tests").exists()
    assert (task.instance_dir / "remove-me.txt").is_file()
    assert requests[0].output_path == "/workspace/deliverables/result.md"
    assert requests[0].configuration == {}


def test_child_attempt_copies_parent_without_changing_parent(tmp_path: Path) -> None:
    task = _resolved_task(tmp_path)
    runtime = LocalTaskRuntime(
        work_root=tmp_path / "attempts",
        adapter_builder=lambda **kwargs: _WorkspaceAdapter(Path(kwargs["workspace"]), []),
    )
    parent = runtime.run_once(task, _planned_trial(), attempt_id="draft")
    (parent.workspace / "parent-only.txt").write_text("parent\n", encoding="utf-8")

    child = runtime.run_once(task, _planned_trial(), attempt_id="refined", parent=parent, instruction="Improve it")

    assert child.parent_attempt_id == "draft"
    assert child.workspace != parent.workspace
    assert (child.workspace / "parent-only.txt").read_text(encoding="utf-8") == "parent\n"
    assert (parent.workspace / "parent-only.txt").read_text(encoding="utf-8") == "parent\n"
    assert child.request.instruction == "Improve it"


def test_run_once_rejects_parent_from_another_trial(tmp_path: Path) -> None:
    task = _resolved_task(tmp_path)
    runtime = LocalTaskRuntime(
        work_root=tmp_path / "attempts",
        adapter_builder=lambda **kwargs: _WorkspaceAdapter(Path(kwargs["workspace"]), []),
    )
    parent = runtime.run_once(task, _planned_trial(), attempt_id="draft")
    other = PlannedTrial(
        trial_id="trial-2",
        experiment_id="experiment-1",
        task_id=task.task.task_id,
        agent=_planned_trial().agent,
        compute=_planned_trial().compute,
        repetition=1,
    )

    with pytest.raises(ValueError, match="another trial"):
        runtime.run_once(task, other, attempt_id="child", parent=parent)


def test_run_trial_verifies_multi_file_workspace_and_retains_artifacts(tmp_path: Path) -> None:
    task = _resolved_task(tmp_path)
    verifier = task.instance_dir / "tests" / "verify.py"
    verifier.write_text(
        """import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--input")
parser.add_argument("--output")
args = parser.parse_args()
workspace = Path.cwd()
assert Path(args.input).read_text() == "Complete\\n"
assert json.loads((workspace / "deliverables/support.json").read_text()) == {"kept": True}
assert not (workspace / "remove-me.txt").exists()
Path(args.output).write_text(json.dumps({"reward": 1.0}))
(workspace / "logs/verifier/details.json").write_text(json.dumps({"multi_file": True}))
""",
        encoding="utf-8",
    )
    observed_workspaces: list[Path] = []

    def builder(**kwargs):  # noqa: ANN003, ANN202
        workspace = Path(kwargs["workspace"])
        observed_workspaces.append(workspace)
        return _WorkspaceAdapter(workspace, [])

    runtime = LocalTaskRuntime(work_root=tmp_path / "attempts", adapter_builder=builder)

    record = run_trial(runtime=runtime, task=task, trial=_planned_trial(), recipe=single_attempt())

    assert record.evaluation is not None
    assert record.evaluation.reward == 1.0
    assert record.evaluation.breakdown == {"multi_file": True}
    assert all(not workspace.exists() for workspace in observed_workspaces)
    assert record.outputs.raw_output_path is not None
    assert Path(record.outputs.raw_output_path).read_bytes() == b"Complete\n"
    support_path = record.outputs.artifact_path("workspace")
    assert support_path is not None
    assert Path(support_path).is_file()


def test_run_trial_tracks_custom_branching_recipe_and_verifies_only_selection(tmp_path: Path) -> None:
    task = _resolved_task(tmp_path)
    verifier = task.instance_dir / "tests" / "verify.py"
    verifier.write_text(
        """import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--input")
parser.add_argument("--output")
args = parser.parse_args()
counter = Path.cwd() / "verifier-count.txt"
counter.write_text(str(int(counter.read_text()) + 1) if counter.exists() else "1")
Path(args.output).write_text(json.dumps({"reward": 1.0}))
""",
        encoding="utf-8",
    )
    observed_workspaces: list[Path] = []

    def builder(**kwargs):  # noqa: ANN003, ANN202
        workspace = Path(kwargs["workspace"])
        observed_workspaces.append(workspace)
        return _WorkspaceAdapter(workspace, [])

    runtime = LocalTaskRuntime(work_root=tmp_path / "attempts", adapter_builder=builder)

    def draft_then_refine(run_once):  # noqa: ANN001, ANN202
        draft = run_once(attempt_id="draft")
        refined = run_once(attempt_id="refined", parent=draft, instruction="Improve the draft")
        return AttemptSelection.selected(refined, reason="refinement completed")

    record = run_trial(runtime=runtime, task=task, trial=_planned_trial(), recipe=draft_then_refine)

    assert len(observed_workspaces) == 2
    assert all(not workspace.exists() for workspace in observed_workspaces)
    assert record.cost is not None
    assert record.cost.model_calls == 2
    assert record.cost.tokens_in == 20
    assert record.cost.tokens_out == 8
    assert record.evaluation is not None and record.evaluation.reward == 1.0


def test_run_experiment_resolves_planned_trials_to_supplied_tasks(tmp_path: Path) -> None:
    task = _resolved_task(tmp_path)
    verifier = task.instance_dir / "tests" / "verify.py"
    verifier.write_text(
        """import argparse
import json
from pathlib import Path
parser = argparse.ArgumentParser()
parser.add_argument("--input")
parser.add_argument("--output")
args = parser.parse_args()
Path(args.output).write_text(json.dumps({"reward": 1.0}))
""",
        encoding="utf-8",
    )
    first = _planned_trial()
    second = first.__class__(
        trial_id="trial-2",
        experiment_id=first.experiment_id,
        task_id=first.task_id,
        agent=first.agent,
        compute=first.compute,
        repetition=2,
    )
    runtime = LocalTaskRuntime(
        work_root=tmp_path / "attempts",
        adapter_builder=lambda **kwargs: _WorkspaceAdapter(Path(kwargs["workspace"]), []),
    )

    records = run_experiment(
        runtime=runtime,
        tasks=[task],
        trials=[first, second],
        recipe=single_attempt(),
    )

    assert [record.trial_id for record in records] == ["trial-1", "trial-2"]
    assert len({record.input.task_revision for record in records}) == 1
    assert all(record.evaluation is not None and record.evaluation.reward == 1.0 for record in records)


def test_run_experiment_rejects_unresolved_planned_task(tmp_path: Path) -> None:
    runtime = LocalTaskRuntime(work_root=tmp_path / "attempts")

    with pytest.raises(ValueError, match="unresolved task"):
        run_experiment(runtime=runtime, tasks=[], trials=[_planned_trial()], recipe=single_attempt())


def test_best_of_one_has_single_attempt_parity_without_selector_call(tmp_path: Path) -> None:
    task = _resolved_task(tmp_path)
    selector_calls = 0

    def selector(_candidates):  # noqa: ANN001, ANN202
        nonlocal selector_calls
        selector_calls += 1
        return SelectorDecision(selected_index=0, reason="unused", configuration={})

    runtime = LocalTaskRuntime(
        work_root=tmp_path / "attempts",
        adapter_builder=lambda **kwargs: _WorkspaceAdapter(Path(kwargs["workspace"]), []),
    )

    record = run_trial(runtime=runtime, task=task, trial=_planned_trial(), recipe=best_of(k=1, selector=selector))

    assert selector_calls == 0
    assert record.cost is not None and record.cost.model_calls == 1
    assert not record.extension_refs


def test_self_select_uses_first_eligible_candidate(tmp_path: Path) -> None:
    task = _resolved_task(tmp_path)
    runtime = LocalTaskRuntime(
        work_root=tmp_path / "attempts",
        adapter_builder=lambda **kwargs: _WorkspaceAdapter(Path(kwargs["workspace"]), []),
    )

    record = run_trial(runtime=runtime, task=task, trial=_planned_trial(), recipe=best_of(k=2, selector=self_select()))

    extension_ref = next(item for item in record.extension_refs if item.extension_kind == "attempt_selection")
    evidence = AttemptSelectionEvidence.model_validate_json(
        (runtime.artifact_root / extension_ref.artifact.artifact_id).read_text(encoding="utf-8")
    )
    assert evidence.selected_index == 0
    assert evidence.selector.configuration["tie_break"] == "lowest_candidate_index"


def test_best_of_three_selects_once_and_persists_candidate_evidence(tmp_path: Path) -> None:
    task = _resolved_task(tmp_path)
    selector_calls = 0

    def selector(candidates):  # noqa: ANN001, ANN202
        nonlocal selector_calls
        selector_calls += 1
        assert [candidate.attempt_id for candidate in candidates] == ["attempt-0", "attempt-1", "attempt-2"]
        assert all(candidate.output_reference is not None for candidate in candidates)
        return SelectorDecision(
            selected_index=1,
            reason="selected declared candidate",
            configuration={"policy": "test"},
            model_calls=1,
            input_tokens=2,
            output_tokens=1,
        )

    runtime = LocalTaskRuntime(
        work_root=tmp_path / "attempts",
        adapter_builder=lambda **kwargs: _WorkspaceAdapter(Path(kwargs["workspace"]), []),
    )

    record = run_trial(runtime=runtime, task=task, trial=_planned_trial(), recipe=best_of(k=3, selector=selector))

    assert selector_calls == 1
    assert record.cost is not None
    assert record.cost.model_calls == 4
    assert record.cost.tokens_in == 32
    assert record.cost.tokens_out == 13
    extension_ref = next(item for item in record.extension_refs if item.extension_kind == "attempt_selection")
    evidence = AttemptSelectionEvidence.model_validate_json(
        (runtime.artifact_root / extension_ref.artifact.artifact_id).read_text(encoding="utf-8")
    )
    assert evidence.selected_index == 1
    assert evidence.selector.configuration == {"policy": "test"}
    assert [candidate.eligible for candidate in evidence.candidates] == [True, True, True]
    assert all(candidate.selector_visible_output is not None for candidate in evidence.candidates)


def test_best_of_returns_failed_trial_without_verification_when_all_candidates_fail(tmp_path: Path) -> None:
    task = _resolved_task(tmp_path)
    marker = tmp_path / "verifier-called"
    (task.instance_dir / "tests" / "verify.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('called')\n",
        encoding="utf-8",
    )
    runtime = LocalTaskRuntime(
        work_root=tmp_path / "attempts",
        adapter_builder=lambda **_kwargs: _MissingOutputAdapter(),
    )

    record = run_trial(
        runtime=runtime,
        task=task,
        trial=_planned_trial(),
        recipe=build_attempt_recipe(BestOfSpec(candidates=3)),
    )

    assert record.execution_status.value == "failed"
    assert record.evaluation_status.value == "failed"
    assert record.evaluation is None
    assert record.output is None
    assert record.cost is not None and record.cost.model_calls == 3
    assert not marker.exists()
    assert all(not workspace.exists() for workspace in runtime.attempt_workspaces)


def test_verifier_feedback_runs_one_same_workspace_retry_and_retains_both_verifications(tmp_path: Path) -> None:
    task = _resolved_task(tmp_path)
    (task.instance_dir / "verifier_retry_prompt.md").write_text("Use the feedback to repair the result.\n")
    (task.instance_dir / "tests" / "verify.py").write_text(
        """import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--input")
parser.add_argument("--output")
args = parser.parse_args()
workspace = Path.cwd()
text = Path(args.input).read_text()
reward = 1.0 if text == "repaired\\n" else 0.25
Path(args.output).write_text(json.dumps({"reward": reward}))
(workspace / "logs/verifier/details.json").write_text(json.dumps({"repaired": reward == 1.0}))
(workspace / "logs/verifier/feedback.md").write_text("Replace the draft result.")
counter = workspace / "verification_calls.txt"
counter.write_text(str(int(counter.read_text()) + 1) if counter.exists() else "1")
""",
        encoding="utf-8",
    )
    requests: list[AdapterRequest] = []
    workspaces: list[Path] = []

    def builder(**kwargs):  # noqa: ANN003, ANN202
        workspace = Path(kwargs["workspace"])
        workspaces.append(workspace)
        return _FeedbackAdapter(workspace, requests)

    runtime = LocalTaskRuntime(work_root=tmp_path / "attempts", adapter_builder=builder)
    record = run_trial_with_verifier_feedback(runtime=runtime, task=task, trial=_planned_trial())

    assert len(requests) == 2
    assert workspaces[0] == workspaces[1]
    assert "draft" in requests[1].instruction
    assert "Replace the draft result." in requests[1].instruction
    assert "Use the feedback to repair the result." in requests[1].instruction
    assert record.evaluation is not None and record.evaluation.reward == 1.0
    assert record.cost is not None and record.cost.model_calls == 2
    assert all(not workspace.exists() for workspace in workspaces)
    logical_paths = {artifact.logical_path: artifact for artifact in record.outputs.artifacts}
    assert "logs/verifier/attempts/attempt-01/result.md" in logical_paths
    assert "logs/verifier/attempts/attempt-01/reward.json" in logical_paths
    assert "logs/verifier/retry.json" in logical_paths
    retry_ref = logical_paths["logs/verifier/retry.json"].artifact
    retry_summary = json.loads((runtime.artifact_root / retry_ref.artifact_id).read_text(encoding="utf-8"))
    assert retry_summary["initial_reward"] == 0.25
    assert retry_summary["final_reward"] == 1.0


def test_run_trial_cleans_tracked_attempt_when_recipe_raises(tmp_path: Path) -> None:
    task = _resolved_task(tmp_path)
    runtime = LocalTaskRuntime(
        work_root=tmp_path / "attempts",
        adapter_builder=lambda **kwargs: _WorkspaceAdapter(Path(kwargs["workspace"]), []),
    )

    def failing_recipe(run_once):  # noqa: ANN001, ANN202
        run_once(attempt_id="created")
        raise RuntimeError("recipe failed")

    with pytest.raises(RuntimeError, match="recipe failed"):
        run_trial(runtime=runtime, task=task, trial=_planned_trial(), recipe=failing_recipe)

    assert runtime.attempt_workspaces
    assert all(not workspace.exists() for workspace in runtime.attempt_workspaces)
