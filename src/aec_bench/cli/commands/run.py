# ABOUTME: CLI run command for Harbor experiments and portable run-package transfer.
# ABOUTME: Preserves config and inline invocation while adding explicit export and import modes.

from __future__ import annotations

import time
from datetime import UTC, datetime
from getpass import getuser
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast

import typer
import yaml

if TYPE_CHECKING:
    from aec_bench.contracts.experiment_manifest import ExperimentManifest

from aec_bench.cli.commands.config import resolve_path
from aec_bench.cli.optional_dependencies import require_optional_extra
from aec_bench.cli.output import console, emit, print_success
from aec_bench.harness.model_execution.llm_reviewer import (
    ReviewerEndpointConfig,
    ReviewerRunConfig,
    load_reviewer_config,
    reviewer_config_from_manifest,
)


def export_package(
    run_id: str = typer.Argument(help="Published run ID"),
    output: Path = typer.Option(..., "--output", "-o", help="Output .tar.zst path"),
    ledger_root: str | None = typer.Option(None, "--ledger-root", help="Ledger directory"),
) -> None:
    """Export one published run as exact portable archive bytes."""

    start = time.monotonic()
    from aec_bench.ledger.run_package import export_run_package

    resolved_ledger = resolve_path("ledger_root", cli_override=ledger_root)
    try:
        reference = export_run_package(ledger_root=resolved_ledger, run_id=run_id, output=output)
    except (FileNotFoundError, FileExistsError, ValueError) as error:
        emit("run export", data=None, errors=[str(error)], start_time=start)
        raise typer.Exit(1) from error
    emit(
        "run export",
        data={"run_id": run_id, "output": str(output), "artifact": reference.model_dump(mode="json")},
        start_time=start,
    )


def import_package(
    archive: Path = typer.Argument(help="Portable .tar.zst run package"),
    ledger_root: str | None = typer.Option(None, "--ledger-root", help="Ledger directory"),
) -> None:
    """Verify and import one portable run package."""

    start = time.monotonic()
    from aec_bench.ledger.run_package import import_run_package

    if not archive.is_file():
        emit("run import", data=None, errors=[f"run package not found: {archive}"], start_time=start)
        raise typer.Exit(1)
    resolved_ledger = resolve_path("ledger_root", cli_override=ledger_root)
    try:
        package, reference = import_run_package(ledger_root=resolved_ledger, data=archive.read_bytes())
    except ValueError as error:
        emit("run import", data=None, errors=[str(error)], start_time=start)
        raise typer.Exit(1) from error
    emit(
        "run import",
        data={
            "run_id": package.run_plan.run_manifest.run_id,
            "artifact": reference.model_dump(mode="json"),
        },
        start_time=start,
    )


