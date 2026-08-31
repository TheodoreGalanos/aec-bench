# ABOUTME: Tests the scheduler-facing finite lifecycle trial adapter.
# ABOUTME: Proves lifecycle release binding, one scheduler attempt, durable evidence, and terminal failures.

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
from aec_bench.contracts.execution_release import LifecycleExecutionRelease
from aec_bench.contracts.experiment_manifest import AgentConfig
from aec_bench.contracts.identity import EntityKind, new_entity_id
from aec_bench.contracts.resolved_run import ResolvedRunSpec
from aec_bench.contracts.run_plan import BestOfAttemptRecipe, PlannedTrial
from aec_bench.contracts.trial_record import (
    AgentConfiguration,
    EvaluationStatus,
    EvidenceStatus,
    ExecutionEnvironmentRef,
    ExecutionStatus,
    ProviderRoute,
    RunManifest,
    TimingRecord,
    TrialInput,
    TrialOutput,
    TrialRecord,
    UnresolvedSourceRef,
)
from aec_bench.execution import ExecutionPolicy, LocalScheduler, RetryPolicy, TrialWorkItem, WorkItemState
from aec_bench.execution.operational import OperationalStore
from aec_bench.harness import lifecycle_trials
from aec_bench.harness.lifecycle_trials import LifecycleTrialAdapter, LifecycleTrialAdapterError
from aec_bench.harness.planned_trial_reconciliation import planned_trial_binding
from aec_bench.lifecycles.compiled import CompiledLifecycle, CompiledLifecycleEnvelope
from aec_bench.lifecycles.runtime.episode import LifecycleExecutionMode, LifecycleVisibilityPolicy
from aec_bench.lifecycles.values import LifecycleExecution, LifecycleTrial
from aec_bench.trials import PlannedTrial as LegacyPlannedTrial
from tests.harness.test_persisted_family_plans import _spec_and_plan, _store


def _release() -> tuple[CompiledLifecycleEnvelope, LifecycleExecutionRelease]:
    envelope = CompiledLifecycleEnvelope(
        visibility="public",
        template_id="test-template",
        lifecycle_id="test-lifecycle",
        variant_id="test-variant",
        lifecycle_spec_sha256="a" * 64,
        package_sha256="b" * 64,
        executable_artifact_sha256="c" * 64,
        operation_protocol_sha256=None,
    )
    release = LifecycleExecutionRelease(
        lifecycle_identity=_identity(EntityKind.LIFECYCLE, "test-lifecycle", version=2),
        variant_identity=_identity(EntityKind.VARIANT, "test-variant", version=3),
        visibility="public",
        template_id=envelope.template_id,
        lifecycle_id=envelope.lifecycle_id,
        variant_id=envelope.variant_id,
        lifecycle_spec_sha256=envelope.lifecycle_spec_sha256,
        package_sha256=envelope.package_sha256,
        executable_artifact_sha256=envelope.executable_artifact_sha256,
        operation_protocol_sha256=None,
    )
    return envelope, release


def _identity(kind: EntityKind, key: str, version: int = 1):
    from aec_bench.contracts.identity import EntityIdentity

    return EntityIdentity(id=new_entity_id(kind), key=key, version=version)


