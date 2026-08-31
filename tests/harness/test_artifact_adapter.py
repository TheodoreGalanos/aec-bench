# ABOUTME: Tests the scheduler-facing artifact trial adapter at its execution boundary.
# ABOUTME: Proves exact plan binding, candidate identity, portable publication, and fail-closed finalization.

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from aec_bench.adapters.base import AdapterRequest, AdapterResult
from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.contracts.execution_policy import ExecutionPolicy
from aec_bench.contracts.identity import EntityKind, new_entity_id
from aec_bench.contracts.run_plan import BestOfAttemptRecipe
from aec_bench.contracts.trial_record import EvaluationStatus
from aec_bench.execution.models import RetryPolicy
from aec_bench.execution.operational import AttemptRecord, OperationalStore, WorkItemRecord
from aec_bench.execution.scheduler import LocalScheduler
from aec_bench.harness.artifact_tasks import (
    ArtifactTrialAdapter,
    ArtifactTrialAdapterError,
    AttemptSelectionEvidence,
    LocalTaskRuntime,
)
from aec_bench.ledger.artifact_repository import ArtifactRepository
from tests.harness.test_persisted_artifact_plan import _ready_store, _spec, _task


class _WritingAdapter:
    def __init__(
        self, workspace: Path, calls: list[int], *, fail: bool = False, failed_calls: frozenset[int] = frozenset()
    ) -> None:
        self.workspace = workspace
        self.calls = calls
        self.fail = fail
        self.failed_calls = failed_calls

    def execute(self, request: AdapterRequest) -> AdapterResult:
        self.calls.append(len(self.calls))
        if self.fail:
            raise RuntimeError("runtime failed")
        output = self.workspace / "deliverables" / "result.md"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(f"candidate-{len(self.calls)}\n", encoding="utf-8")
        return AdapterResult(
            adapter_name="direct",
            resolved_model="model-0",
            configuration_record={},
            agent_output=AgentOutput(
                status=(
                    AgentOutputStatus.FAILED
                    if len(self.calls) - 1 in self.failed_calls
                    else AgentOutputStatus.COMPLETED
                ),
                output_path=request.output_path,
                output_format=request.output_format,
            ),
            transcript=[],
        )


def _scheduled_boundary(
    tmp_path: Path,
    *,
    best_of: int | None = None,
    verify: bool = False,
    fail: bool = False,
    failed_calls: frozenset[int] = frozenset(),
    scheduler_owned: bool = False,
) -> tuple[ArtifactTrialAdapter, OperationalStore, WorkItemRecord, AttemptRecord | None, LocalTaskRuntime, list[int]]:
    task = _task(tmp_path)
    if verify:
        (task.instance_dir / "tests" / "verify.py").write_text(
            "raise RuntimeError('verifier failed')\n", encoding="utf-8"
        )
    spec = _spec(task)
    evidence_store, plan = _ready_store(
        tmp_path,
        spec,
        attempt_recipe=(None if best_of is None else BestOfAttemptRecipe(candidates=best_of, selector="self")),
    )
    now = datetime(2026, 8, 30, 12, tzinfo=UTC)
    operational = OperationalStore(tmp_path / "operational.sqlite3")
    operational.create_run(str(plan.run_id), spec_ref="runs/artifact/spec.json", status="ready", now=now)
    operational.put_plan(
        str(plan.plan_id),
        run_id=str(plan.run_id),
        plan_ref="runs/artifact/plan.json",
        state="ready",
        now=now,
    )
    trial = plan.trials[0]
    operational.put_planned_trial(
        str(trial.trial_id),
        plan_id=str(plan.plan_id),
        run_id=str(plan.run_id),
        ordinal=trial.ordinal,
        now=now,
    )
    work = operational.create_work_item(
        str(new_entity_id(EntityKind.WORK_ITEM)),
        work_key=str(trial.trial_key),
        run_id=str(plan.run_id),
        trial_id=str(trial.trial_id),
        plan_id=str(plan.plan_id),
        ordinal=trial.ordinal,
        execution_family="artifact",
        backend="local",
        provider_route="default",
        model_route="model-0",
        resource_class="default",
        retry_policy=RetryPolicy(),
        available_at=now,
        now=now,
    )
    attempt = None
    if not scheduler_owned:
        lease = operational.acquire_lease(work.work_id, owner="scheduler", now=now, ttl=timedelta(minutes=5))
        attempt = operational.create_attempt_for_lease(
            work.work_id,
            trial_id=work.trial_id,
            lease_id=lease.lease_id,
            candidate_index=1,
            retry_number=0,
            now=now,
        )
        operational.update_work_item(work.work_id, state="running", now=now)
        operational.update_planned_trial(work.trial_id, state="running", now=now)
        attempt = operational.transition_attempt(attempt.attempt_id, state="running", now=now)
    calls: list[int] = []
    runtime = LocalTaskRuntime(
        work_root=tmp_path / "work",
        adapter_builder=lambda **kwargs: _WritingAdapter(
            Path(kwargs["workspace"]), calls, fail=fail, failed_calls=failed_calls
        ),
        normalise=False,
    )
    adapter = ArtifactTrialAdapter(
        evidence_store=evidence_store,
        operational_store=operational,
        plan=plan,
        runtime=runtime,
        tasks=[task],
        verify=verify,
    )
    return adapter, operational, operational.get_work_item(work.work_id), attempt, runtime, calls


