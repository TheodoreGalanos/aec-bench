# ABOUTME: Composes persisted AEC-Bench run plans with the current local scheduler.
# ABOUTME: Keeps start and resume provider-neutral while resolving only executable repository paths.

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal

from aec_bench.contracts.identity import EntityKey, EntityKind, new_entity_id, validate_uuidv7
from aec_bench.contracts.run_plan import RunPlan
from aec_bench.contracts.task_snapshot import RepositoryTaskSnapshotRef
from aec_bench.execution.backend import ExecutionBackendControl
from aec_bench.execution.models import RetryPolicy, TrialWorkItem, WorkItemState
from aec_bench.execution.operational import OperationalStore, OperationalStoreError
from aec_bench.execution.scheduler import LocalScheduler, SchedulerRunReport, Worker
from aec_bench.harness.artifact_tasks import ArtifactTrialAdapter, LocalTaskRuntime
from aec_bench.harness.compilation.task_snapshot import TaskSnapshotError, assert_task_snapshot_matches_directory
from aec_bench.ledger.evidence_run_store import EvidenceRunStore, EvidenceRunStoreError
from aec_bench.tasks.instance import ResolvedTaskInstance, resolve_instance_paths
from aec_bench.tasks.loader import LoadError, load_task_definition


class RunControlError(RuntimeError):
    """Raised when a persisted run cannot be composed for local execution."""


@dataclass(frozen=True, slots=True)
class ResolvedExecution:
    """Scheduler worker and external controls resolved for one persisted plan."""

    worker: Worker
    backends: Mapping[str, ExecutionBackendControl]
    cleanup: AbstractContextManager[object] | None = None


@dataclass(frozen=True, slots=True)
class RunControlResult:
    """Outcome of one bounded start or resume operation."""

    operation: Literal["start", "resume"]
    run_id: str
    plan_id: str
    report: SchedulerRunReport
    totals: Mapping[str, int]

    def as_dict(self) -> dict[str, object]:
        return {
            "operation": self.operation,
            "run_id": self.run_id,
            "plan_id": self.plan_id,
            "report": self.report.model_dump(mode="json"),
            "totals": dict(self.totals),
        }


WorkerResolver = Callable[[RunPlan, EvidenceRunStore, OperationalStore], ResolvedExecution]


def start_or_resume_run(
    *,
    run_selector: str,
    operation: Literal["start", "resume"],
    plan_root: Path,
    operational_store_path: Path,
    tasks_root: Path | None = None,
    owner: str = "aec-bench",
    worker_resolver: WorkerResolver | None = None,
    now: datetime | None = None,
) -> RunControlResult:
    """Start or resume one persisted ready run through the local scheduler."""

    selected_now = (now or datetime.now(UTC)).astimezone(UTC)
    if not run_selector.strip():
        raise RunControlError("run selector must not be blank")
    if operation not in {"start", "resume"}:
        raise RunControlError(f"unsupported run operation: {operation}")
    try:
        readable_store = EvidenceRunStore.open_read_only(plan_root)
        stored = readable_store.find_run(run_selector)
    except (EvidenceRunStoreError, ValueError) as error:
        raise RunControlError(str(error)) from error
    if stored.plan is None:
        raise RunControlError("run has no persisted plan")
    if operation == "start" and stored.state.state != "ready":
        raise RunControlError(f"run start requires a ready run; current state is {stored.state.state}")
    if operation == "resume" and stored.state.state not in {"ready", "started"}:
        raise RunControlError(f"run resume requires a ready or started run; current state is {stored.state.state}")
    plan = stored.plan
    if plan.state != "ready":
        raise RunControlError(f"persisted run plan is not ready: {plan.state}")
    if worker_resolver is None:
        _preflight_local_plan(plan, tasks_root)

    try:
        operational = (
            OperationalStore(operational_store_path)
            if operation == "start" and not operational_store_path.exists()
            else OperationalStore.open_existing(operational_store_path)
        )
        _ensure_operational_records(operational, readable_store, plan)
        if worker_resolver is None:
            resolved = _resolve_local_execution(plan, EvidenceRunStore(plan_root), operational, tasks_root)
        else:
            resolved = worker_resolver(plan, EvidenceRunStore(plan_root), operational)
        scheduler = LocalScheduler(operational, stored.spec.execution_policy)
        with resolved.cleanup or nullcontext():
            if operation == "resume":
                operational.expire_leases(run_id=plan.run_id, now=selected_now)
                scheduler.reconcile_unknown(plan.run_id, backends=resolved.backends, now=selected_now)
                current_items = operational.list_work_items(plan.run_id)
                if any(item.state == "unknown" for item in current_items):
                    raise RunControlError("resume is blocked by work with unresolved external state")
                if any(item.state in {"leased", "running"} for item in current_items):
                    raise RunControlError("resume is blocked by active work from another owner")
            work_items = _work_items_for_plan(operational, plan, stored.spec.execution_policy.retry_policy)
            op_plan = operational.get_plan(plan.plan_id)
            if op_plan.state == "ready":
                scheduler.enqueue_ready_plan(plan, work_items)
            if stored.state.state == "ready":
                EvidenceRunStore(plan_root).start_run(plan.run_identity, started_at=selected_now)
            report, totals = _dispatch_until_quiet(scheduler, resolved.worker, owner=owner, now=selected_now)
            return RunControlResult(operation, str(plan.run_id), str(plan.plan_id), report, totals)
    except (OperationalStoreError, EvidenceRunStoreError, LoadError, ValueError) as error:
        raise RunControlError(str(error)) from error