def _record(spec: ResolvedRunSpec, trial: PlannedTrial, *, completed: bool = True) -> TrialRecord:
    started = datetime(2026, 8, 30, 12, 2, tzinfo=UTC)
    finished = started + timedelta(seconds=1)
    manifest = RunManifest(
        run_id=str(spec.run_identity.id),
        experiment_id=str(spec.experiment_identity.id),
        source=UnresolvedSourceRef(reason="test"),
        agent=AgentConfiguration(adapter=trial.agent_condition.adapter, model=trial.agent_condition.model),
        execution_environment=ExecutionEnvironmentRef(runtime_image="test", compute_backend=trial.compute.backend),
        provider_route=ProviderRoute(provider="test", route="test"),
    )
    return TrialRecord(
        trial_id=str(trial.trial_id),
        run_id=str(spec.run_identity.id),
        task_id=trial.task_release.task_id,
        planned_trial_binding=planned_trial_binding(trial, spec),
        execution_status=ExecutionStatus.COMPLETED if completed else ExecutionStatus.FAILED,
        evaluation_status=EvaluationStatus.COMPLETED,
        evidence_status=EvidenceStatus.NOT_REQUIRED,
        started_at=started,
        completed_at=finished,
        input=TrialInput(instruction="Run lifecycle", task_revision="b" * 64, task_kind="lifecycle"),
        output=(
            TrialOutput(
                agent_output=AgentOutput(
                    status=AgentOutputStatus.COMPLETED if completed else AgentOutputStatus.FAILED,
                    output_path="outputs/result.json",
                    output_format="json",
                )
            )
            if completed
            else None
        ),
        evaluation=EvaluationResult(
            reward=1.0 if completed else 0.0,
            validity=ValidityCheck(output_parseable=completed, schema_valid=completed, verifier_completed=True),
        ),
        timing=TimingRecord(total_seconds=1),
    ).bind_run_manifest(manifest)


def _boundary(tmp_path: Path, *, recipe: BestOfAttemptRecipe | None = None):
    envelope, release = _release()
    spec, plan = _spec_and_plan(tmp_path, family="lifecycle", family_release=release)
    if recipe is not None:
        plan = plan.model_copy(update={"trials": (plan.trials[0].model_copy(update={"attempt_recipe": recipe}),)})
    evidence = _store(tmp_path, spec, plan)
    operational = OperationalStore(tmp_path / "operational.sqlite3")
    now = datetime(2026, 8, 30, 12, 2, tzinfo=UTC)
    operational.create_run(str(plan.run_id), spec_ref="resolved-run-spec.json", status="ready", now=now)
    operational.put_plan(str(plan.plan_id), run_id=str(plan.run_id), plan_ref="run-plan.json", state="ready", now=now)
    trial = plan.trials[0]
    item = TrialWorkItem(
        work_id=new_entity_id(EntityKind.WORK_ITEM),
        work_key=trial.trial_key,
        run_id=plan.run_id,
        plan_id=plan.plan_id,
        trial_id=trial.trial_id,
        ordinal=trial.ordinal,
        execution_family="lifecycle",
        backend=trial.compute.backend,
        provider_route="lifecycle",
        model_route=trial.agent_condition.model,
        resource_class="default",
        retry_policy=RetryPolicy(maximum_attempts=1),
        state=WorkItemState.PLANNED,
        created_at=now,
        available_at=now,
    )
    compiled = object.__new__(CompiledLifecycle)
    object.__setattr__(compiled, "package_dir", tmp_path / "package")
    object.__setattr__(compiled, "envelope", envelope)
    legacy = LegacyPlannedTrial(
        trial_id=str(trial.trial_id),
        experiment_id=str(spec.experiment_identity.id),
        task_id=trial.task_release.task_id,
        agent=AgentConfig(
            name=str(trial.agent_condition.identity.key),
            adapter=trial.agent_condition.adapter,
            model=trial.agent_condition.model,
            parameters=trial.agent_condition.parameters,
            client=trial.agent_condition.client,
            system_prompt=trial.agent_condition.system_prompt,
        ),
        compute=trial.compute,
        repetition=trial.repetition,
    )
    lifecycle = LifecycleTrial(
        planned=legacy,
        compiled=compiled,
        run_dir=tmp_path / "lifecycle-run",
        execution_mode=LifecycleExecutionMode.FRESH_CONTEXT,
        visibility_policy=LifecycleVisibilityPolicy.ARTIFACT_MEMORY,
    )
    return spec, plan, evidence, operational, item, lifecycle


