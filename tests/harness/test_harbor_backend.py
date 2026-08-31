# ABOUTME: Tests the strict scheduler-facing Harbor backend boundary.
# ABOUTME: Uses a provider-free client fake to prove exact identity binding and portable publication.

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

import pytest

from aec_bench.contracts.execution_policy import ExecutionPolicy
from aec_bench.contracts.identity import EntityKind, new_entity_id
from aec_bench.contracts.trial_record import AgentConfiguration as RecordAgentConfiguration
from aec_bench.contracts.trial_record import ExecutionEnvironmentRef
from aec_bench.execution.models import FailureClass, FailureClassification, FailureKind, RetryPolicy, TrialWorkItem
from aec_bench.execution.operational import OperationalStore
from aec_bench.execution.scheduler import LocalScheduler
from aec_bench.harness.harbor_backend import HarborBackend, HarborBackendError, HarborRemoteState, HarborSubmission
from aec_bench.harness.harbor_conformance import (
    EXPECTED_CAPABILITIES,
    REQUIRED_GUARANTEES,
    HarborBackendConformanceCase,
    run_harbor_backend_conformance,
)
from aec_bench.trials import planned_trial_binding
from tests.harness.test_persisted_artifact_plan import _ready_store, _spec, _task
from tests.support.trial_record_factories import make_trial_record


class _Client:
    def __init__(
        self,
        record,  # noqa: ANN001
        *,
        state: Literal["completed", "unknown"] = "completed",
        submit_error: bool = False,
        missing_result: bool = False,
    ) -> None:
        self.record = record
        self.state = state
        self.submit_error = submit_error
        self.missing_result = missing_result
        self.transport = None
        self.submit_calls = 0

    def submit(self, transport):  # noqa: ANN001
        if self.submit_error:
            raise RuntimeError("Harbor submission response was lost")
        self.submit_calls += 1
        self.transport = transport
        return HarborSubmission(external_id="job-1", harbor_trial_name="trial-1")

    def inspect(self, submission):  # noqa: ANN001
        return HarborRemoteState(state=self.state)

    def collect(self, submission):  # noqa: ANN001
        return None if self.missing_result else self.record