def run_experiment(
    config: Path | None = typer.Option(None, "--config", "-c", help="Experiment config YAML"),
    tasks_root: str | None = typer.Option(None, "--tasks-root", help="Tasks directory"),
    tasks_path: str | None = typer.Argument(None, help="Task path (simple invocation)"),
    package_value: str | None = typer.Argument(None, help="Run ID or archive path for export/import"),
    comparison_value: str | None = typer.Argument(None, help="Second run selector for `run diff`"),
    model: str | None = typer.Option(None, "--model", help="Model name"),
    adapter: str = typer.Option(
        "tool_loop",
        "--adapter",
        "--harness",
        help="Agent harness: tool_loop, pydantic_ai, direct, rlm, lambda-rlm, deepseek_harness",
    ),
    backend: str = typer.Option(
        "modal",
        "--backend",
        "-b",
        help="Harbor execution backend: modal, morph, e2b, daytona, docker.",
    ),
    repetitions: int = typer.Option(1, "--repetitions", "-n", help="Repetitions"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show plan without executing"),
    no_verify: bool = typer.Option(False, "--no-verify", help="Skip verification (agent-only run)"),
    reviewer: bool = typer.Option(False, "--reviewer", help="Run the post-verifier LLM reviewer stage"),
    reviewer_model: str | None = typer.Option(None, "--reviewer-model", help="Single reviewer model name"),
    reviewer_models_config: Path | None = typer.Option(
        None,
        "--reviewer-models-config",
        help="JSON/YAML reviewer model endpoint config",
    ),
    fail_on_reviewer_error: bool = typer.Option(
        False,
        "--fail-on-reviewer-error",
        help="Fail the run when the reviewer stage cannot complete",
    ),
    output: Path | None = typer.Option(None, "--output", "-o", help="Exported .tar.zst path"),
    ledger_root: str | None = typer.Option(None, "--ledger-root", help="Ledger directory"),
    store_root: str | None = typer.Option(None, "--store-root", help="Evidence run store directory"),
    observations: Path | None = typer.Option(None, "--observations", help="JSON trial outcomes for `run reconcile`"),
    cancellation_requested: bool = typer.Option(
        False,
        "--cancellation-requested",
        help="Account reconciled cancellations as a cancelled run",
    ),
    operational_store_path: Path | None = typer.Option(
        None,
        "--operational-store",
        help="Explicit SQLite operational store for run control and status",
    ),
    plan_root: Path | None = typer.Option(
        None,
        "--plan-root",
        help="Explicit portable run-plan root for run control and status",
    ),
) -> None:
    """Run an experiment.

    Two invocation styles:

      aec-bench run --config experiment.yaml --tasks-root ../tasks

      aec-bench run ../tasks/mechanical/heat-load --model claude-sonnet-4-20250514

    Returns (dry-run): experiment_id, selected_tasks, planned_trials, agents,
    repetitions, trials list (trial_id, task_id, agent per trial).

    Returns (live run): experiment_id, job_dir, imported, duplicates.

    Examples:
      aec-bench run tasks/electrical/voltage-drop --model gpt-4.1-mini --dry-run
      aec-bench run export run-001 --output run-package.tar.zst
      aec-bench run import run-package.tar.zst
      aec-bench --json run --config experiment.yaml | jq '.data.experiment_id'
    """
    if tasks_path == "status":
        _status_run(
            selector=package_value,
            operational_store_path=operational_store_path,
            plan_root=plan_root,
        )
        return
    if tasks_path == "cancel":
        _cancel_run(selector=package_value, operational_store_path=operational_store_path)
        return
    if tasks_path in {"start", "resume"}:
        _start_or_resume_run(
            operation=cast(Literal["start", "resume"], tasks_path),
            selector=package_value,
            tasks_root=tasks_root,
            operational_store_path=operational_store_path,
            plan_root=plan_root,
        )
        return
    if tasks_path in {"plan", "inspect", "diff", "reconcile"}:
        _review_run(
            operation=tasks_path,
            selector=package_value,
            comparison_selector=comparison_value,
            config=config,
            tasks_root=tasks_root,
            no_verify=no_verify,
            store_root=store_root,
            observations=observations,
            cancellation_requested=cancellation_requested,
        )
        return
    if tasks_path == "export":
        if package_value is None or output is None:
            raise typer.BadParameter("run export requires <run-id> and --output <path>")
        export_package(run_id=package_value, output=output, ledger_root=ledger_root)
        return
    if tasks_path == "import":
        if package_value is None:
            raise typer.BadParameter("run import requires <archive-path>")
        import_package(archive=Path(package_value), ledger_root=ledger_root)
        return
    if package_value is not None:
        raise typer.BadParameter(f"unexpected run argument: {package_value}")
    start = time.monotonic()
    reviewer_config = _reviewer_config_from_cli(
        enabled=reviewer,
        model=reviewer_model,
        models_config=reviewer_models_config,
        fail_on_error=fail_on_reviewer_error,
    )

    if config is not None:
        _run_from_config(
            config,
            tasks_root=tasks_root,
            dry_run=dry_run,
            start=start,
            no_verify=no_verify,
            reviewer_config=reviewer_config,
        )
    elif tasks_path is not None and model is not None:
        _run_inline(
            tasks_path=tasks_path,
            model=model,
            adapter=adapter,
            backend=backend,
            repetitions=repetitions,
            tasks_root=tasks_root,
            dry_run=dry_run,
            start=start,
            no_verify=no_verify,
            reviewer_config=reviewer_config,
        )
    else:
        emit(
            "run",
            data=None,
            errors=["provide --config <file> or <tasks-path> --model <name>"],
            start_time=start,
        )
        return


def _status_run(
    *,
    selector: str | None,
    operational_store_path: Path | None,
    plan_root: Path | None,
) -> None:
    """Emit one read-only operational projection for an explicit run."""

    start = time.monotonic()
    if selector is None:
        emit("run status", data=None, errors=["run status requires <run-id>"], start_time=start)
        return
    if operational_store_path is None or plan_root is None:
        emit(
            "run status",
            data=None,
            errors=["run status requires --operational-store and --plan-root"],
            start_time=start,
        )
        return
    from aec_bench.execution.operational.store import OperationalStoreError
    from aec_bench.harness.run_progress import load_run_progress, present_run_progress
    from aec_bench.ledger.evidence_run_store import EvidenceRunStoreError

    try:
        progress = load_run_progress(
            selector,
            operational_store_path=operational_store_path,
            plan_root=plan_root,
        )
    except (EvidenceRunStoreError, OperationalStoreError, ValueError) as error:
        emit("run status", data=None, errors=[str(error)], start_time=start)
        return
    data = present_run_progress(progress).model_dump(mode="json")
    emit("run status", data=data, start_time=start, human_renderer=_render_status_human)


def _start_or_resume_run(
    *,
    operation: Literal["start", "resume"],
    selector: str | None,
    tasks_root: str | None,
    operational_store_path: Path | None,
    plan_root: Path | None,
) -> None:
    """Run one persisted plan through the current local scheduler composition."""

    start = time.monotonic()
    if selector is None:
        emit(f"run {operation}", data=None, errors=[f"run {operation} requires <run-id>"], start_time=start)
        return
    if operational_store_path is None or plan_root is None:
        emit(
            f"run {operation}",
            data=None,
            errors=[f"run {operation} requires --operational-store and --plan-root"],
            start_time=start,
        )
        return
    from aec_bench.harness.run_control import RunControlError, start_or_resume_run

    try:
        result = start_or_resume_run(
            run_selector=selector,
            operation=operation,
            plan_root=plan_root,
            operational_store_path=operational_store_path,
            tasks_root=None if tasks_root is None else Path(tasks_root),
        )
    except (RunControlError, ValueError) as error:
        emit(f"run {operation}", data=None, errors=[str(error)], start_time=start)
        return
    emit(f"run {operation}", data=result.as_dict(), start_time=start)


def _render_status_human(data: object) -> None:
    """Render the flat status fields in terminal-friendly form."""

    if not isinstance(data, dict):
        return
    for field in (
        "run_id",
        "plan_id",
        "status",
        "planned",
        "succeeded",
        "failed",
        "running",
        "queued",
        "unknown",
        "cancelled",
        "retries",
    ):
        if field in data:
            console.print(f"{field}: {data[field]}")


def _cancel_run(*, selector: str | None, operational_store_path: Path | None) -> None:
    """Request cancellation of queued and active work in one operational run."""

    start = time.monotonic()
    if selector is None:
        emit("run cancel", data=None, errors=["run cancel requires <run-id>"], start_time=start)
        return
    if operational_store_path is None:
        emit("run cancel", data=None, errors=["run cancel requires --operational-store"], start_time=start)
        return
    from aec_bench.execution.operational.store import OperationalStoreError

    try:
        from aec_bench.execution.operational.store import OperationalStore

        store = OperationalStore.open_existing(operational_store_path)
        before = store.list_work_items(selector)
        queued_before = {item.work_id for item in before if item.state == "queued"}
        run = store.request_cancellation(selector)
        after = store.list_work_items(selector)
        attempts = {attempt.attempt_id: attempt for attempt in store.list_attempts_for_run(selector)}
        submission_attempts = {item.attempt_id for item in store.list_backend_submissions_for_run(selector)}
        submitted_work_ids = {
            attempt.work_id for attempt_id, attempt in attempts.items() if attempt_id in submission_attempts
        }
        pending = sum(item.state == "cancel_requested" and item.work_id in submitted_work_ids for item in after)
        data = {
            "run_id": selector,
            "status": run.status,
            "queued_cancelled": sum(item.work_id in queued_before and item.state == "cancelled" for item in after),
            "active_work_cancel_requested": sum(item.state == "cancel_requested" for item in after),
            "backend_cancellation_pending": pending,
            "unknown_reconciliation": sum(attempt.state == "unknown" for attempt in attempts.values()),
        }
    except (OperationalStoreError, ValueError) as error:
        emit("run cancel", data=None, errors=[str(error)], start_time=start)
        return
    emit("run cancel", data=data, start_time=start, human_renderer=_render_cancel_human)


def _render_cancel_human(data: object) -> None:
    """Render cancellation state without implying backend cancellation completed."""

    if not isinstance(data, dict):
        return
    for field in (
        "run_id",
        "status",
        "queued_cancelled",
        "active_work_cancel_requested",
        "backend_cancellation_pending",
        "unknown_reconciliation",
    ):
        if field in data:
            console.print(f"{field}: {data[field]}")


def _review_run(
    *,
    operation: str,
    selector: str | None,
    comparison_selector: str | None,
    config: Path | None,
    tasks_root: str | None,
    no_verify: bool,
    store_root: str | None,
    observations: Path | None,
    cancellation_requested: bool,
) -> None:
    start = time.monotonic()
    from aec_bench.cli.commands.run_review import diff_data, inspect_data, load_run, plan_data, reconcile_data
    from aec_bench.ledger.evidence_run_store import EvidenceRunStoreError

    if config is not None and operation != "plan":
        emit(f"run {operation}", data=None, errors=["--config is supported only by 'run plan'"], start_time=start)
        return
    if config is not None and selector is not None:
        emit("run plan", data=None, errors=["run plan accepts --config or a run selector, not both"], start_time=start)
        return
    if selector is None and config is None:
        emit(f"run {operation}", data=None, errors=[f"run {operation} requires a run key or UUID"], start_time=start)
        return
    resolved_store = resolve_path("ledger_root", cli_override=store_root)
    try:
        if operation == "plan" and config is not None:
            data = _persist_plan_from_config(
                config,
                tasks_root=tasks_root,
                no_verify=no_verify,
                store_root=resolved_store,
            )
        else:
            if selector is None:
                raise ValueError("run plan requires --config <path> or a run key or UUID")
            selected = load_run(resolved_store, selector)
            if operation == "plan":
                data = plan_data(selected)
            elif operation == "inspect":
                data = inspect_data(selected, observations)
            elif operation == "reconcile":
                if observations is None:
                    raise ValueError("run reconcile requires --observations <path>")
                data = reconcile_data(
                    selected,
                    observations,
                    cancellation_requested=cancellation_requested,
                )
            else:
                if comparison_selector is None:
                    raise ValueError("run diff requires two run keys or UUIDs")
                comparison = load_run(resolved_store, comparison_selector)
                data = diff_data(selected, comparison, left_selector=selector, right_selector=comparison_selector)
    except (EvidenceRunStoreError, OSError, ValueError) as error:
        emit(f"run {operation}", data=None, errors=[str(error)], start_time=start)
        return
    emit(f"run {operation}", data=data, start_time=start, human_renderer=_render_review)


def _persist_plan_from_config(
    config_path: Path,
    *,
    tasks_root: str | None,
    no_verify: bool,
    store_root: Path,
) -> dict[str, Any]:
    """Resolve an artifact manifest, persist its spec and ready plan, and return both views."""

    from aec_bench.cli.commands.run_review import plan_data

    manifest, resolved_tasks = _load_manifest_config(config_path, tasks_root=tasks_root, no_verify=no_verify)
    from aec_bench.contracts.execution_policy import ExecutionPolicy
    from aec_bench.contracts.identity import EntityIdentity, EntityKey, EntityKind, new_entity_id
    from aec_bench.contracts.resolved_run import resolve_run_spec
    from aec_bench.contracts.run_plan import TaskPlanningProfile, plan_run
    from aec_bench.contracts.task_definition import TaskDefinition, TaskMetadata
    from aec_bench.harness.compilation.task_snapshot import resolve_task_snapshots
    from aec_bench.harness.scheduler import select_manifest_task_values
    from aec_bench.ledger.evidence_run_store import EvidenceRunStore
    from aec_bench.tasks.registry import TaskRegistry
    from aec_bench.tasks.selector import validate_execution_tasks

    registry = TaskRegistry(tasks_root=resolved_tasks)
    registry.reload()
    selected = select_manifest_task_values(
        registry.all(),
        manifest,
        project_root=resolved_tasks.parent,
        tasks_root=resolved_tasks,
    )
    if not selected:
        raise ValueError("no tasks matched the manifest selector")
    validate_execution_tasks(selected, permitted_visibility=manifest.tasks.visibility_filter)
    if any(not isinstance(task, TaskDefinition) for task in selected):
        raise ValueError(
            "run plan --config requires identity-bearing artifact task releases; "
            "Interactive World and lifecycle task values are not yet supported by this planner boundary"
        )
    task_definitions = tuple(task for task in selected if isinstance(task, TaskDefinition))
    for task in task_definitions:
        if task.identity is None:
            raise ValueError("run plan --config requires every selected task to declare an identity")
    task_releases = resolve_task_snapshots(
        task_refs=tuple(task.task_id for task in task_definitions),
        tasks_root=resolved_tasks,
    )
    created_at = datetime.now(UTC)
    experiment_identity = EntityIdentity(
        id=new_entity_id(EntityKind.EXPERIMENT),
        key=EntityKey(manifest.experiment_id),
        version=1,
    )
    run_id = new_entity_id(EntityKind.RUN)
    occurrence = created_at.strftime("%Y%m%d-%H%M%S-%f")
    run_identity = EntityIdentity(
        id=run_id,
        key=EntityKey(f"{manifest.experiment_id}-run-{occurrence}"),
        version=1,
    )
    from aec_bench.contracts.experiment_manifest import AgentCondition

    conditions = tuple(
        AgentCondition(
            identity=EntityIdentity(
                id=new_entity_id(EntityKind.AGENT_CONDITION),
                key=EntityKey(agent.name),
                version=1,
            ),
            adapter=agent.adapter,
            model=agent.model,
            client=agent.client,
            system_prompt=agent.system_prompt,
            parameters=agent.parameters,
        )
        for agent in manifest.agents
    )
    spec = resolve_run_spec(
        manifest,
        task_releases=task_releases,
        agent_conditions=conditions,
        experiment_identity=experiment_identity,
        run_identity=run_identity,
        created_at=created_at,
        created_by=getuser() or "unknown",
        execution_policy=ExecutionPolicy(max_concurrency=1),
    )
    profiles = {}
    for task in task_definitions:
        identity = task.identity
        if identity is None:
            raise ValueError("run plan --config requires every selected task to declare an identity")
        profiles[identity.id] = TaskPlanningProfile(
            metadata=TaskMetadata(
                identity=identity,
                lifecycle=task.lifecycle,
                visibility=task.visibility,
            ),
            execution_family="artifact",
        )
    plan = plan_run(
        spec,
        plan_identity=EntityIdentity(
            id=new_entity_id(EntityKind.PLAN),
            key=EntityKey(f"{run_identity.key}-plan"),
            version=1,
        ),
        created_at=created_at,
        task_profiles=profiles,
        validate_combination=_validate_artifact_combination,
    )
    store = EvidenceRunStore(store_root)
    store.create_run(spec)
    store.write_draft_plan(run_identity, plan.model_copy(update={"state": "draft"}))
    store.promote_ready_plan(run_identity, plan)
    return plan_data(store.read_run(run_identity))


def _validate_artifact_combination(task_release: object, condition: object, execution_family: str) -> None:
    """Keep the config planner honest: this boundary creates artifact-only plans."""

    del task_release, condition
    if execution_family != "artifact":
        raise ValueError(f"run plan --config does not support execution family: {execution_family}")


def _load_manifest_config(
    config_path: Path,
    *,
    tasks_root: str | None,
    no_verify: bool = False,
) -> tuple[ExperimentManifest, Path]:
    """Load one config with prompt files and dataset selectors resolved."""

    if not config_path.exists():
        raise ValueError(f"config file not found: {config_path}")
    config_dir = config_path.parent.resolve()
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    resolved_tasks = resolve_path("tasks_root", cli_override=tasks_root)
    raw = _resolve_interactive_dataset_alias(raw, project_root=resolved_tasks.parent)
    from aec_bench.contracts.experiment_manifest import ExperimentManifest

    manifest = ExperimentManifest.model_validate(raw)
    if no_verify:
        manifest = manifest.model_copy(update={"disable_verification": True})
    resolved_agents = []
    for agent in manifest.agents:
        if agent.system_prompt_file is not None:
            prompt_path = config_dir / agent.system_prompt_file
            if not prompt_path.exists():
                raise ValueError(f"system prompt not found: {prompt_path}")
            agent = agent.model_copy(
                update={
                    "system_prompt": prompt_path.read_text(encoding="utf-8"),
                    "system_prompt_file": None,
                }
            )
        resolved_agents.append(agent)
    return manifest.model_copy(update={"agents": resolved_agents}), resolved_tasks


def _render_review(data: object) -> None:
    import json

    if isinstance(data, dict) and isinstance(data.get("plan"), dict):
        from aec_bench.contracts.identity import format_display_ref

        run = data.get("run", {})
        plan = data["plan"]
        summary = data.get("summary", plan.get("summary", {}))
        run_identity = run.get("run_identity", {})
        run_ref = (
            format_display_ref(run_identity["key"], run_identity["id"])
            if run_identity.get("key") and run_identity.get("id")
            else "unknown"
        )
        console.print(f"Run: {run_ref}")
        console.print(f"Experiment: {run.get('experiment_identity', {}).get('key', 'unknown')}")
        console.print(f"Plan: {summary.get('total_trials', 0)} trials")
        console.print(f"Tasks: {summary.get('selected_task_count', 0)}")
        console.print(f"Agents: {summary.get('agent_condition_count', 0)}")
        console.print(f"Repetitions: {summary.get('repetitions', 0)}")
        console.print(f"Families: {summary.get('trials_by_execution_family', {})}")
        console.print(f"Backends: {summary.get('trials_by_backend', {})}")
        console.print(f"Visibility: {summary.get('tasks_by_visibility', {})}")
        console.print(f"Deprecated tasks: {summary.get('deprecated_task_count', 0)}")
        console.print(f"Status: {plan.get('state', 'unknown')}")
        return
    if isinstance(data, dict) and "plan_trial_count" in data:
        from aec_bench.contracts.identity import format_display_ref

        run_identity = data.get("run_identity", {})
        run_ref = (
            format_display_ref(run_identity["key"], run_identity["id"])
            if run_identity.get("key") and run_identity.get("id")
            else "unknown"
        )
        console.print(f"Run: {run_ref}")
        console.print(f"State: {data.get('state', 'unknown')}")
        console.print(f"Trials: {data.get('plan_trial_count', 0)}")
        console.print(f"Task releases: {len(data.get('task_releases', []))}")
        console.print(f"Agent conditions: {len(data.get('agent_conditions', []))}")
        console.print(f"Plan readiness: {data.get('plan_readiness', 'unknown')}")
        provider_identity = data.get("provider_identity", {})
        console.print(f"Requested provider: {provider_identity.get('requested')}")
        console.print(f"Observed provider: {provider_identity.get('observed')}")
        accounting = data.get("accounting")
        if isinstance(accounting, dict):
            console.print(f"Result completeness: {accounting.get('completeness', 'unknown')}")
            console.print(f"Validity: {accounting.get('validity', 'unknown')}")
            console.print(f"Missing trials: {len(accounting.get('missing_trial_ids', []))}")
            console.print(f"Conflicting duplicates: {len(accounting.get('conflicting_duplicate_trial_ids', []))}")
        else:
            console.print("Result completeness: unknown (no observations supplied)")
        return
    if isinstance(data, dict) and "changes" in data:
        changes = data["changes"]
        console.print(f"Diff: {data.get('left', 'unknown')} -> {data.get('right', 'unknown')}")
        if not changes:
            console.print("Unchanged")
        else:
            console.print("Changed:")
            for change in changes:
                console.print(f"  {change['path']}: {change['before']} -> {change['after']}")
            stable = data.get("unchanged", [])
            if stable:
                console.print("Unchanged:")
                for path in stable[:10]:
                    console.print(f"  {path}")
        return
    if isinstance(data, dict) and "counts" in data and "status" in data:
        counts = data["counts"]
        for name in (
            "planned",
            "succeeded",
            "failed",
            "cancelled",
            "timed_out",
            "invalid",
            "missing",
            "duplicate",
            "unexpected",
        ):
            console.print(f"{name.replace('_', ' ').title()}: {counts.get(name, 0)}")
        console.print(f"Run status: {data['status']}")
        console.print(f"Validity: {data.get('validity', 'unknown')}")
        return
    console.print(json.dumps(data, indent=2, default=str))


def _run_from_config(
    config_path: Path,
    *,
    tasks_root: str | None,
    dry_run: bool,
    start: float,
    no_verify: bool = False,
    reviewer_config: ReviewerRunConfig | None = None,
) -> None:
    if not config_path.exists():
        emit("run", data=None, errors=[f"config file not found: {config_path}"], start_time=start)
        return

    config_dir = config_path.parent.resolve()
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    resolved_tasks = resolve_path("tasks_root", cli_override=tasks_root)
    raw = _resolve_interactive_dataset_alias(raw, project_root=resolved_tasks.parent)

    from aec_bench.contracts.experiment_manifest import ExperimentManifest

    manifest = ExperimentManifest.model_validate(raw)
    if no_verify:
        manifest = manifest.model_copy(update={"disable_verification": True})

    resolved_agents = []
    for agent in manifest.agents:
        if agent.system_prompt_file is not None:
            prompt_path = config_dir / agent.system_prompt_file
            if not prompt_path.exists():
                emit(
                    "run",
                    data=None,
                    errors=[f"system prompt not found: {prompt_path}"],
                    start_time=start,
                )
                return
            agent = agent.model_copy(
                update={
                    "system_prompt": prompt_path.read_text(encoding="utf-8"),
                    "system_prompt_file": None,
                }
            )
        resolved_agents.append(agent)
    manifest = manifest.model_copy(update={"agents": resolved_agents})

    _execute_manifest(
        manifest,
        tasks_root=resolved_tasks,
        dry_run=dry_run,
        start=start,
        reviewer_config=reviewer_config,
    )


def _run_inline(
    *,
    tasks_path: str,
    model: str,
    adapter: str,
    backend: str = "modal",
    repetitions: int,
    tasks_root: str | None,
    dry_run: bool,
    start: float,
    no_verify: bool = False,
    reviewer_config: ReviewerRunConfig | None = None,
) -> None:
    from aec_bench.contracts.experiment_manifest import (
        AgentConfig,
        ComputeConfig,
        ExperimentManifest,
        TaskSelector,
    )

    resolved_tasks = resolve_path("tasks_root", cli_override=tasks_root)
    tasks_abs = Path(tasks_path).resolve()
    try:
        relative = tasks_abs.relative_to(resolved_tasks).as_posix()
    except ValueError:
        relative = tasks_path.rstrip("/")
    # Match both leaf tasks (exact path) and parent dirs (with sub-instances)
    task_patterns = [relative, relative + "/*"]

    manifest = ExperimentManifest(
        experiment_id=f"inline-{model.split('/')[-1].split('-')[0]}",
        name=f"Inline run: {model}",
        tasks=TaskSelector(include_patterns=task_patterns),
        agents=[
            AgentConfig(
                name=f"{adapter}-{model.split('-')[0]}",
                adapter=adapter,
                model=model,
            )
        ],
        compute=ComputeConfig(backend=backend),
        repetitions=repetitions,
        disable_verification=no_verify,
    )

    resolved_tasks = resolve_path("tasks_root", cli_override=tasks_root)
    _execute_manifest(
        manifest,
        tasks_root=resolved_tasks,
        dry_run=dry_run,
        start=start,
        reviewer_config=reviewer_config,
    )


def _execute_manifest(
    manifest: ExperimentManifest,
    *,
    tasks_root: Path,
    dry_run: bool,
    start: float,
    reviewer_config: ReviewerRunConfig | None = None,
) -> None:
    effective_reviewer_config = reviewer_config or reviewer_config_from_manifest(manifest.reviewer)
    from aec_bench.harness.scheduler import select_manifest_task_values
    from aec_bench.tasks.registry import TaskRegistry
    from aec_bench.trials import plan_trials

    registry = TaskRegistry(tasks_root=tasks_root)
    registry.reload()
    project_root = tasks_root.parent
    selected_tasks = select_manifest_task_values(
        registry.all(),
        manifest,
        project_root=project_root,
        tasks_root=tasks_root,
    )

    if not selected_tasks:
        if any(agent.adapter != "prime-agent" for agent in manifest.agents):
            require_optional_extra("Experiment execution support", "execution", ("harbor",))
        emit(
            "run",
            data=None,
            errors=["no tasks matched the manifest selector"],
            start_time=start,
        )
        return

    plan = plan_trials(
        manifest.experiment_id,
        tasks=selected_tasks,
        agents=manifest.agents,
        compute=manifest.compute,
        repetitions=manifest.repetitions,
        permitted_visibility=manifest.tasks.visibility_filter,
    )

    from aec_bench.contracts.task_definition import TaskDefinition
    from aec_bench.harness.world_routing import validate_world_routes
    from aec_bench.worlds.tasks import WorldTask

    world_tasks = [task for task in selected_tasks if isinstance(task, WorldTask)]
    artifact_tasks = [task for task in selected_tasks if isinstance(task, TaskDefinition)]
    world_trials = [trial for trial in plan if trial.task_id in {task.task_id for task in world_tasks}]
    if world_tasks:
        validate_world_routes(world_tasks, world_trials)
    needs_harbor = bool(artifact_tasks) or any(trial.agent.adapter == "deepseek_harness" for trial in world_trials)
    morph = manifest.compute.backend == "morph"
    if needs_harbor:
        require_optional_extra("Experiment execution support", "execution", ("harbor",))

    if needs_harbor:
        from aec_bench.cli.harbor_environment import HARBOR_RUN_BACKENDS

        if manifest.compute.backend not in HARBOR_RUN_BACKENDS:
            supported = ", ".join(HARBOR_RUN_BACKENDS)
            emit(
                "run",
                data=None,
                errors=[
                    f"backend '{manifest.compute.backend}' is not supported by 'aec-bench run'; "
                    f"choose one of: {supported}"
                ],
                start_time=start,
            )
            return

    if dry_run:
        plan_data = {
            "experiment_id": manifest.experiment_id,
            "backend": manifest.compute.backend,
            "selected_tasks": len(selected_tasks),
            "planned_trials": len(plan),
            "agents": [a.name for a in manifest.agents],
            "repetitions": manifest.repetitions,
            "trials": [{"trial_id": t.trial_id, "task_id": t.task_id, "agent": t.agent.name} for t in plan],
            "reviewer": _reviewer_plan(effective_reviewer_config),
        }

        def _render_dry_run(d: dict[str, Any]) -> None:
            console.print(f"[bold]Dry Run: {d['experiment_id']}[/bold]")
            console.print(f"  Backend:    {d['backend']}")
            console.print(f"  Tasks:      {d['selected_tasks']}")
            console.print(f"  Agents:     {', '.join(d['agents'])}")
            console.print(f"  Repetitions: {d['repetitions']}")
            console.print(f"  Total trials: [bold]{d['planned_trials']}[/bold]")

            from rich.table import Table

            table = Table(title="Planned Trials")
            table.add_column("Trial ID", style="dim")
            table.add_column("Task")
            table.add_column("Agent")

            for trial in d["trials"][:20]:
                table.add_row(trial["trial_id"], trial["task_id"], trial["agent"])

            if len(d["trials"]) > 20:
                table.add_row("...", f"({len(d['trials']) - 20} more)", "...")

            console.print(table)

        emit("run", plan_data, start_time=start, human_renderer=_render_dry_run)
        return

    modules: tuple[str, ...] = ()
    commands: tuple[str, ...] = ()
    extras: list[str] = []
    if needs_harbor and morph:
        modules = ("morphcloud",)
        extras.append("execution,morph")
    if world_tasks and any(trial.agent.adapter == "prime-agent" for trial in world_trials):
        modules = (*modules, "acp")
        commands = (*commands, "prime-agent")
        extras.append("prime-agent")
    if effective_reviewer_config is not None and effective_reviewer_config.enabled:
        modules = (*modules, "pydantic_ai")
        extras.append("local-agents")
    if modules:
        require_optional_extra("Experiment execution support", ",".join(extras), modules, commands)

    console.print(f"[bold]Running: {manifest.name}[/bold]")
    console.print(f"  {len(plan)} trials across {len(selected_tasks)} tasks")

    from aec_bench.harness.artifact_tasks import SingleAttemptSpec
    from aec_bench.harness.artifact_tasks import run_experiment as run_task_experiment
    from aec_bench.harness.harbor_runtime import HarborExperimentRuntime
    from aec_bench.harness.harbor_workflow import SynchronousHarborWorkflow
    from aec_bench.tasks.instance import resolve_instance_paths

    resolved_ledger = resolve_path("ledger_root")
    jobs_root = project_root / "jobs"

    records = []
    result = None
    if artifact_tasks:
        from aec_bench.cli.harbor_environment import resolve_harbor_environment_binding

        runtime = HarborExperimentRuntime(
            workflow=SynchronousHarborWorkflow(
                project_root=project_root,
                repo_root=project_root,
                tasks_root=tasks_root,
                ledger_root=resolved_ledger,
                jobs_root=jobs_root,
            ),
            manifest=manifest,
            config_path=project_root / f".aec-bench-{manifest.experiment_id}.yaml",
            environment_binding=resolve_harbor_environment_binding(manifest.compute.backend),
        )

        def _progress(snapshot: object) -> None:
            console.print(f"  [dim]{snapshot}[/dim]")

        runtime.progress_callback = _progress
        artifact_ids = {task.task_id for task in artifact_tasks}
        records.extend(
            run_task_experiment(
                runtime=runtime,
                tasks=[resolve_instance_paths(task, tasks_root / task.task_id) for task in artifact_tasks],
                trials=[trial for trial in plan if trial.task_id in artifact_ids],
                recipe=SingleAttemptSpec(),
                reviewer=reviewer_config,
                verify=not manifest.disable_verification,
            )
        )
        result = runtime.last_result
        if result is None:
            raise RuntimeError("Harbor experiment did not produce a workflow result")

    if world_tasks:
        import asyncio
        from functools import partial

        from aec_bench.harness.world_routing import run_selected_world
        from aec_bench.harness.world_trials import run_world_experiment
        from aec_bench.ledger.writer import write_trial_record

        records.extend(
            asyncio.run(
                run_world_experiment(
                    tasks=world_tasks,
                    trials=world_trials,
                    run_trial=partial(run_selected_world, work_root=jobs_root / manifest.experiment_id),
                    persist=partial(write_trial_record, ledger_root=resolved_ledger),
                )
            )
        )
    order = {trial.trial_id: index for index, trial in enumerate(plan)}
    records.sort(key=lambda record: order[record.trial_id])

    result_data = {
        "experiment_id": manifest.experiment_id,
        "job_dir": str(result.job_dir) if result is not None and result.job_dir else None,
        "imported": len(records),
        "duplicates": 0 if result is None else result.import_result.duplicate_trials,
        "reviewer": None if result is None else _reviewer_result_data(result.reviewer_result),
    }

    def _render_result(d: dict[str, Any]) -> None:
        print_success(f"Completed: {d['imported']} trials imported into ledger")

    emit("run", result_data, start_time=start, human_renderer=_render_result)


def _resolve_interactive_dataset_alias(raw: object, *, project_root: Path) -> object:
    """Replace one user-facing dataset selector with its exact reference before validation."""

    if not isinstance(raw, dict):
        return raw
    tasks = raw.get("tasks")
    if not isinstance(tasks, dict):
        return raw
    selector = tasks.get("dataset")
    if not isinstance(selector, str):
        return raw

    from aec_bench.config import load_config
    from aec_bench.dataset.publication import resolve_dataset

    config = load_config(project_root)
    resolved = resolve_dataset(
        datasets_root=config.datasets_root,
        selector=selector,
        project_root=project_root,
    )
    if resolved is None:
        raise ValueError(f"dataset selector did not resolve to a publication: {selector}")
    resolved_tasks = dict(tasks)
    resolved_tasks["dataset"] = resolved.reference.model_dump(mode="json")
    resolved_raw = dict(raw)
    resolved_raw["tasks"] = resolved_tasks
    return resolved_raw


def _reviewer_config_from_cli(
    *,
    enabled: bool,
    model: str | None,
    models_config: Path | None,
    fail_on_error: bool,
) -> ReviewerRunConfig | None:
    if models_config is not None:
        config = load_reviewer_config(models_config)
        return config.model_copy(update={"enabled": True, "fail_on_error": fail_on_error or config.fail_on_error})
    if model is not None:
        return ReviewerRunConfig(
            enabled=True,
            fail_on_error=fail_on_error,
            models=[
                ReviewerEndpointConfig(
                    name=model,
                    model=model,
                )
            ],
        )
    if enabled:
        return ReviewerRunConfig(enabled=True, fail_on_error=fail_on_error)
    return None


def _reviewer_plan(config: ReviewerRunConfig | None) -> dict[str, Any]:
    if config is None:
        return {"enabled": False, "required": False, "models": []}
    return {
        "enabled": config.enabled,
        "required": config.required,
        "models": [model.name for model in config.models],
        "fail_on_error": config.fail_on_error,
    }


def _reviewer_result_data(result: Any | None) -> dict[str, Any] | None:
    if result is None:
        return None
    return {
        "trial_count": result.trial_count,
        "complete_count": result.complete_count,
        "error_count": result.error_count,
        "skipped_count": result.skipped_count,
    }