def test_lifecycle_adapter_publishes_one_attempt_and_record(tmp_path: Path, monkeypatch) -> None:
    spec, plan, evidence, operational, item, lifecycle = _boundary(tmp_path)
    output = tmp_path / "output.json"
    output.write_bytes(b"lifecycle output\n")
    lifecycle.run_dir.mkdir(parents=True)
    (lifecycle.run_dir / "pre-existing-checkpoint.marker").write_bytes(b"preserve lifecycle state")
    observed_trials: list[LifecycleTrial] = []

    def fake_run(**kwargs):
        observed_trials.append(kwargs["trial"])
        for checkpoint in ("checkpoint-1", "checkpoint-2", "checkpoint-3"):
            (lifecycle.run_dir / checkpoint).write_text("lifecycle-owned\n")
        record = _record(spec, plan.trials[0])
        record.attach_artifact("output:result", output, media_type="application/json")
        return record

    monkeypatch.setattr(lifecycle_trials, "run_lifecycle_trial", fake_run)
    adapter = LifecycleTrialAdapter(
        evidence_store=evidence,
        operational_store=operational,
        plan=plan,
        trials=[lifecycle],
        execute=lambda _: LifecycleExecution(state={}, agent={}, tool_schema=()),
        verify=lambda _package, _run: {},
    )
    scheduler = LocalScheduler(operational, ExecutionPolicy(max_concurrency=1))
    scheduler.enqueue_ready_plan(plan, (item,))
    report = scheduler.dispatch_once(adapter, owner="scheduler", now=datetime(2026, 8, 30, 12, 2, tzinfo=UTC))

    assert report.succeeded_count == 1
    assert observed_trials == [lifecycle]
    assert observed_trials[0].run_dir == lifecycle.run_dir
    assert (lifecycle.run_dir / "pre-existing-checkpoint.marker").read_bytes() == b"preserve lifecycle state"
    assert len(operational.list_attempts(plan.trials[0].trial_id)) == 1
    submission = operational.list_backend_submissions_for_run(plan.run_id)[0]
    assert len(operational.list_backend_submissions_for_run(plan.run_id)) == 1
    run_dir = evidence.run_directory(spec.run_identity)
    record_path = next(run_dir.glob("trial-records/*.json"))
    record = json.loads(record_path.read_text())
    artifact = record["output"]["artifacts"][0]["artifact"]
    assert (record_path.parent / "_artifacts" / artifact["artifact_id"]).read_bytes() == b"lifecycle output\n"
    receipt = json.loads(next(run_dir.glob("receipts/*.json")).read_text())
    assert receipt["submission_id"] == submission.submission_id
    assert receipt["output_references"][0]["artifact_id"] == artifact["artifact_id"]
    assert len(tuple(run_dir.glob("receipts/*.json"))) == 1
    assert len(tuple(run_dir.glob("finalizations/*.json"))) == 1


def test_lifecycle_adapter_rejects_best_of_before_submission(tmp_path: Path, monkeypatch) -> None:
    spec, plan, evidence, operational, item, lifecycle = _boundary(
        tmp_path,
        recipe=BestOfAttemptRecipe(candidates=2, selector="self"),
    )
    calls = 0

    def fake_run(**_kwargs):
        nonlocal calls
        calls += 1
        return _record(spec, plan.trials[0])

    monkeypatch.setattr(lifecycle_trials, "run_lifecycle_trial", fake_run)
    adapter = LifecycleTrialAdapter(
        evidence_store=evidence,
        operational_store=operational,
        plan=plan,
        trials=[lifecycle],
        execute=lambda _: LifecycleExecution(state={}, agent={}, tool_schema=()),
        verify=lambda _package, _run: {},
    )
    scheduler = LocalScheduler(operational, ExecutionPolicy(max_concurrency=1))
    scheduler.enqueue_ready_plan(plan, (item,))
    report = scheduler.dispatch_once(adapter, owner="scheduler", now=datetime(2026, 8, 30, 12, 2, tzinfo=UTC))

    assert report.failed_count == 1
    assert calls == 0
    assert not operational.list_backend_submissions_for_run(plan.run_id)
    assert not list(evidence.run_directory(spec.run_identity).glob("finalizations/*.json"))


