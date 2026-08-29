# ABOUTME: Tests functional lifecycle trial and experiment composition through normal result values.
# ABOUTME: Proves local execution, verification, optional persistence, and direct record return.

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from aec_bench.adapters.runtime_limits import AdapterRuntimeLimitError
from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.experimentation.meta_harness import HarnessCandidate, evaluate_harness_candidate
from aec_bench.harness.lifecycle_local import run_local_lifecycle
from aec_bench.lifecycles.application import (
    LifecycleExecution,
    LifecycleTrial,
    run_lifecycle_experiment,
    run_lifecycle_trial,
)
from aec_bench.lifecycles.catalogue import verify_lifecycle
from aec_bench.lifecycles.compiled import compile_lifecycle
from aec_bench.lifecycles.runtime.episode import LifecycleExecutionMode, LifecycleVisibilityPolicy
from aec_bench.lifecycles.runtime.lifecycle import EvidenceLifecycleError
from aec_bench.trials import PlannedTrial


class _GoldAdapterBuilder:
    def __init__(self, package_dir: Path) -> None:
        self._submissions = json.loads((package_dir / "hidden" / "gold-submissions.json").read_text(encoding="utf-8"))

    def __call__(self, **_kwargs: Any) -> Any:
        submissions = self._submissions

        class _Adapter:
            def execute(self, request: Any) -> Any:
                output = Path(request.output_path)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(submissions[output.stem]), encoding="utf-8")
                return SimpleNamespace(
                    adapter_name="tool_loop",
                    resolved_model="test-model",
                    configuration_record={"model": "test-model", "max_turns": 5},
                    agent_output=SimpleNamespace(status=SimpleNamespace(value="completed")),
                    transcript=[],
                    raw_output_text=None,
                    provider_error=None,
                    failure_kind=None,
                    usage_input_tokens=2,
                    usage_output_tokens=1,
                    usage_cache_read_tokens=0,
                    usage_cache_write_tokens=0,
                )

        return _Adapter()


class _CrashingAdapterBuilder:
    def __call__(self, **_kwargs: Any) -> Any:
        class _Adapter:
            def execute(self, _request: Any) -> Any:
                raise RuntimeError("simulated adapter crash")

        return _Adapter()


class _CompletedWithoutSubmissionAdapterBuilder:
    def __call__(self, **_kwargs: Any) -> Any:
        class _Adapter:
            def execute(self, _request: Any) -> Any:
                return SimpleNamespace(
                    adapter_name="tool_loop",
                    resolved_model="test-model",
                    configuration_record={"model": "test-model", "max_turns": 5},
                    agent_output=SimpleNamespace(status=SimpleNamespace(value="completed")),
                    transcript=[],
                    raw_output_text=None,
                    provider_error=None,
                    failure_kind=None,
                    usage_input_tokens=2,
                    usage_output_tokens=1,
                    usage_cache_read_tokens=0,
                    usage_cache_write_tokens=0,
                )

        return _Adapter()


def _trial(
    tmp_path: Path,
    trial_id: str,
    *,
    task_id: str = "drainage-model-evidence-lifecycle-review",
    adapter: str = "tool_loop",
    execution_mode: LifecycleExecutionMode = LifecycleExecutionMode.FRESH_CONTEXT,
    resource_limits: dict[str, int] | None = None,
    timeout_override: int | None = None,
    max_turns_per_session: int = 5,
) -> LifecycleTrial:
    compiled = compile_lifecycle(
        "drainage-model-evidence-lifecycle-review",
        tmp_path / f"package-{trial_id}",
        variant_id="staged_full_correction",
    )
    return LifecycleTrial(
        planned=PlannedTrial(
            trial_id=trial_id,
            experiment_id="lifecycle-functional-test",
            task_id=task_id,
            agent=AgentConfig(
                name="test-agent",
                adapter=adapter,
                model="test-model",
                parameters={"max_turns_per_session": max_turns_per_session},
            ),
            compute=ComputeConfig(
                backend="local",
                resource_limits=resource_limits or {},
                timeout_override=timeout_override,
            ),
            repetition=1,
        ),
        compiled=compiled,
        run_dir=tmp_path / f"run-{trial_id}",
        execution_mode=execution_mode,
        visibility_policy=(
            LifecycleVisibilityPolicy.PERSISTENT_CONTEXT
            if execution_mode is LifecycleExecutionMode.PERSISTENT_CONTEXT
            else LifecycleVisibilityPolicy.ARTIFACT_MEMORY
        ),
    )


