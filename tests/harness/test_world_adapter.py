# ABOUTME: Tests the scheduler-facing Interactive World trial adapter.
# ABOUTME: Proves exact binding, one complete episode attempt, durable publication, and failure handling.

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
from aec_bench.contracts.identity import EntityKind, new_entity_id
from aec_bench.contracts.resolved_run import ResolvedRunSpec
from aec_bench.contracts.run_plan import BestOfAttemptRecipe, PlannedTrial, RunPlan
from aec_bench.contracts.trial_record import (
    AgentConfiguration,
    EvaluationStatus,
    EvidenceStatus,
    ExecutionEnvironmentRef,
    ExecutionStatus,
    PlannedTrialBinding,
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
from aec_bench.harness.planned_trial_reconciliation import planned_trial_binding
from aec_bench.harness.world_trials import WorldTrialAdapter, WorldTrialAdapterError
from aec_bench.ledger.evidence_run_store import EvidenceRunStore
from aec_bench.trials import PlannedTrial as LegacyPlannedTrial
from aec_bench.worlds.tasks import WorldTask
from tests.harness.test_persisted_family_plans import _spec_and_plan, _store, _world_task


def _record(
    spec: ResolvedRunSpec,
    trial: PlannedTrial,
    task: WorldTask,
    *,
    completed: bool = True,
    evaluation_failed: bool = False,
    artifact_root: Path | None = None,
) -> TrialRecord:
    started = datetime(2026, 8, 30, 12, 2, tzinfo=UTC)
    finished = datetime(2026, 8, 30, 12, 2, 1, tzinfo=UTC)
    manifest = RunManifest(
        run_id=str(spec.run_identity.id),
        experiment_id=str(spec.experiment_identity.id),
        source=UnresolvedSourceRef(reason="test"),
        agent=AgentConfiguration(adapter=trial.agent_condition.adapter, model=trial.agent_condition.model),
        execution_environment=ExecutionEnvironmentRef(runtime_image="test", compute_backend=trial.compute.backend),
        provider_route=ProviderRoute(provider="test", route="test"),
    )
    record = TrialRecord(
        trial_id=str(trial.trial_id),
        run_id=str(spec.run_identity.id),
        task_id=task.task_id,
        planned_trial_binding=planned_trial_binding(trial, spec),
        execution_status=ExecutionStatus.COMPLETED if completed else ExecutionStatus.FAILED,
        evaluation_status=EvaluationStatus.FAILED if evaluation_failed else EvaluationStatus.COMPLETED,
        evidence_status=EvidenceStatus.NOT_REQUIRED,
        started_at=started,
        completed_at=finished,
        input=TrialInput(instruction=task.instruction, task_revision=task.task_revision, task_kind="world"),
        output=(
            TrialOutput(
                agent_output=AgentOutput(
                    status=AgentOutputStatus.COMPLETED if completed else AgentOutputStatus.FAILED,
                    output_path="outputs/world.json",
                    output_format="json",
                ),
                artifacts=(),
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
    if artifact_root is not None:
        artifact_root.mkdir(parents=True, exist_ok=True)
        output_path = artifact_root / "world-output.json"
        provider_path = artifact_root / "provider.json"
        authority_path = artifact_root / "authority.json"
        output_path.write_bytes(b"world output bytes\n")
        provider_path.write_bytes(b"provider evidence bytes\n")
        authority_path.write_bytes(b"world authority bytes\n")
        record.attach_artifact("output:world-output", output_path, media_type="application/json")
        record.attach_artifact("provider_evidence", provider_path, media_type="application/json")
        record.attach_artifact("authority:world:aec-bench/test-world/1", authority_path, media_type="application/json")
    return record


def _boundary(
    tmp_path: Path,
    *,
    attempt_recipe: BestOfAttemptRecipe | None = None,
) -> tuple[WorldTask, ResolvedRunSpec, RunPlan, EvidenceRunStore, OperationalStore, TrialWorkItem]:
    task, release, _ = _world_task()
    spec, plan = _spec_and_plan(tmp_path)
    if attempt_recipe is not None:
        plan = plan.model_copy(
            update={"trials": (plan.trials[0].model_copy(update={"attempt_recipe": attempt_recipe}),)}
        )
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
        execution_family="world",
        backend=trial.compute.backend,
        provider_route="prime-agent",
        model_route=trial.agent_condition.model,
        resource_class="default",
        retry_policy=RetryPolicy(maximum_attempts=1),
        state=WorkItemState.PLANNED,
        created_at=now,
        available_at=now,
    )
    return task, spec, plan, evidence, operational, item


def test_scheduler_runs_one_complete_world_episode_and_publishes_portable_result(tmp_path: Path) -> None:
    task, spec, plan, evidence, operational, item = _boundary(tmp_path)
    seen: list[str] = []

    async def runner(
        world_task: WorldTask,
        legacy_trial: LegacyPlannedTrial,
        binding: PlannedTrialBinding,
    ) -> TrialRecord:
        seen.append(legacy_trial.trial_id)
        assert world_task is task
        assert binding.trial_identity == plan.trials[0].trial_identity
        return _record(spec, plan.trials[0], task, artifact_root=tmp_path / "source-artifacts")

    adapter = WorldTrialAdapter(
        evidence_store=evidence,
        operational_store=operational,
        plan=plan,
        tasks=[task],
        run_trial=runner,
    )
    scheduler = LocalScheduler(operational, ExecutionPolicy(max_concurrency=1))
    scheduler.enqueue_ready_plan(plan, (item,))
    report = scheduler.dispatch_once(adapter, owner="scheduler", now=datetime(2026, 8, 30, 12, 2, tzinfo=UTC))

    assert report.succeeded_count == 1
    assert seen == [str(plan.trials[0].trial_id)]
    assert len(operational.list_attempts(plan.trials[0].trial_id)) == 1
    submissions = operational.list_backend_submissions_for_run(plan.run_id)
    assert len(submissions) == 1
    run_dir = evidence.run_directory(spec.run_identity)
    receipt_path = next(run_dir.glob("receipts/*.json"))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["submission_id"] == submissions[0].submission_id
    record_path = next(run_dir.glob("trial-records/*.json"))
    persisted = json.loads(record_path.read_text(encoding="utf-8"))
    artifact_root = record_path.parent / "_artifacts"
    output_reference = persisted["output"]["artifacts"][0]["artifact"]
    assert (artifact_root / output_reference["artifact_id"]).read_bytes() == b"world output bytes\n"
    provider_reference = persisted["provider_evidence"]
    assert (artifact_root / provider_reference["artifact_id"]).read_bytes() == b"provider evidence bytes\n"
    authority_reference = persisted["authority_evidence"][0]["artifact"]
    assert (artifact_root / authority_reference["artifact_id"]).read_bytes() == b"world authority bytes\n"
    assert receipt["output_references"][0]["artifact_id"] == output_reference["artifact_id"]
    assert receipt["authority_evidence"][0]["artifact"]["artifact_id"] == authority_reference["artifact_id"]
    assert list(run_dir.glob("receipts/*.json"))
    assert list(evidence.run_directory(spec.run_identity).glob("finalizations/*.json"))
    assert list(evidence.run_directory(spec.run_identity).glob("trial-records/*.json"))


def test_world_adapter_persists_failed_receipt_without_finalization_on_exception(tmp_path: Path) -> None:
    task, spec, plan, evidence, operational, item = _boundary(tmp_path)

    async def runner(*_args: object) -> TrialRecord:
        raise RuntimeError("episode failed")

    adapter = WorldTrialAdapter(
        evidence_store=evidence,
        operational_store=operational,
        plan=plan,
        tasks=[task],
        run_trial=runner,
    )
    scheduler = LocalScheduler(operational, ExecutionPolicy(max_concurrency=1))
    scheduler.enqueue_ready_plan(plan, (item,))
    report = scheduler.dispatch_once(adapter, owner="scheduler", now=datetime(2026, 8, 30, 12, 2, tzinfo=UTC))

    assert report.failed_count == 1
    assert len(list(evidence.run_directory(spec.run_identity).glob("receipts/*.json"))) == 1
    assert not list(evidence.run_directory(spec.run_identity).glob("finalizations/*.json"))
    assert not list(evidence.run_directory(spec.run_identity).glob("trial-records/*.json"))
    assert operational.list_backend_submissions_for_run(plan.run_id)[0].state == "failed"
    receipt = json.loads(next(evidence.run_directory(spec.run_identity).glob("receipts/*.json")).read_text())
    assert receipt["failure"]["kind"] == "result_import_failed"


def test_world_adapter_keeps_execution_success_when_evaluation_fails(tmp_path: Path) -> None:
    task, spec, plan, evidence, operational, item = _boundary(tmp_path)

    async def runner(*_args: object) -> TrialRecord:
        return _record(spec, plan.trials[0], task, evaluation_failed=True, artifact_root=tmp_path / "source-artifacts")

    adapter = WorldTrialAdapter(
        evidence_store=evidence,
        operational_store=operational,
        plan=plan,
        tasks=[task],
        run_trial=runner,
    )
    scheduler = LocalScheduler(operational, ExecutionPolicy(max_concurrency=1))
    scheduler.enqueue_ready_plan(plan, (item,))
    report = scheduler.dispatch_once(adapter, owner="scheduler", now=datetime(2026, 8, 30, 12, 2, tzinfo=UTC))

    assert report.succeeded_count == 1
    assert operational.list_attempts(plan.trials[0].trial_id)[0].state == "succeeded"


def test_world_adapter_publishes_terminal_failed_execution(tmp_path: Path) -> None:
    task, spec, plan, evidence, operational, item = _boundary(tmp_path)

    async def runner(*_args: object) -> TrialRecord:
        return _record(spec, plan.trials[0], task, completed=False)

    adapter = WorldTrialAdapter(
        evidence_store=evidence,
        operational_store=operational,
        plan=plan,
        tasks=[task],
        run_trial=runner,
    )
    scheduler = LocalScheduler(operational, ExecutionPolicy(max_concurrency=1))
    scheduler.enqueue_ready_plan(plan, (item,))
    report = scheduler.dispatch_once(adapter, owner="scheduler", now=datetime(2026, 8, 30, 12, 2, tzinfo=UTC))

    assert report.failed_count == 1
    assert operational.get_work_item(item.work_id).state == "failed"
    assert operational.get_planned_trial(plan.trials[0].trial_id).state == "failed"
    assert operational.list_attempts(plan.trials[0].trial_id)[0].state == "failed"
    assert operational.list_backend_submissions_for_run(plan.run_id)[0].state == "failed"
    run_dir = evidence.run_directory(spec.run_identity)
    assert len(list(run_dir.glob("receipts/*.json"))) == 1
    assert len(list(run_dir.glob("trial-records/*.json"))) == 1
    assert len(list(run_dir.glob("finalizations/*.json"))) == 1


def test_world_adapter_rejects_best_of_world_recipe_before_effects(tmp_path: Path) -> None:
    task, spec, plan, evidence, operational, item = _boundary(
        tmp_path,
        attempt_recipe=BestOfAttemptRecipe(candidates=2, selector="self"),
    )
    calls = 0

    async def runner(*_args: object) -> TrialRecord:
        nonlocal calls
        calls += 1
        return _record(spec, plan.trials[0], task)

    adapter = WorldTrialAdapter(
        evidence_store=evidence,
        operational_store=operational,
        plan=plan,
        tasks=[task],
        run_trial=runner,
    )
    scheduler = LocalScheduler(operational, ExecutionPolicy(max_concurrency=1))
    scheduler.enqueue_ready_plan(plan, (item,))
    report = scheduler.dispatch_once(adapter, owner="scheduler", now=datetime(2026, 8, 30, 12, 2, tzinfo=UTC))

    assert report.failed_count == 1
    assert calls == 0
    assert not operational.list_backend_submissions_for_run(plan.run_id)
    assert not list(evidence.run_directory(spec.run_identity).glob("receipts/*.json"))
    assert not list(evidence.run_directory(spec.run_identity).glob("trial-records/*.json"))


def test_world_adapter_accepts_a_scheduler_retry_as_the_single_world_attempt(tmp_path: Path) -> None:
    task, spec, plan, evidence, operational, item = _boundary(tmp_path)

    async def runner(*_args: object) -> TrialRecord:
        return _record(spec, plan.trials[0], task, artifact_root=tmp_path / "source-artifacts")

    scheduler = LocalScheduler(operational, ExecutionPolicy(max_concurrency=1))
    scheduler.enqueue_ready_plan(plan, (item,))
    now = datetime(2026, 8, 30, 12, 2, tzinfo=UTC)
    lease = operational.acquire_lease(item.work_id, owner="retry-owner", now=now, ttl=timedelta(minutes=5))
    operational.update_work_item(item.work_id, state="running", now=now)
    operational.update_planned_trial(item.trial_id, state="running", now=now)
    attempt = operational.create_attempt_for_lease(
        item.work_id,
        trial_id=item.trial_id,
        lease_id=lease.lease_id,
        candidate_index=1,
        retry_number=2,
        now=now,
    )
    attempt = operational.transition_attempt(attempt.attempt_id, state="running", now=now)
    adapter = WorldTrialAdapter(
        evidence_store=evidence,
        operational_store=operational,
        plan=plan,
        tasks=[task],
        run_trial=runner,
    )

    result = adapter.execute(operational.get_work_item(item.work_id), attempt)

    assert result.receipt.process_status == "succeeded"
    assert operational.list_attempts(plan.trials[0].trial_id)[0].retry_number == 2


def test_world_adapter_rejects_world_profile_drift_before_runner(tmp_path: Path) -> None:
    from dataclasses import replace

    from aec_bench.contracts.interactive_world import InteractiveWorldProfileRef

    task, spec, plan, evidence, operational, item = _boundary(tmp_path)
    drifted = replace(task, profile=InteractiveWorldProfileRef(task.world.task_world_id, "other", "d" * 64))
    calls = 0

    async def runner(*_args: object) -> TrialRecord:
        nonlocal calls
        calls += 1
        return _record(spec, plan.trials[0], task)

    adapter = WorldTrialAdapter(
        evidence_store=evidence,
        operational_store=operational,
        plan=plan,
        tasks=[drifted],
        run_trial=runner,
    )
    scheduler = LocalScheduler(operational, ExecutionPolicy(max_concurrency=1))
    scheduler.enqueue_ready_plan(plan, (item,))
    report = scheduler.dispatch_once(adapter, owner="scheduler", now=datetime(2026, 8, 30, 12, 2, tzinfo=UTC))

    assert report.failed_count == 1
    assert calls == 0
    assert not list(evidence.run_directory(spec.run_identity).glob("receipts/*.json"))


def test_world_adapter_rejects_duplicate_publication_before_runner(tmp_path: Path) -> None:
    task, spec, plan, evidence, operational, item = _boundary(tmp_path)
    calls = 0

    async def runner(*_args: object) -> TrialRecord:
        nonlocal calls
        calls += 1
        return _record(spec, plan.trials[0], task)

    adapter = WorldTrialAdapter(
        evidence_store=evidence,
        operational_store=operational,
        plan=plan,
        tasks=[task],
        run_trial=runner,
    )
    scheduler = LocalScheduler(operational, ExecutionPolicy(max_concurrency=1))
    scheduler.enqueue_ready_plan(plan, (item,))
    scheduler.dispatch_once(adapter, owner="scheduler", now=datetime(2026, 8, 30, 12, 2, tzinfo=UTC))
    with pytest.raises(WorldTrialAdapterError):
        adapter(
            operational.get_work_item(item.work_id),
            operational.list_attempts(plan.trials[0].trial_id)[0],
        )
    assert calls == 1