@pytest.mark.parametrize("field", ("variant_id", "package_sha256"))
def test_lifecycle_adapter_rejects_release_drift_before_effects(tmp_path: Path, monkeypatch, field: str) -> None:
    spec, plan, evidence, operational, item, lifecycle = _boundary(tmp_path)
    drifted_envelope = lifecycle.compiled.envelope.model_copy(
        update={field: "drifted-variant" if field == "variant_id" else "d" * 64}
    )
    drifted_compiled = object.__new__(CompiledLifecycle)
    object.__setattr__(drifted_compiled, "package_dir", lifecycle.package_dir)
    object.__setattr__(drifted_compiled, "envelope", drifted_envelope)
    drifted_lifecycle = LifecycleTrial(
        planned=lifecycle.planned,
        compiled=drifted_compiled,
        run_dir=lifecycle.run_dir,
        execution_mode=lifecycle.execution_mode,
        visibility_policy=lifecycle.visibility_policy,
    )
    calls = 0

    def fake_run(**_kwargs):
        nonlocal calls
        calls += 1
        return _record(spec, plan.trials[0])

    monkeypatch.setattr(lifecycle_trials, "run_lifecycle_trial", fake_run)
    adapter = LifecycleTrialAdapter(
        evidence_store=evidence,
        operational_store=operational,
        plan=plan,
        trials=[drifted_lifecycle],
        execute=lambda _: LifecycleExecution(state={}, agent={}, tool_schema=()),
        verify=lambda _package, _run: {},
    )
    scheduler = LocalScheduler(operational, ExecutionPolicy(max_concurrency=1))
    scheduler.enqueue_ready_plan(plan, (item,))
    report = scheduler.dispatch_once(adapter, owner="scheduler", now=datetime(2026, 8, 30, 12, 2, tzinfo=UTC))

    assert report.failed_count == 1
    assert calls == 0
    assert not operational.list_backend_submissions_for_run(plan.run_id)
    run_dir = evidence.run_directory(spec.run_identity)
    assert not list(run_dir.glob("trial-records/*.json"))
    assert not list(run_dir.glob("receipts/*.json"))
    assert not list(run_dir.glob("finalizations/*.json"))


def test_lifecycle_adapter_publishes_a_valid_failed_execution(tmp_path: Path, monkeypatch) -> None:
    spec, plan, evidence, operational, item, lifecycle = _boundary(tmp_path)

    def fake_run(**_kwargs):
        return _record(spec, plan.trials[0], completed=False)

    monkeypatch.setattr(lifecycle_trials, "run_lifecycle_trial", fake_run)
    adapter = LifecycleTrialAdapter(
        evidence_store=evidence,
        operational_store=operational,
        plan=plan,
        trials=[lifecycle],
        execute=lambda _: LifecycleExecution(state={}, agent={}, tool_schema=()),
        verify=lambda _package, _run: {},
    )
    scheduler = LocalScheduler(operational, ExecutionPolicy(max_concurrency=1))
    scheduler.enqueue_ready_plan(plan, (item,))
    report = scheduler.dispatch_once(adapter, owner="scheduler", now=datetime(2026, 8, 30, 12, 2, tzinfo=UTC))

    assert report.failed_count == 1
    attempt = operational.list_attempts(plan.trials[0].trial_id)[0]
    assert attempt.state == "failed"
    submission = operational.list_backend_submissions_for_run(plan.run_id)[0]
    assert submission.state == "failed"
    assert operational.get_work_item(item.work_id).state == "failed"
    assert operational.get_planned_trial(plan.trials[0].trial_id).state == "failed"
    run_dir = evidence.run_directory(spec.run_identity)
    assert len(tuple(run_dir.glob("receipts/*.json"))) == 1
    assert len(tuple(run_dir.glob("trial-records/*.json"))) == 1
    assert len(tuple(run_dir.glob("finalizations/*.json"))) == 1