@pytest.mark.parametrize(
    "scenario",
    (
        "completed",
        "remote_unknown",
        "remote_completion_after_unknown",
        "submit_uncertain",
        "missing_result",
        "identity_drift",
    ),
)
def test_harbor_backend_reconciles_one_scheduler_attempt(tmp_path: Path, scenario: str) -> None:
    task = _task(tmp_path)
    spec = _spec(task)
    evidence, plan = _ready_store(tmp_path, spec)
    trial = plan.trials[0]
    output = tmp_path / "harbor-output.md"
    output.write_text("complete\n", encoding="utf-8")
    record = make_trial_record(
        timestamp=datetime(2026, 8, 30, 12, 2, tzinfo=UTC),
        experiment_id=str(spec.experiment_identity.id),
        trial_id=str(trial.trial_id),
        run_id=str(spec.run_identity.id),
        task_id=trial.task_release.task_id,
        task={"task_id": trial.task_release.task_id, "task_revision": trial.task_release.artifact.sha256},
        agent=RecordAgentConfiguration(
            adapter=trial.agent_condition.adapter,
            model=trial.agent_condition.model,
            adapter_revision="adapter-revision",
            configuration={"parameters": trial.agent_condition.parameters},
        ),
        environment=ExecutionEnvironmentRef(
            runtime_image="test-image",
            compute_backend=trial.compute.backend,
            tool_versions={},
        ),
    )
    record.attach_artifact("raw_output", output, media_type="text/markdown")
    record = record.model_copy(update={"planned_trial_binding": planned_trial_binding(trial, spec)})
    if scenario == "identity_drift":
        record = record.model_copy(update={"input": record.input.model_copy(update={"task_revision": "0" * 64})})

    operational = OperationalStore(tmp_path / "operational.sqlite3")
    operational.create_run(plan.run_id, spec_ref="runs/run/spec.json", status="ready")
    operational.put_plan(plan.plan_id, run_id=plan.run_id, plan_ref="runs/run/plan.json", state="ready")
    now = datetime(2026, 8, 30, 12, 2, tzinfo=UTC)
    scheduler = LocalScheduler(operational, ExecutionPolicy(max_concurrency=1))
    scheduler.enqueue_ready_plan(
        plan,
        (
            TrialWorkItem(
                work_id=new_entity_id(EntityKind.WORK_ITEM),
                work_key="work-1",
                run_id=plan.run_id,
                plan_id=plan.plan_id,
                trial_id=trial.trial_id,
                ordinal=trial.ordinal,
                execution_family="artifact",
                backend=trial.compute.backend,
                provider_route="default",
                model_route="default",
                resource_class="cpu-small",
                priority=0,
                retry_policy=RetryPolicy(),
                state="planned",
                created_at=now,
                available_at=now,
            ),
        ),
    )
    client = _Client(
        record,
        state="unknown" if scenario in {"remote_unknown", "remote_completion_after_unknown"} else "completed",
        submit_error=scenario == "submit_uncertain",
        missing_result=scenario == "missing_result",
    )
    backend = HarborBackend(evidence_store=evidence, operational_store=operational, plan=plan, client=client)
    assert backend.capabilities == EXPECTED_CAPABILITIES

    report = scheduler.dispatch_once(backend, owner="scheduler", now=now)

    expected_success = scenario == "completed"
    expected_failure = scenario == "identity_drift"
    assert report.succeeded_count == int(expected_success)
    assert report.failed_count == int(expected_failure)
    assert len(operational.list_attempts(trial.trial_id)) == 1
    submissions = operational.list_backend_submissions_for_run(plan.run_id)
    assert len(submissions) == 1
    run_directory = evidence.run_directory(spec.run_identity)
    mapping_paths = tuple((run_directory / "harbor-mappings").glob("*.json"))
    assert len(mapping_paths) == 1
    mapping = json.loads(mapping_paths[0].read_text(encoding="utf-8"))
    assert mapping["trial_id"] == str(trial.trial_id)
    assert mapping["attempt_id"] == operational.list_attempts(trial.trial_id)[0].attempt_id
    assert mapping["harbor_trial_name"] is None
    if expected_success:
        assert client.transport is not None
        assert client.transport.trial_id == trial.trial_id
        assert client.transport.ordinal == trial.ordinal
        assert submissions[0].external_id == "job-1"
        assert submissions[0].state == "completed"
        assert (run_directory / "trial-records" / f"{trial.trial_id}.json").is_file()
        persisted = json.loads((run_directory / "trial-records" / f"{trial.trial_id}.json").read_text(encoding="utf-8"))
        assert persisted["output"]["agent_result"]["harbor_trial_name"] == "trial-1"
        assert persisted["output"]["agent_result"]["harbor_external_id"] == "job-1"
        assert len(tuple((run_directory / "receipts").glob("*.json"))) == 1
        assert len(tuple((run_directory / "finalizations").glob("*.json"))) == 1
        receipt_payload = json.loads(next((run_directory / "receipts").glob("*.json")).read_text(encoding="utf-8"))
        assert receipt_payload["attempt_id"] == operational.list_attempts(trial.trial_id)[0].attempt_id
        assert receipt_payload["submission_id"] == submissions[0].submission_id
        assert receipt_payload["process_status"] == "succeeded"
        assert receipt_payload["started_at"] and receipt_payload["finished_at"]
        assert receipt_payload["failure"] is None
        with pytest.raises(HarborBackendError):
            backend(
                replace(operational.list_work_items(plan.run_id)[0], state="running"),
                replace(operational.list_attempts(trial.trial_id)[0], state="running"),
            )
        assert len(tuple((run_directory / "finalizations").glob("*.json"))) == 1
        assert client.submit_calls == 1
        with pytest.raises(HarborBackendError, match="does not match"):
            backend(
                replace(operational.list_work_items(plan.run_id)[0], state="running", ordinal=trial.ordinal + 1),
                replace(operational.list_attempts(trial.trial_id)[0], state="running"),
            )
    elif expected_failure:
        assert submissions[0].state == "failed"
        assert operational.get_attempt(operational.list_attempts(trial.trial_id)[0].attempt_id).state == "failed"
        assert not (run_directory / "trial-records" / f"{trial.trial_id}.json").exists()
        assert not (run_directory / "finalizations" / f"{trial.trial_id}.json").exists()
    else:
        assert submissions[0].state == "unknown"
        unknown_attempt = operational.get_attempt(operational.list_attempts(trial.trial_id)[0].attempt_id)
        assert unknown_attempt.state == "unknown"
        assert unknown_attempt.failure_kind == "unknown_external_state"
        assert unknown_attempt.failure_class == "unknown"
        assert unknown_attempt.reconciliation_state == "pending"
        assert submissions[0].reconciliation_state == "pending"
        assert len(tuple((run_directory / "receipts").glob("*.json"))) == 1
        assert not (run_directory / "trial-records" / f"{trial.trial_id}.json").exists()
        assert not (run_directory / "finalizations" / f"{trial.trial_id}.json").exists()
        if scenario == "remote_completion_after_unknown":
            client.state = "completed"

            scheduler.reconcile_unknown(
                plan.run_id,
                backends={trial.compute.backend: backend},
                now=now + timedelta(seconds=5),
            )

            assert operational.get_work_item(operational.list_work_items(plan.run_id)[0].work_id).state == "succeeded"
            assert operational.list_attempts(trial.trial_id)[0].state == "succeeded"
            assert (run_directory / "trial-records" / f"{trial.trial_id}.json").is_file()
            assert len(tuple((run_directory / "finalizations").glob("*.json"))) == 1

            work_item = operational.list_work_items(plan.run_id)[0]
            attempt = operational.list_attempts(trial.trial_id)[0]
            submission = operational.list_backend_submissions_for_run(plan.run_id)[0]
            operational.update_work_item(work_item.work_id, state="unknown")
            operational.update_planned_trial(trial.trial_id, state="unknown")
            operational.transition_attempt(attempt.attempt_id, state="unknown", reconciliation_state="pending")
            operational.transition_backend_submission(
                submission.submission_id, state="unknown", reconciliation_state="pending"
            )
            client.state = "unknown"
            scheduler.reconcile_unknown(
                plan.run_id,
                backends={trial.compute.backend: backend},
                now=now + timedelta(seconds=10),
            )
            assert operational.get_work_item(work_item.work_id).state == "succeeded"
            assert operational.get_attempt(attempt.attempt_id).state == "succeeded"
            assert operational.get_backend_submission(submission.submission_id).state == "completed"
            assert len(tuple((run_directory / "trial-records").glob("*.json"))) == 1
            assert len(tuple((run_directory / "finalizations").glob("*.json"))) == 1