def _ensure_operational_records(store: OperationalStore, evidence: EvidenceRunStore, plan: RunPlan) -> None:
    run_dir = evidence.run_directory(plan.run_identity)
    spec_ref = (run_dir / "resolved-run-spec.json").relative_to(evidence.root).as_posix()
    plan_ref = (run_dir / "run-plan.json").relative_to(evidence.root).as_posix()
    store.create_run(str(plan.run_id), spec_ref=spec_ref, status="ready", now=plan.created_at)
    store.put_plan(str(plan.plan_id), run_id=str(plan.run_id), plan_ref=plan_ref, state="ready", now=plan.created_at)


def _work_items_for_plan(
    store: OperationalStore, plan: RunPlan, retry_policy: RetryPolicy
) -> tuple[TrialWorkItem, ...]:
    existing = {item.trial_id: item for item in store.list_work_items(plan.run_id)}
    expected_trial_ids = {str(trial.trial_id) for trial in plan.trials}
    if existing and set(existing) != expected_trial_ids:
        raise RunControlError("stored work items do not exactly match the authoritative plan")
    result: list[TrialWorkItem] = []
    for trial in plan.trials:
        old = existing.get(str(trial.trial_id))
        if old is not None and (
            old.plan_id != str(plan.plan_id)
            or old.run_id != str(plan.run_id)
            or old.ordinal != trial.ordinal
            or old.execution_family != str(trial.execution_family)
            or old.backend != trial.compute.backend
        ):
            raise RunControlError(f"stored work item does not match authoritative trial: {trial.trial_id}")
        provider_route = trial.agent_condition.client.kind if trial.agent_condition.client else "default"
        resource_class = str(trial.compute.resource_limits.get("resource_class", "default"))
        result.append(
            TrialWorkItem(
                work_id=new_entity_id(EntityKind.WORK_ITEM) if old is None else validate_uuidv7(old.work_id),
                work_key=EntityKey(f"{trial.ordinal:04d}-{trial.trial_key}"),
                run_id=plan.run_id,
                plan_id=plan.plan_id,
                trial_id=trial.trial_id,
                ordinal=trial.ordinal,
                execution_family=trial.execution_family,
                backend=trial.compute.backend,
                provider_route=provider_route,
                model_route=trial.agent_condition.model,
                resource_class=resource_class,
                retry_policy=retry_policy,
                state=WorkItemState.PLANNED if old is None else WorkItemState(old.state),
                created_at=plan.created_at,
                available_at=plan.created_at,
            )
        )
    return tuple(result)


def _dispatch_until_quiet(
    scheduler: LocalScheduler,
    worker: Worker,
    *,
    owner: str,
    now: datetime,
) -> tuple[SchedulerRunReport, dict[str, int]]:
    report = scheduler.dispatch_once(worker, owner=owner, now=now)
    totals = {
        "leased": report.leased_count,
        "succeeded": report.succeeded_count,
        "failed": report.failed_count,
        "retried": report.retried_count,
        "cancelled": report.cancelled_count,
        "unknown": report.unknown_count,
    }
    while not report.idle:
        if report.next_available_at is not None and report.next_available_at > now:
            break
        report = scheduler.dispatch_once(worker, owner=owner, now=datetime.now(UTC))
        for name, value in (
            ("leased", report.leased_count),
            ("succeeded", report.succeeded_count),
            ("failed", report.failed_count),
            ("retried", report.retried_count),
            ("cancelled", report.cancelled_count),
            ("unknown", report.unknown_count),
        ):
            totals[name] += value
    return report, totals