def test_lifecycle_adapter_keeps_failed_evaluation_as_successful_execution(tmp_path: Path, monkeypatch) -> None:
    spec, plan, evidence, operational, item, lifecycle = _boundary(tmp_path)
    output = tmp_path / "evaluation-failed-output.json"
    output.write_bytes(b"evaluation failed after execution\n")

    def fake_run(**_kwargs):
        record = _record(spec, plan.trials[0])
        record.evaluation_status = EvaluationStatus.FAILED
        record.attach_artifact("output:result", output, media_type="application/json")
        return record

    monkeypatch.setattr(lifecycle_trials, "run_lifecycle_trial", fake_run)
    adapter = LifecycleTrialAdapter(
        evidence_store=evidence,
        operational_store=operational,
        plan=plan,
        trials=[lifecycle],
        execute=lambda _: LifecycleExecution(state={}, agent={}, tool_schema=()),
        verify=lambda _package, _run: {},
    )
    scheduler = LocalScheduler(operational, ExecutionPolicy(max_concurrency=1))
    scheduler.enqueue_ready_plan(plan, (item,))
    report = scheduler.dispatch_once(adapter, owner="scheduler", now=datetime(2026, 8, 30, 12, 2, tzinfo=UTC))

    assert report.succeeded_count == 1
    attempt = operational.list_attempts(plan.trials[0].trial_id)[0]
    assert operational.get_attempt(attempt.attempt_id).state == "succeeded"
    assert operational.list_backend_submissions_for_run(plan.run_id)[0].state == "completed"
    assert operational.get_work_item(item.work_id).state == "succeeded"
    assert operational.get_planned_trial(plan.trials[0].trial_id).state == "succeeded"
    record_path = next(evidence.run_directory(spec.run_identity).glob("trial-records/*.json"))
    assert json.loads(record_path.read_text())["evaluation_status"] == "failed"


def test_lifecycle_adapter_exception_publishes_infrastructure_receipt_only(tmp_path: Path, monkeypatch) -> None:
    spec, plan, evidence, operational, item, lifecycle = _boundary(tmp_path)

    def fake_run(**_kwargs):
        raise RuntimeError("runner stopped")

    monkeypatch.setattr(lifecycle_trials, "run_lifecycle_trial", fake_run)
    adapter = LifecycleTrialAdapter(
        evidence_store=evidence,
        operational_store=operational,
        plan=plan,
        trials=[lifecycle],
        execute=lambda _: LifecycleExecution(state={}, agent={}, tool_schema=()),
        verify=lambda _package, _run: {},
    )
    scheduler = LocalScheduler(operational, ExecutionPolicy(max_concurrency=1))
    scheduler.enqueue_ready_plan(plan, (item,))
    report = scheduler.dispatch_once(adapter, owner="scheduler", now=datetime(2026, 8, 30, 12, 2, tzinfo=UTC))

    assert report.failed_count == 1
    run_dir = evidence.run_directory(spec.run_identity)
    receipts = tuple(run_dir.glob("receipts/*.json"))
    assert len(receipts) == 1
    receipt = json.loads(receipts[0].read_text())
    assert receipt["process_status"] == "failed"
    assert receipt["failure"]["kind"] == "result_import_failed"
    assert not list(run_dir.glob("trial-records/*.json"))
    assert not list(run_dir.glob("finalizations/*.json"))