def test_harbor_backend_conformance_case_exercises_scheduler_path(tmp_path: Path) -> None:
    task = _task(tmp_path)
    spec = _spec(task)
    evidence, plan = _ready_store(tmp_path, spec)
    trial = plan.trials[0]
    output = tmp_path / "harbor-output.md"
    output.write_text("complete\n", encoding="utf-8")
    record = make_trial_record(
        timestamp=datetime(2026, 8, 30, 12, 2, tzinfo=UTC),
        experiment_id=str(spec.experiment_identity.id),
        trial_id=str(trial.trial_id),
        run_id=str(spec.run_identity.id),
        task_id=trial.task_release.task_id,
        task={"task_id": trial.task_release.task_id, "task_revision": trial.task_release.artifact.sha256},
        agent=RecordAgentConfiguration(
            adapter=trial.agent_condition.adapter,
            model=trial.agent_condition.model,
            adapter_revision="adapter-revision",
            configuration={"parameters": trial.agent_condition.parameters},
        ),
        environment=ExecutionEnvironmentRef(
            runtime_image="test-image", compute_backend=trial.compute.backend, tool_versions={}
        ),
    )
    record.attach_artifact("raw_output", output, media_type="text/markdown")
    record = record.model_copy(update={"planned_trial_binding": planned_trial_binding(trial, spec)})
    operational = OperationalStore(tmp_path / "operational.sqlite3")
    operational.create_run(plan.run_id, spec_ref="runs/run/spec.json", status="ready")
    operational.put_plan(plan.plan_id, run_id=plan.run_id, plan_ref="runs/run/plan.json", state="ready")
    now = datetime(2026, 8, 30, 12, 2, tzinfo=UTC)
    scheduler = LocalScheduler(operational, ExecutionPolicy(max_concurrency=1))
    scheduler.enqueue_ready_plan(
        plan,
        (
            TrialWorkItem(
                work_id=new_entity_id(EntityKind.WORK_ITEM),
                work_key="work-conformance",
                run_id=plan.run_id,
                plan_id=plan.plan_id,
                trial_id=trial.trial_id,
                ordinal=trial.ordinal,
                execution_family="artifact",
                backend=trial.compute.backend,
                provider_route="default",
                model_route="default",
                resource_class="cpu-small",
                priority=0,
                retry_policy=RetryPolicy(),
                state="planned",
                created_at=now,
                available_at=now,
            ),
        ),
    )
    client = _Client(record)
    backend = HarborBackend(evidence_store=evidence, operational_store=operational, plan=plan, client=client)
    outcomes = []

    def worker(work_item, attempt):  # noqa: ANN001
        outcome = backend.execute(work_item, attempt)
        outcomes.append(outcome)
        return outcome

    scheduler.dispatch_once(worker, owner="conformance", now=now)
    assert len(outcomes) == 1
    successful = outcomes[0]
    work_item = operational.list_work_items(plan.run_id)[0]
    attempt = operational.list_attempts(trial.trial_id)[0]
    submission = operational.list_backend_submissions_for_run(plan.run_id)[0]
    repeated = lambda: backend.reconcile(  # noqa: E731
        replace(work_item, state="unknown"),
        replace(attempt, state="unknown"),
        replace(submission, state="unknown"),
    )

    unknown_root = tmp_path / "unknown"
    unknown_root.mkdir()
    unknown_task = _task(unknown_root)
    unknown_spec = _spec(unknown_task)
    unknown_evidence, unknown_plan = _ready_store(unknown_root, unknown_spec)
    unknown_trial = unknown_plan.trials[0]
    unknown_operational = OperationalStore(unknown_root / "operational.sqlite3")
    unknown_operational.create_run(unknown_plan.run_id, spec_ref="runs/run/spec.json", status="ready")
    unknown_operational.put_plan(
        unknown_plan.plan_id, run_id=unknown_plan.run_id, plan_ref="runs/run/plan.json", state="ready"
    )
    unknown_scheduler = LocalScheduler(unknown_operational, ExecutionPolicy(max_concurrency=1))
    unknown_scheduler.enqueue_ready_plan(
        unknown_plan,
        (
            TrialWorkItem(
                work_id=new_entity_id(EntityKind.WORK_ITEM),
                work_key="work-unknown",
                run_id=unknown_plan.run_id,
                plan_id=unknown_plan.plan_id,
                trial_id=unknown_trial.trial_id,
                ordinal=unknown_trial.ordinal,
                execution_family="artifact",
                backend=unknown_trial.compute.backend,
                provider_route="default",
                model_route="default",
                resource_class="cpu-small",
                priority=0,
                retry_policy=RetryPolicy(),
                state="planned",
                created_at=now,
                available_at=now,
            ),
        ),
    )
    unknown_client = _Client(record, state="unknown")
    unknown_backend = HarborBackend(
        evidence_store=unknown_evidence,
        operational_store=unknown_operational,
        plan=unknown_plan,
        client=unknown_client,
    )
    unknown_outcomes = []

    def unknown_worker(work_item, attempt):  # noqa: ANN001
        outcome = unknown_backend.execute(work_item, attempt)
        unknown_outcomes.append(outcome)
        return outcome

    unknown_scheduler.dispatch_once(unknown_worker, owner="conformance", now=now)
    unknown_outcome = unknown_outcomes[0]
    persisted_path = next((evidence.run_directory(spec.run_identity) / "harbor-mappings").glob("*.json"))
    persisted = json.loads(persisted_path.read_text(encoding="utf-8"))
    assert client.transport is not None
    identity = lambda: (  # noqa: E731
        str(client.transport.trial_id),
        record.trial_id,
        str(successful.finalization.trial_id),
    )

    result = run_harbor_backend_conformance(
        HarborBackendConformanceCase(
            backend=backend,
            successful_execution=lambda: successful,
            repeated_collection=repeated,
            unknown_execution=lambda: unknown_outcome,
            cancellation=lambda: backend.cancel(
                work_item,
                attempt,
                submission,
            ),
            retryable_failure=lambda: FailureClassification(
                failure_class=FailureClass.INFRASTRUCTURE,
                kind=FailureKind.TRANSPORT_UNAVAILABLE,
                message="transport unavailable",
            ),
            terminal_failure=lambda: FailureClassification(
                failure_class=FailureClass.BENCHMARK,
                kind=FailureKind.TASK_FAILURE,
                message="task failed",
            ),
            persisted_transport=lambda: persisted,
            wrong_identity=lambda: backend.execute(
                replace(work_item, ordinal=work_item.ordinal + 1),
                replace(attempt, state="running"),
            ),
            planned_trial_identity=identity,
        )
    )
    assert set(result["proven"]) == REQUIRED_GUARANTEES