def _resolve_local_execution(
    plan: RunPlan,
    evidence: EvidenceRunStore,
    operational: OperationalStore,
    tasks_root: Path | None,
) -> ResolvedExecution:
    families = {str(trial.execution_family) for trial in plan.trials}
    if families != {"artifact"}:
        raise RunControlError(f"unsupported execution family for local start: {', '.join(sorted(families))}")
    backends = {str(trial.compute.backend) for trial in plan.trials}
    if backends != {"local"}:
        raise RunControlError(f"no local worker is available for backend: {', '.join(sorted(backends))}")
    if tasks_root is None:
        raise RunControlError("local artifact execution requires --tasks-root for run start or resume")
    selected_root = Path(tasks_root).expanduser().absolute()
    if not selected_root.is_dir():
        raise RunControlError(f"tasks root is not a directory: {selected_root}")
    tasks = _load_planned_tasks(plan, selected_root)
    temporary = TemporaryDirectory(prefix=f"aec-bench-{plan.run_id}-")
    runtime = LocalTaskRuntime(
        work_root=Path(temporary.name) / "work",
        artifact_root=Path(temporary.name) / "artifacts",
    )
    adapter = ArtifactTrialAdapter(
        evidence_store=evidence,
        operational_store=operational,
        plan=plan,
        runtime=runtime,
        tasks=tasks,
        verify=True,
    )
    return ResolvedExecution(worker=adapter, backends={}, cleanup=temporary)


def _preflight_local_plan(plan: RunPlan, tasks_root: Path | None) -> None:
    """Validate local family, backend, and exact repository snapshots before writes."""

    families = {str(trial.execution_family) for trial in plan.trials}
    if families != {"artifact"}:
        raise RunControlError(f"unsupported execution family for local start: {', '.join(sorted(families))}")
    backends = {str(trial.compute.backend) for trial in plan.trials}
    if backends != {"local"}:
        raise RunControlError(f"no local worker is available for backend: {', '.join(sorted(backends))}")
    if tasks_root is None:
        raise RunControlError("local artifact execution requires --tasks-root for run start or resume")
    selected_root = Path(tasks_root).expanduser().absolute()
    if not selected_root.is_dir():
        raise RunControlError(f"tasks root is not a directory: {selected_root}")
    _load_planned_tasks(plan, selected_root)


def _load_planned_tasks(plan: RunPlan, tasks_root: Path) -> list[ResolvedTaskInstance]:
    """Resolve each task by its saved snapshot coordinate and verify its bytes."""

    candidates = tuple(
        sorted(task_file.parent for task_file in tasks_root.rglob("task.toml") if not task_file.is_symlink())
    )
    tasks: list[ResolvedTaskInstance] = []
    seen: set[str] = set()
    for trial in plan.trials:
        reference = trial.task_release
        task_id = str(reference.task_id)
        if task_id in seen:
            continue
        seen.add(task_id)
        if isinstance(reference, RepositoryTaskSnapshotRef):
            instance_dir = (tasks_root / reference.task_id).absolute()
        else:
            instance_dir = None
            for path in candidates:
                try:
                    candidate = load_task_definition(path, tasks_root)
                except (LoadError, OSError, ValueError):
                    continue
                if candidate.task_id == task_id:
                    instance_dir = path
                    break
            if instance_dir is None:
                raise RunControlError(f"cannot locate planned task snapshot: {task_id}")
        assert instance_dir is not None
        try:
            task = load_task_definition(instance_dir, tasks_root)
            resolved = resolve_instance_paths(task, instance_dir)
            assert_task_snapshot_matches_directory(reference=reference, task_dir=resolved.instance_dir)
        except (LoadError, OSError, ValueError, TaskSnapshotError) as error:
            raise RunControlError(f"cannot validate planned task {task_id}: {error}") from error
        tasks.append(resolved)
    return tasks


__all__ = ("ResolvedExecution", "RunControlError", "RunControlResult", "WorkerResolver", "start_or_resume_run")