def test_lifecycle_adapter_accepts_scheduler_retry_as_one_complete_attempt(tmp_path: Path, monkeypatch) -> None:
    spec, plan, evidence, operational, item, lifecycle = _boundary(tmp_path)
    output = tmp_path / "retry-output.json"
    output.write_bytes(b"retry output\n")

    def fake_run(**_kwargs):
        record = _record(spec, plan.trials[0])
        record.attach_artifact("output:result", output, media_type="application/json")
        return record

    monkeypatch.setattr(lifecycle_trials, "run_lifecycle_trial", fake_run)
    adapter = LifecycleTrialAdapter(
        evidence_store=evidence,
        operational_store=operational,
        plan=plan,
        trials=[lifecycle],
        execute=lambda _: LifecycleExecution(state={}, agent={}, tool_schema=()),
        verify=lambda _package, _run: {},
    )
    scheduler = LocalScheduler(operational, ExecutionPolicy(max_concurrency=1))
    scheduler.enqueue_ready_plan(plan, (item,))
    now = datetime(2026, 8, 30, 12, 2, tzinfo=UTC)
    selected = operational.lease_next_work_item(owner="scheduler", now=now, ttl=timedelta(minutes=1))
    assert selected is not None
    leased_item, lease = selected
    attempt = operational.create_attempt_for_lease(
        leased_item.work_id,
        trial_id=leased_item.trial_id,
        lease_id=lease.lease_id,
        candidate_index=1,
        retry_number=2,
        now=now,
    )
    running_item = operational.update_work_item(leased_item.work_id, state="running", now=now)
    operational.update_planned_trial(running_item.trial_id, state="running", now=now)
    running_attempt = operational.transition_attempt(attempt.attempt_id, state="running", now=now)

    outcome = adapter(running_item, running_attempt)

    assert outcome.terminal_state == "succeeded"
    assert operational.get_attempt(attempt.attempt_id).retry_number == 2


def test_lifecycle_adapter_rejects_duplicate_before_runtime_effects(tmp_path: Path, monkeypatch) -> None:
    spec, plan, evidence, operational, item, lifecycle = _boundary(tmp_path)
    output = tmp_path / "duplicate-output.json"
    output.write_bytes(b"duplicate output\n")
    calls = 0

    def fake_run(**_kwargs):
        nonlocal calls
        calls += 1
        record = _record(spec, plan.trials[0])
        record.attach_artifact("output:result", output, media_type="application/json")
        return record

    monkeypatch.setattr(lifecycle_trials, "run_lifecycle_trial", fake_run)
    adapter = LifecycleTrialAdapter(
        evidence_store=evidence,
        operational_store=operational,
        plan=plan,
        trials=[lifecycle],
        execute=lambda _: LifecycleExecution(state={}, agent={}, tool_schema=()),
        verify=lambda _package, _run: {},
    )
    scheduler = LocalScheduler(operational, ExecutionPolicy(max_concurrency=1))
    scheduler.enqueue_ready_plan(plan, (item,))
    now = datetime(2026, 8, 30, 12, 2, tzinfo=UTC)
    first = scheduler.dispatch_once(adapter, owner="scheduler", now=now)
    assert first.succeeded_count == 1
    submission_count = len(operational.list_backend_submissions_for_run(plan.run_id))

    operational.update_work_item(item.work_id, state="queued", now=now)
    operational.update_planned_trial(plan.trials[0].trial_id, state="queued", now=now)
    selected = operational.lease_next_work_item(owner="scheduler", now=now, ttl=timedelta(minutes=1))
    assert selected is not None
    leased_item, lease = selected
    retry_attempt = operational.create_attempt_for_lease(
        leased_item.work_id,
        trial_id=leased_item.trial_id,
        lease_id=lease.lease_id,
        candidate_index=1,
        retry_number=1,
        now=now,
    )
    running_item = operational.update_work_item(leased_item.work_id, state="running", now=now)
    running_attempt = operational.transition_attempt(retry_attempt.attempt_id, state="running", now=now)

    with pytest.raises(LifecycleTrialAdapterError, match="trial finalization already exists"):
        adapter(running_item, running_attempt)

    assert calls == 1
    assert len(operational.list_backend_submissions_for_run(plan.run_id)) == submission_count