def _execute(trial: LifecycleTrial) -> LifecycleExecution:
    return run_local_lifecycle(trial=trial, adapter_builder=_GoldAdapterBuilder(trial.package_dir))


def test_run_lifecycle_trial_returns_and_optionally_persists_same_record(tmp_path: Path) -> None:
    trial = _trial(tmp_path, "trial-one")
    persisted: list[TrialRecord] = []

    record = run_lifecycle_trial(
        trial=trial,
        execute=_execute,
        verify=verify_lifecycle,
        persist=persisted.append,
    )

    assert persisted == [record]
    assert persisted[0] is record
    assert record.trial_id == "trial-one"
    assert record.evaluation is not None
    assert record.evaluation.reward == 1.0
    assert record.lifecycle_execution is not None
    assert record.lifecycle_execution.execution_mode == "fresh_context"


def test_run_lifecycle_experiment_returns_records_in_declared_order(tmp_path: Path) -> None:
    trials = [_trial(tmp_path, "trial-one"), _trial(tmp_path, "trial-two")]

    records = run_lifecycle_experiment(trials=trials, execute=_execute, verify=verify_lifecycle)

    assert [record.trial_id for record in records] == ["trial-one", "trial-two"]


def test_run_lifecycle_trial_rejects_coercive_executor_turn_limit(tmp_path: Path) -> None:
    trial = _trial(tmp_path, "coercive-executor-turn-limit", max_turns_per_session=1)

    def execute_with_boolean_turn_limit(selected_trial: LifecycleTrial) -> LifecycleExecution:
        execution = _execute(selected_trial)
        return LifecycleExecution(
            state=execution.state,
            agent={**execution.agent, "max_turns_per_session": True},
            tool_schema=execution.tool_schema,
        )

    with pytest.raises(ValueError, match="executor turn limit does not match"):
        run_lifecycle_trial(
            trial=trial,
            execute=execute_with_boolean_turn_limit,
            verify=verify_lifecycle,
        )


def test_run_lifecycle_trial_preserves_logical_task_id_and_compiled_provenance(tmp_path: Path) -> None:
    task_id = "learning-study/drainage-probe"
    trial = _trial(tmp_path, "logical-task-id", task_id=task_id)

    record = run_lifecycle_trial(trial=trial, execute=_execute, verify=verify_lifecycle)

    provenance = record.lifecycle_provenance
    assert provenance is not None
    assert record.task_id == task_id
    assert provenance.lifecycle_id == trial.compiled.envelope.lifecycle_id
    assert provenance.package_sha256 == trial.compiled.envelope.package_sha256
    assert provenance.variant_id == trial.compiled.envelope.variant_id


def test_run_lifecycle_trial_rejects_deepseek_before_executor_call(tmp_path: Path) -> None:
    trial = _trial(
        tmp_path,
        "deepseek-canonical-record",
        adapter="deepseek_harness",
        execution_mode=LifecycleExecutionMode.PERSISTENT_CONTEXT,
    )
    executor_called = False

    def execute(_trial: LifecycleTrial) -> LifecycleExecution:
        nonlocal executor_called
        executor_called = True
        raise AssertionError("executor must not run")

    with pytest.raises(ValueError, match="cannot produce the required canonical lifecycle turn-limit evidence"):
        run_lifecycle_trial(trial=trial, execute=execute, verify=verify_lifecycle)

    assert not executor_called
    assert not trial.run_dir.exists()


