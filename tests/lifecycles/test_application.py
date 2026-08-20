# ABOUTME: Tests functional lifecycle trial and experiment composition through normal result values.
# ABOUTME: Proves local execution, verification, optional persistence, and direct record return.

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.experimentation.lifecycle_studies.meta_harness import (
    LifecycleHarnessCandidate,
    evaluate_lifecycle_candidate,
)
from aec_bench.experimentation.meta_harness import HarnessCandidate, evaluate_harness_candidate
from aec_bench.harness.lifecycle_local import run_local_lifecycle
from aec_bench.lifecycles.application import (
    LifecycleTrial,
    run_lifecycle_experiment,
    run_lifecycle_trial,
)
from aec_bench.lifecycles.catalogue import materialize_lifecycle, verify_lifecycle
from aec_bench.lifecycles.runtime.episode import LifecycleExecutionMode, LifecycleVisibilityPolicy
from aec_bench.trials import PlannedTrial


class _GoldAdapterBuilder:
    def __init__(self, package_dir: Path) -> None:
        self._submissions = json.loads((package_dir / "hidden" / "gold-submissions.json").read_text(encoding="utf-8"))

    def __call__(self, **_kwargs):
        submissions = self._submissions

        class _Adapter:
            def execute(self, request):
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


def _trial(tmp_path: Path, trial_id: str) -> LifecycleTrial:
    package = materialize_lifecycle(
        "drainage-model-evidence-lifecycle-review",
        tmp_path / f"package-{trial_id}",
    )
    return LifecycleTrial(
        planned=PlannedTrial(
            trial_id=trial_id,
            experiment_id="lifecycle-functional-test",
            task_id="drainage-model-evidence-lifecycle-review",
            agent=AgentConfig(
                name="test-agent",
                adapter="tool_loop",
                model="test-model",
                parameters={"max_turns_per_session": 5},
            ),
            compute=ComputeConfig(backend="local"),
            repetition=1,
        ),
        package_dir=package,
        run_dir=tmp_path / f"run-{trial_id}",
        execution_mode=LifecycleExecutionMode.FRESH_CONTEXT,
        visibility_policy=LifecycleVisibilityPolicy.ARTIFACT_MEMORY,
    )


def _execute(trial: LifecycleTrial):
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
    assert record.trial_id == "trial-one"
    assert record.evaluation is not None
    assert record.evaluation.reward == 1.0
    assert record.lifecycle_execution is not None
    assert record.lifecycle_execution.execution_mode == "fresh_context"


def test_run_lifecycle_experiment_returns_records_in_declared_order(tmp_path: Path) -> None:
    trials = [_trial(tmp_path, "trial-one"), _trial(tmp_path, "trial-two")]

    records = run_lifecycle_experiment(trials=trials, execute=_execute, verify=verify_lifecycle)

    assert [record.trial_id for record in records] == ["trial-one", "trial-two"]


def test_lifecycle_candidate_uses_runtime_independent_meta_harness_boundary(tmp_path: Path) -> None:
    candidate = HarnessCandidate(
        candidate_id="fresh-context",
        value=LifecycleHarnessCandidate(
            trials=(_trial(tmp_path, "trial-one"),),
            execute=_execute,
            verify=verify_lifecycle,
        ),
    )

    evaluated = evaluate_harness_candidate(candidate, evaluate=evaluate_lifecycle_candidate)

    assert [record.trial_id for record in evaluated.records] == ["trial-one"]