def test_adapter_executes_one_scheduler_attempt_and_publishes_one_final_record(tmp_path: Path) -> None:
    adapter, operational, work, attempt, _, calls = _scheduled_boundary(tmp_path)

    result = adapter.execute(work, attempt)

    assert calls == [0]
    assert len(result.receipts) == 1
    assert str(result.receipts[0].attempt_id) == attempt.attempt_id
    assert result.receipts[0].process_status == "succeeded"
    assert result.receipts[0].verifier_receipt is None
    assert str(result.finalization.trial_id) == work.trial_id
    assert result.record.execution_status == "completed"
    assert result.record.evaluation_status == EvaluationStatus.COMPLETED
    assert result.finalization.trial_record_ref.endswith(f"{work.trial_id}.json")
    assert (tmp_path / "runs" / str(result.finalization.trial_record_ref)).is_file()


def test_adapter_keeps_best_of_candidates_under_one_trial_and_binds_scheduler_attempt(tmp_path: Path) -> None:
    adapter, operational, work, attempt, runtime, calls = _scheduled_boundary(tmp_path, best_of=3)

    result = adapter.execute(work, attempt)

    assert len(calls) == 3
    assert len(result.receipts) == 3
    candidate_attempt_ids = {str(receipt.attempt_id) for receipt in result.receipts}
    assert attempt.attempt_id in candidate_attempt_ids
    selection_ref = next(item for item in result.record.extension_refs if item.extension_kind == "attempt_selection")
    evidence = AttemptSelectionEvidence.model_validate_json(
        ArtifactRepository(runtime.artifact_root).read_bytes(selection_ref.artifact)
    )
    assert evidence.selected_index == 0
    assert evidence.candidates[0].attempt_id == attempt.attempt_id
    assert all(candidate.attempt_id in candidate_attempt_ids for candidate in evidence.candidates)
    attempts = operational.list_attempts(work.trial_id)
    assert [(item.candidate_index, item.retry_number, item.state) for item in attempts] == [
        (1, 0, "succeeded"),
        (2, 0, "succeeded"),
        (3, 0, "succeeded"),
    ]
    submissions = tuple(
        submission for item in attempts for submission in operational.list_backend_submissions(item.attempt_id)
    )
    assert len(submissions) == 3
    assert {submission.submission_id for submission in submissions} == {
        str(receipt.submission_id) for receipt in result.receipts
    }
    assert len(list((tmp_path / "runs").rglob("receipts/*.json"))) == 3
    assert len(list((tmp_path / "runs").rglob("finalizations/*.json"))) == 1