@pytest.mark.asyncio
async def test_lifecycle_candidate_uses_runtime_independent_meta_harness_boundary(tmp_path: Path) -> None:
    candidate = HarnessCandidate(
        candidate_id="fresh-context",
        value=(_trial(tmp_path, "trial-one"),),
    )

    evaluated = await evaluate_harness_candidate(
        candidate,
        evaluate=lambda item: run_lifecycle_experiment(
            trials=item.value,
            execute=_execute,
            verify=verify_lifecycle,
        ),
    )

    assert [record.trial_id for record in evaluated.records] == ["trial-one"]


@pytest.mark.parametrize(
    "execution_mode",
    [LifecycleExecutionMode.FRESH_CONTEXT, LifecycleExecutionMode.PERSISTENT_CONTEXT],
)
def test_run_lifecycle_trial_finalizes_adapter_exception_as_failed_record(
    tmp_path: Path,
    execution_mode: LifecycleExecutionMode,
) -> None:
    trial = _trial(tmp_path, f"adapter-crash-{execution_mode.value}", execution_mode=execution_mode)
    executions: list[LifecycleExecution] = []
    persisted: list[TrialRecord] = []

    def execute(selected_trial: LifecycleTrial) -> LifecycleExecution:
        execution = run_local_lifecycle(trial=selected_trial, adapter_builder=_CrashingAdapterBuilder())
        executions.append(execution)
        return execution

    record = run_lifecycle_trial(
        trial=trial,
        execute=execute,
        verify=verify_lifecycle,
        persist=persisted.append,
    )

    assert executions[0].agent["status"] == "failed"
    assert persisted == [record]
    assert record.evaluation is not None
    assert record.evaluation.reward == 0.0
    assert record.lifecycle_execution is not None
    assert record.lifecycle_execution.status == "failed"
    assert len(record.lifecycle_execution.sessions) == 1
    session = record.lifecycle_execution.sessions[0]
    assert session.failure_kind == "adapter_exception"
    assert session.provider_error == "simulated adapter crash"


def test_run_local_lifecycle_propagates_submission_integrity_error(tmp_path: Path) -> None:
    trial = _trial(tmp_path, "invalid-submission")

    with pytest.raises(EvidenceLifecycleError, match="checkpoint submission not found"):
        run_local_lifecycle(trial=trial, adapter_builder=_CompletedWithoutSubmissionAdapterBuilder())

    result_path = trial.run_dir / "episodes" / "initial_review" / "initial_review.session-001" / "agent_result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert result["failure_kind"] == "episode_submission_invalid"
    assert "checkpoint submission not found" in result["provider_error"]


@pytest.mark.parametrize(
    ("resource_limits", "timeout_override", "unsupported_limit"),
    [
        ({"max_tokens": 256}, None, "max_tokens"),
        ({}, 30, "timeout_sec"),
    ],
)
@pytest.mark.parametrize(
    "execution_mode",
    [LifecycleExecutionMode.FRESH_CONTEXT, LifecycleExecutionMode.PERSISTENT_CONTEXT],
)
def test_run_local_lifecycle_rejects_unsupported_limits_before_state_changes(
    tmp_path: Path,
    execution_mode: LifecycleExecutionMode,
    resource_limits: dict[str, int],
    timeout_override: int | None,
    unsupported_limit: str,
) -> None:
    trial = _trial(
        tmp_path,
        f"unsupported-{execution_mode.value}-{unsupported_limit}",
        execution_mode=execution_mode,
        resource_limits=resource_limits,
        timeout_override=timeout_override,
    )

    with pytest.raises(AdapterRuntimeLimitError, match=unsupported_limit):
        run_local_lifecycle(trial=trial, adapter_builder=_GoldAdapterBuilder(trial.package_dir))

    assert not trial.run_dir.exists()