def test_scheduler_dispatches_adapter_and_preserves_candidate_outcomes(tmp_path: Path) -> None:
    adapter, operational, work, _, _, calls = _scheduled_boundary(
        tmp_path, best_of=2, failed_calls=frozenset({0}), scheduler_owned=True
    )
    scheduler = LocalScheduler(operational, ExecutionPolicy(max_concurrency=1))
    now = datetime(2026, 8, 30, 12, tzinfo=UTC)

    report = scheduler.dispatch_once(adapter, owner="scheduler", now=now)

    assert report.succeeded_count == 1
    assert len(calls) == 2
    attempts = operational.list_attempts(work.trial_id)
    assert [item.state for item in attempts] == ["failed", "succeeded"]
    assert operational.get_work_item(work.work_id).state == "succeeded"
    assert operational.get_planned_trial(work.trial_id).state == "succeeded"
    assert len(list((tmp_path / "runs").rglob("receipts/*.json"))) == 2
    assert len(list((tmp_path / "runs").rglob("finalizations/*.json"))) == 1


def test_adapter_publishes_verifier_failure_as_completed_execution_with_failed_evaluation(tmp_path: Path) -> None:
    adapter, _, work, attempt, _, _ = _scheduled_boundary(tmp_path, verify=True)

    result = adapter.execute(work, attempt)

    assert result.receipts[0].process_status == "succeeded"
    assert result.receipts[0].verifier_receipt is not None
    assert result.record.execution_status == "completed"
    assert result.record.evaluation_status == EvaluationStatus.FAILED


def test_adapter_records_failed_candidate_before_selecting_later_candidate(tmp_path: Path) -> None:
    adapter, operational, work, _, _, calls = _scheduled_boundary(tmp_path, best_of=3, failed_calls=frozenset({0}))

    result = adapter.execute(work, operational.get_attempt(operational.list_attempts(work.trial_id)[0].attempt_id))

    assert len(calls) == 3
    assert [receipt.process_status for receipt in result.receipts] == ["failed", "succeeded", "succeeded"]
    assert result.record.execution_status == "completed"
    assert result.finalization.attempt_id == result.receipts[1].attempt_id


def test_adapter_finalizes_all_candidate_failure_once(tmp_path: Path) -> None:
    adapter, operational, work, attempt, _, calls = _scheduled_boundary(
        tmp_path, best_of=3, failed_calls=frozenset({0, 1, 2})
    )

    result = adapter.execute(work, attempt)

    assert len(calls) == 3
    assert result.record.execution_status == "failed"
    assert all(receipt.process_status == "failed" for receipt in result.receipts)
    assert all(item.state == "failed" for item in operational.list_attempts(work.trial_id))


def test_adapter_propagates_runtime_failure_without_finalizing(tmp_path: Path) -> None:
    adapter, operational, work, attempt, _, _ = _scheduled_boundary(tmp_path, fail=True)

    with pytest.raises(RuntimeError, match="runtime failed"):
        adapter.execute(work, attempt)
    assert operational.list_attempts(work.trial_id)[0].state == "failed"
    assert len(operational.list_backend_submissions(attempt.attempt_id)) == 1
    assert len(list((tmp_path / "runs").rglob("receipts/*.json"))) == 1
    assert not list((tmp_path / "runs").rglob("finalizations/*.json"))


def test_adapter_rejects_duplicate_finalization_before_running_again(tmp_path: Path) -> None:
    adapter, _, work, attempt, _, calls = _scheduled_boundary(tmp_path)
    adapter.execute(work, attempt)

    with pytest.raises(ArtifactTrialAdapterError, match="already exists"):
        adapter.execute(work, attempt)
    assert calls == [0]
