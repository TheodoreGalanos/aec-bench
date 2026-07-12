# ABOUTME: CLI commands for running the AEC-Bench meta-harness process runtime.
# ABOUTME: Parses process artifacts and delegates execution to library modules.

from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import typer
import yaml  # type: ignore[import-untyped]

from aec_bench.cli.output import emit, print_success
from aec_bench.meta_harness.autonomy import AutonomyConfig, run_autonomous_process
from aec_bench.meta_harness.evidence_lifecycle import (
    branch_evidence_lifecycle,
    prepare_evidence_checkpoint,
    read_evidence_lifecycle_state,
    revisit_evidence_checkpoint,
    submit_evidence_checkpoint,
)
from aec_bench.meta_harness.evidence_lifecycle_ablation import (
    inspect_lifecycle_ablation_plan,
    load_lifecycle_ablation_manifest,
    run_lifecycle_ablation,
)
from aec_bench.meta_harness.evidence_lifecycle_local import (
    LifecycleVisibilityPolicy,
    run_local_evidence_lifecycle_fresh_context,
    run_local_evidence_lifecycle_session,
)
from aec_bench.meta_harness.harbor_task import materialize_harbor_task_package
from aec_bench.meta_harness.logic_profile import evaluate_logic_profile
from aec_bench.meta_harness.model_runner import (
    build_intake_model_run_plan,
    build_operation_model_run_plan,
    build_review_model_run_plan,
    build_review_request,
    build_world_generation_model_run_plan,
    evaluate_with_review,
    load_model_endpoints,
    parse_model_endpoint,
    parse_review_response,
    run_intake_models,
    run_operation_models,
    run_review_models,
    run_world_generation_models,
)
from aec_bench.meta_harness.operation_orchestrator import run_operation_orchestrator
from aec_bench.meta_harness.operation_profile import apply_world_operation
from aec_bench.meta_harness.recipe import materialize_harness_comparison_recipe
from aec_bench.meta_harness.world_process import (
    apply_governance_decision,
    build_problem_brief_request,
    build_world_generation_request,
)
from aec_bench.meta_harness.world_runtime import run_process
from aec_bench.task_world_templates.materializer import verify_template_lifecycle

app = typer.Typer(help="Run meta-harness intake, world, operation, and governance processes.")


@app.command("lifecycle-start")
def lifecycle_start_command(
    package: Path = typer.Option(..., "--package", help="Materialized evidence-lifecycle package"),
    run_dir: Path = typer.Option(..., "--run-dir", help="Persistent lifecycle run directory"),
) -> None:
    """Release the next lifecycle checkpoint into its persistent workspace."""
    start = time.monotonic()
    result = prepare_evidence_checkpoint(package, run_dir)
    emit("meta-harness lifecycle-start", result, start_time=start)


@app.command("lifecycle-submit")
def lifecycle_submit_command(
    package: Path = typer.Option(..., "--package", help="Materialized evidence-lifecycle package"),
    run_dir: Path = typer.Option(..., "--run-dir", help="Persistent lifecycle run directory"),
) -> None:
    """Accept the active checkpoint submission without releasing future evidence."""
    start = time.monotonic()
    result = submit_evidence_checkpoint(package, run_dir)
    emit("meta-harness lifecycle-submit", result, start_time=start)


@app.command("lifecycle-status")
def lifecycle_status_command(
    package: Path = typer.Option(..., "--package", help="Materialized evidence-lifecycle package"),
    run_dir: Path = typer.Option(..., "--run-dir", help="Persistent lifecycle run directory"),
) -> None:
    """Read lifecycle state without advancing or accepting a checkpoint."""
    start = time.monotonic()
    result = read_evidence_lifecycle_state(package, run_dir)
    emit("meta-harness lifecycle-status", result, start_time=start)


@app.command("lifecycle-revisit")
def lifecycle_revisit_command(
    package: Path = typer.Option(..., "--package", help="Materialized evidence-lifecycle package"),
    run_dir: Path = typer.Option(..., "--run-dir", help="Persistent lifecycle run directory"),
    checkpoint_id: str = typer.Option(..., "--checkpoint-id", help="Submitted checkpoint to inspect"),
    reason: str = typer.Option(..., "--reason", help="Reason for revisiting the checkpoint"),
) -> None:
    """Inspect and log an immutable prior checkpoint without rewinding the run."""
    start = time.monotonic()
    result = revisit_evidence_checkpoint(
        package,
        run_dir,
        checkpoint_id=checkpoint_id,
        reason=reason,
    )
    emit("meta-harness lifecycle-revisit", result, start_time=start)


@app.command("lifecycle-branch")
def lifecycle_branch_command(
    package: Path = typer.Option(..., "--package", help="Materialized evidence-lifecycle package"),
    parent_run_dir: Path = typer.Option(..., "--parent-run-dir", help="Existing parent lifecycle run"),
    branch_run_dir: Path = typer.Option(..., "--branch-run-dir", help="New derived lifecycle run"),
    checkpoint_id: str = typer.Option(..., "--checkpoint-id", help="Submitted checkpoint to reopen"),
    branch_id: str = typer.Option(..., "--branch-id", help="Stable identity for the derived run"),
    reason: str = typer.Option(..., "--reason", help="Reason for branching from the checkpoint"),
) -> None:
    """Create an isolated lifecycle run by reopening one submitted checkpoint."""
    start = time.monotonic()
    result = branch_evidence_lifecycle(
        package,
        parent_run_dir,
        branch_run_dir,
        checkpoint_id=checkpoint_id,
        branch_id=branch_id,
        reason=reason,
    )
    emit("meta-harness lifecycle-branch", result, start_time=start)


@app.command("lifecycle-run-local")
def lifecycle_run_local_command(
    package: Path = typer.Option(..., "--package", help="Materialized evidence-lifecycle package"),
    run_dir: Path = typer.Option(..., "--run-dir", help="Persistent lifecycle run directory"),
    model: str = typer.Option(..., "--model", "-m", help="Model name for the lifecycle agent"),
    adapter: str = typer.Option("tool_loop", "--adapter", "-a", help="Local adapter kind"),
    mode: str = typer.Option(
        "persistent",
        "--mode",
        help="Execution mode: persistent (one conversation) or fresh-context (one per checkpoint)",
    ),
    process_id: str = typer.Option("process.lifecycle", "--process-id", help="Parent meta-harness process id"),
    max_turns: int = typer.Option(60, "--max-turns", min=1, help="Maximum model requests per model session"),
    visibility_policy: str | None = typer.Option(
        None,
        "--visibility-policy",
        help="Model-visible memory policy; defaults by execution mode",
    ),
) -> None:
    """Run all lifecycle checkpoints locally, persistent by default."""
    start = time.monotonic()
    if mode == "persistent":
        selected_visibility = _lifecycle_visibility_policy(
            visibility_policy or LifecycleVisibilityPolicy.PERSISTENT_CONTEXT.value
        )
        result = run_local_evidence_lifecycle_session(
            package_dir=package,
            run_dir=run_dir,
            model=model,
            adapter_kind=adapter,
            max_turns=max_turns,
            process_id=process_id,
            verifier=verify_template_lifecycle,
            visibility_policy=selected_visibility,
        )
    elif mode == "fresh-context":
        selected_visibility = _lifecycle_visibility_policy(
            visibility_policy or LifecycleVisibilityPolicy.ARTIFACT_MEMORY.value
        )
        result = run_local_evidence_lifecycle_fresh_context(
            package_dir=package,
            run_dir=run_dir,
            model=model,
            adapter_kind=adapter,
            max_turns=max_turns,
            process_id=process_id,
            verifier=verify_template_lifecycle,
            visibility_policy=selected_visibility,
        )
    else:
        raise typer.BadParameter("mode must be 'persistent' or 'fresh-context'", param_hint="--mode")
    emit("meta-harness lifecycle-run-local", result, start_time=start)


def _lifecycle_visibility_policy(value: str) -> LifecycleVisibilityPolicy:
    try:
        return LifecycleVisibilityPolicy(value)
    except ValueError as exc:
        choices = ", ".join(policy.value for policy in LifecycleVisibilityPolicy)
        raise typer.BadParameter(
            f"visibility policy must be one of: {choices}",
            param_hint="--visibility-policy",
        ) from exc


@app.command("lifecycle-ablation")
def lifecycle_ablation_command(
    config: Path = typer.Option(..., "--config", help="Lifecycle ablation YAML manifest"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print the exact plan without writing or calling models"),
) -> None:
    """Plan or execute a typed, resumable evidence-lifecycle ablation sweep."""
    start = time.monotonic()
    command = "meta-harness lifecycle-ablation"
    try:
        manifest = load_lifecycle_ablation_manifest(config)
        if dry_run:
            result = {
                "dry_run": True,
                **inspect_lifecycle_ablation_plan(manifest),
            }
        else:
            result = run_lifecycle_ablation(manifest).model_dump(mode="json")
    except (OSError, ValueError, yaml.YAMLError) as exc:
        emit(command, None, errors=[str(exc)], start_time=start)
        return
    emit(command, result, start_time=start)


@app.command("logic-evaluate")
def logic_evaluate_command(
    world: Path = typer.Option(..., "--world", help="Task-world JSON"),
    run: Path = typer.Option(..., "--run", help="Task-run evidence JSON"),
) -> None:
    """Evaluate a task run against a world's deterministic logic profile."""
    start = time.monotonic()
    world_payload = _load_json(world)
    run_payload = _load_json(run)
    evidence = run_payload.get("evidence", run_payload)
    result = evaluate_logic_profile(world_payload.get("logic_profile", {}), evidence).to_dict()
    emit("meta-harness logic-evaluate", result, start_time=start)


@app.command("review")
def review_command(
    world: Path = typer.Option(..., "--world", help="Task-world JSON"),
    run: Path = typer.Option(..., "--run", help="Task-run evidence JSON"),
    review_response: Path | None = typer.Option(
        None,
        "--review-response",
        help="Structured reviewer response JSON or text",
    ),
) -> None:
    """Emit an LLM review packet or apply a structured review response."""
    start = time.monotonic()
    world_payload = _load_json(world)
    run_payload = _load_json(run)
    if review_response is None:
        result = build_review_request(world_payload, run_payload)
    else:
        review = parse_review_response(review_response.read_text(encoding="utf-8"))
        result = evaluate_with_review(world_payload, run_payload, review)
    emit("meta-harness review", result, start_time=start)


@app.command("review-models")
def review_models_command(
    world: Path = typer.Option(..., "--world", help="Task-world JSON"),
    run: Path = typer.Option(..., "--run", help="Task-run evidence JSON"),
    model: list[str] | None = typer.Option(None, "--model", help="Model endpoint spec"),
    models_config: Path | None = typer.Option(None, "--models-config", help="Endpoint config JSON"),
    emit_run_plan: bool = typer.Option(False, "--emit-run-plan", help="Emit endpoint run plan only"),
    allow_provider_errors: bool = typer.Option(
        False,
        "--allow-provider-errors",
        help="Return success even if providers fail",
    ),
) -> None:
    """Run or plan logic-profile reviewer model calls."""
    start = time.monotonic()
    endpoints = _require_endpoints(model, models_config)
    world_payload = _load_json(world)
    run_payload = _load_json(run)
    if emit_run_plan:
        result = build_review_model_run_plan(world_payload, run_payload, endpoints)
        emit("meta-harness review-models", result, start_time=start)
        return
    result = run_review_models(world_payload, run_payload, endpoints)
    _emit_model_result("meta-harness review-models", result, start, allow_provider_errors)


@app.command("operation-apply")
def operation_apply_command(
    world: Path = typer.Option(..., "--world", help="Task-world JSON"),
    operation: Path = typer.Option(..., "--operation", help="Operation JSON"),
    other_world: Path | None = typer.Option(None, "--other-world", help="Right-hand world for product operations"),
) -> None:
    """Apply one deterministic operation-profile operation."""
    start = time.monotonic()
    operation_payload = _load_json(operation)
    if other_world is not None:
        operation_payload = operation_payload | {"other_world": _load_json(other_world)}
    result = apply_world_operation(_load_json(world), operation_payload).to_dict()
    emit("meta-harness operation-apply", result, start_time=start)


@app.command("operation-orchestrate")
def operation_orchestrate_command(
    brief: Path = typer.Option(..., "--brief", help="Problem-space brief JSON"),
    world: list[Path] | None = typer.Option(None, "--world", help="Task-world JSON. Repeat for multiple worlds."),
    allowed_operation: list[str] | None = typer.Option(
        None,
        "--allowed-operation",
        help="Allowed operation name. Repeat to restrict the environment.",
    ),
    plan: Path | None = typer.Option(None, "--plan", help="Operation plan JSON"),
    emit_request: bool = typer.Option(False, "--emit-request", help="Emit request packet without executing a plan"),
) -> None:
    """Build an operation-orchestrator request or execute a supplied plan."""
    start = time.monotonic()
    worlds = _load_worlds(world)
    result = run_operation_orchestrator(
        brief=_load_json(brief),
        worlds=worlds,
        allowed_operations=allowed_operation,
        operation_plan=None if emit_request else _load_optional_json(plan),
    ).to_dict()
    emit("meta-harness operation-orchestrate", result, start_time=start)


@app.command("operation-models")
def operation_models_command(
    brief: Path = typer.Option(..., "--brief", help="Problem-space brief JSON"),
    world: list[Path] | None = typer.Option(None, "--world", help="Task-world JSON. Repeat for multiple worlds."),
    model: list[str] | None = typer.Option(None, "--model", help="Model endpoint spec"),
    models_config: Path | None = typer.Option(None, "--models-config", help="Endpoint config JSON"),
    allowed_operation: list[str] | None = typer.Option(
        None,
        "--allowed-operation",
        help="Allowed operation name. Repeat to restrict the environment.",
    ),
    emit_run_plan: bool = typer.Option(False, "--emit-run-plan", help="Emit endpoint run plan only"),
    allow_provider_errors: bool = typer.Option(
        False,
        "--allow-provider-errors",
        help="Return success even if providers fail",
    ),
) -> None:
    """Run or plan model-backed operation orchestration."""
    start = time.monotonic()
    endpoints = _require_endpoints(model, models_config)
    brief_payload = _load_json(brief)
    worlds = _load_worlds(world)
    if emit_run_plan:
        result = build_operation_model_run_plan(
            brief=brief_payload,
            worlds=worlds,
            endpoints=endpoints,
            allowed_operations=allowed_operation,
        )
        emit("meta-harness operation-models", result, start_time=start)
        return
    result = run_operation_models(
        brief=brief_payload,
        worlds=worlds,
        endpoints=endpoints,
        allowed_operations=allowed_operation,
    )
    _emit_model_result("meta-harness operation-models", result, start, allow_provider_errors)


@app.command("harbor-task")
def harbor_task_command(
    brief: Path = typer.Option(..., "--brief", help="Problem-space brief JSON"),
    world: list[Path] | None = typer.Option(None, "--world", help="Task-world JSON. Repeat for multiple worlds."),
    output: Path = typer.Option(..., "--output", help="Directory where Harbor-shaped artifacts are written"),
    task_id: str | None = typer.Option(None, "--task-id", help="Optional stable task id"),
    plan: Path | None = typer.Option(None, "--plan", help="Operation plan JSON"),
    allowed_operation: list[str] | None = typer.Option(
        None,
        "--allowed-operation",
        help="Allowed operation name. Repeat to restrict the environment.",
    ),
    model: list[str] | None = typer.Option(None, "--model", help="Model endpoint spec recorded in agent input"),
    models_config: Path | None = typer.Option(None, "--models-config", help="Endpoint config JSON"),
) -> None:
    """Materialize a Harbor-shaped operation-orchestrator task package."""
    start = time.monotonic()
    result = materialize_harbor_task_package(
        output_dir=output,
        brief=_load_json(brief),
        worlds=_load_worlds(world),
        task_id=task_id,
        allowed_operations=allowed_operation,
        operation_plan=_load_optional_json(plan),
        model_endpoints=_load_stage_endpoints(model, models_config),
    )
    emit("meta-harness harbor-task", result, start_time=start)


@app.command("intake")
def intake_command(
    task_text: str | None = typer.Option(None, "--task-text", help="Natural-language task request"),
    task_file: Path | None = typer.Option(None, "--task-file", help="File containing the task request"),
    process_id: str | None = typer.Option(None, "--process-id", help="Stable process id"),
) -> None:
    """Emit a problem-space brief request from natural-language prose."""
    start = time.monotonic()
    result = build_problem_brief_request(task_text=_task_text(task_text, task_file), process_id=process_id)
    emit("meta-harness intake", result, start_time=start)


@app.command("intake-models")
def intake_models_command(
    task_text: str | None = typer.Option(None, "--task-text", help="Natural-language task request"),
    task_file: Path | None = typer.Option(None, "--task-file", help="File containing the task request"),
    process_id: str | None = typer.Option(None, "--process-id", help="Stable process id"),
    model: list[str] | None = typer.Option(None, "--model", help="Model endpoint spec"),
    models_config: Path | None = typer.Option(None, "--models-config", help="Endpoint config JSON"),
    emit_run_plan: bool = typer.Option(False, "--emit-run-plan", help="Emit endpoint run plan only"),
    allow_provider_errors: bool = typer.Option(
        False,
        "--allow-provider-errors",
        help="Return success even if providers fail",
    ),
) -> None:
    """Run or plan model-backed problem-space intake."""
    start = time.monotonic()
    endpoints = _require_endpoints(model, models_config)
    resolved_task_text = _task_text(task_text, task_file)
    if emit_run_plan:
        result = build_intake_model_run_plan(
            task_text=resolved_task_text,
            endpoints=endpoints,
            process_id=process_id,
        )
        emit("meta-harness intake-models", result, start_time=start)
        return
    result = run_intake_models(task_text=resolved_task_text, endpoints=endpoints, process_id=process_id)
    _emit_model_result("meta-harness intake-models", result, start, allow_provider_errors)


@app.command("world-request")
def world_request_command(
    brief: Path = typer.Option(..., "--brief", help="Problem-space brief JSON"),
    source_world: Path | None = typer.Option(None, "--source-world", help="Optional source world JSON"),
    governance_directive: Path | None = typer.Option(
        None,
        "--governance-directive",
        help="Optional governance directive JSON",
    ),
    process_id: str | None = typer.Option(None, "--process-id", help="Stable process id"),
) -> None:
    """Emit a world-generation request from a problem-space brief."""
    start = time.monotonic()
    result = build_world_generation_request(
        brief=_load_json(brief),
        source_world=_load_optional_json(source_world),
        governance_directive=_load_optional_json(governance_directive),
        process_id=process_id,
    )
    emit("meta-harness world-request", result, start_time=start)


@app.command("world-models")
def world_models_command(
    brief: Path = typer.Option(..., "--brief", help="Problem-space brief JSON"),
    source_world: Path | None = typer.Option(None, "--source-world", help="Optional source world JSON"),
    governance_directive: Path | None = typer.Option(
        None,
        "--governance-directive",
        help="Optional governance directive JSON",
    ),
    process_id: str | None = typer.Option(None, "--process-id", help="Stable process id"),
    model: list[str] | None = typer.Option(None, "--model", help="Model endpoint spec"),
    models_config: Path | None = typer.Option(None, "--models-config", help="Endpoint config JSON"),
    emit_run_plan: bool = typer.Option(False, "--emit-run-plan", help="Emit endpoint run plan only"),
    allow_provider_errors: bool = typer.Option(
        False,
        "--allow-provider-errors",
        help="Return success even if providers fail",
    ),
) -> None:
    """Run or plan model-backed world generation."""
    start = time.monotonic()
    endpoints = _require_endpoints(model, models_config)
    brief_payload = _load_json(brief)
    source_payload = _load_optional_json(source_world)
    directive_payload = _load_optional_json(governance_directive)
    if emit_run_plan:
        result = build_world_generation_model_run_plan(
            brief=brief_payload,
            source_world=source_payload,
            governance_directive=directive_payload,
            endpoints=endpoints,
            process_id=process_id,
        )
        emit("meta-harness world-models", result, start_time=start)
        return
    result = run_world_generation_models(
        brief=brief_payload,
        source_world=source_payload,
        governance_directive=directive_payload,
        endpoints=endpoints,
        process_id=process_id,
    )
    _emit_model_result("meta-harness world-models", result, start, allow_provider_errors)


@app.command("govern")
def govern_command(
    brief: Path = typer.Option(..., "--brief", help="Problem-space brief JSON"),
    source_world: Path = typer.Option(..., "--source-world", help="Source world JSON"),
    proposal: Path = typer.Option(..., "--proposal", help="Operation proposal JSON"),
    decision: Path = typer.Option(..., "--decision", help="Governance decision JSON"),
    process_id: str | None = typer.Option(None, "--process-id", help="Stable process id"),
) -> None:
    """Apply a governance decision to an operation proposal."""
    start = time.monotonic()
    result = apply_governance_decision(
        brief=_load_json(brief),
        source_world=_load_json(source_world),
        proposal=_load_json(proposal),
        decision=_load_json(decision),
        process_id=process_id,
    )
    emit("meta-harness govern", result, start_time=start)


@app.command("autonomous")
def autonomous_command(
    task_text: str | None = typer.Option(None, "--task-text", help="Natural-language task request"),
    task_file: Path | None = typer.Option(None, "--task-file", help="File containing the task request"),
    process_id: str | None = typer.Option(None, "--process-id", help="Stable process id"),
    brief: Path | None = typer.Option(None, "--brief", help="Initial problem-space brief JSON"),
    world: Path | None = typer.Option(None, "--world", help="Initial world JSON"),
    world_candidate: list[Path] | None = typer.Option(None, "--world-candidate", help="Queued world JSON"),
    task_run: list[Path] | None = typer.Option(None, "--task-run", help="Queued task-run JSON"),
    operation_plan: list[Path] | None = typer.Option(None, "--operation-plan", help="Queued operation plan JSON"),
    governance_proposal: list[Path] | None = typer.Option(
        None,
        "--governance-proposal",
        help="Queued governance proposal JSON",
    ),
    governance_decision: list[Path] | None = typer.Option(
        None,
        "--governance-decision",
        help="Queued governance decision JSON",
    ),
    output: Path | None = typer.Option(None, "--output", help="Output directory for artifacts and ledger"),
    ledger: Path | None = typer.Option(None, "--ledger", help="Process ledger JSONL path"),
    max_iterations: int = typer.Option(10, "--max-iterations", help="Maximum autonomous iterations"),
    batch_size: int = typer.Option(1, "--batch-size", help="Candidate batch size"),
    improvement_threshold: float = typer.Option(0.02, "--improvement-threshold", help="Selection threshold"),
    stagnation_window: int = typer.Option(3, "--stagnation-window", help="Non-improvement window"),
    max_world_regenerations: int = typer.Option(
        4,
        "--max-world-regenerations",
        help="Maximum accepted world regenerations",
    ),
    max_governance_actions: int = typer.Option(
        8,
        "--max-governance-actions",
        help="Maximum governance actions",
    ),
    max_cost_usd: float | None = typer.Option(None, "--max-cost-usd", help="Optional cost budget"),
    auto_accept_scope: list[str] | None = typer.Option(None, "--auto-accept-scope", help="Scope to auto-accept"),
    require_human_for: list[str] | None = typer.Option(None, "--require-human-for", help="Scope requiring humans"),
    selection_strategy: str = typer.Option("hill_climb", "--selection-strategy", help="Candidate strategy"),
    intake_model: list[str] | None = typer.Option(None, "--intake-model", help="Intake model endpoint spec"),
    intake_models_config: Path | None = typer.Option(None, "--intake-models-config", help="Intake endpoint config"),
    world_model: list[str] | None = typer.Option(None, "--world-model", help="World model endpoint spec"),
    world_models_config: Path | None = typer.Option(None, "--world-models-config", help="World endpoint config"),
    review_model: list[str] | None = typer.Option(None, "--review-model", help="Reviewer model endpoint spec"),
    review_models_config: Path | None = typer.Option(None, "--review-models-config", help="Reviewer endpoint config"),
    operation_model: list[str] | None = typer.Option(None, "--operation-model", help="Operation model endpoint spec"),
    operation_models_config: Path | None = typer.Option(
        None,
        "--operation-models-config",
        help="Operation endpoint config",
    ),
) -> None:
    """Run bounded autonomous supervision over explicit pauseable process artifacts."""
    start = time.monotonic()
    proposals = _load_queue(governance_proposal)
    decisions = _load_queue(governance_decision)
    if len(proposals) != len(decisions):
        raise typer.BadParameter("--governance-proposal and --governance-decision counts must match")

    config = AutonomyConfig(
        max_iterations=max_iterations,
        batch_size=batch_size,
        improvement_threshold=improvement_threshold,
        stagnation_window=stagnation_window,
        max_world_regenerations=max_world_regenerations,
        max_governance_actions=max_governance_actions,
        max_cost_usd=max_cost_usd,
        auto_accept_scopes=tuple(auto_accept_scope or ["run_only"]),
        require_human_for=tuple(require_human_for or ["world_schema", "world_generator"]),
        selection_strategy=selection_strategy,
    )
    result = run_autonomous_process(
        task_text=_task_text(task_text, task_file),
        process_id=process_id,
        config=config,
        problem_space_brief=_load_optional_json(brief),
        world=_load_optional_json(world),
        intake_endpoints=_load_stage_endpoints(intake_model, intake_models_config),
        world_generation_endpoints=_load_stage_endpoints(world_model, world_models_config),
        review_endpoints=_load_stage_endpoints(review_model, review_models_config),
        operation_endpoints=_load_stage_endpoints(operation_model, operation_models_config),
        output_dir=output,
        ledger_path=ledger,
        world_resolver=_queue_resolver(_load_queue(world_candidate), "world candidate"),
        task_run_resolver=_queue_resolver(_load_queue(task_run), "task run"),
        operation_plan_resolver=_queue_resolver(_load_queue(operation_plan), "operation plan"),
        governance_resolver=_governance_queue_resolver(proposals, decisions),
    )
    emit("meta-harness autonomous", result, start_time=start)


@app.command("recipe")
def recipe_command(
    task_text: str | None = typer.Option(None, "--task-text", help="Natural-language task request"),
    task_file: Path | None = typer.Option(None, "--task-file", help="File containing the task request"),
    output: Path = typer.Option(..., "--output", help="Directory where the recipe workspace is written"),
    process_id: str | None = typer.Option(None, "--process-id", help="Stable recipe/process id"),
    baseline_world: Path | None = typer.Option(None, "--baseline-world", help="Existing baseline world JSON"),
    baseline_run: Path | None = typer.Option(None, "--baseline-run", help="Existing baseline task-run JSON"),
    candidate_world: Path | None = typer.Option(None, "--candidate-world", help="Candidate world JSON"),
    candidate_run: Path | None = typer.Option(None, "--candidate-run", help="Candidate task-run JSON"),
    baseline_experiment: Path | None = typer.Option(
        None,
        "--baseline-experiment",
        help="Existing baseline experiment YAML",
    ),
    candidate_experiment: Path | None = typer.Option(
        None,
        "--candidate-experiment",
        help="Candidate experiment YAML",
    ),
    models_config: Path | None = typer.Option(None, "--models-config", help="Shared intake/world endpoint config"),
    reviewer_models_config: Path | None = typer.Option(
        None,
        "--reviewer-models-config",
        help="Reviewer endpoint config",
    ),
    operation_models_config: Path | None = typer.Option(
        None,
        "--operation-models-config",
        help="Operation planner endpoint config",
    ),
    command_prefix: str = typer.Option("aec-bench", "--command-prefix", help="Command used in generated scripts"),
) -> None:
    """Materialize a scriptable candidate-vs-baseline harness comparison recipe."""
    start = time.monotonic()
    result = materialize_harness_comparison_recipe(
        output_dir=output,
        task_text=_task_text(task_text, task_file),
        process_id=process_id,
        baseline_world=baseline_world,
        baseline_run=baseline_run,
        candidate_world=candidate_world,
        candidate_run=candidate_run,
        baseline_experiment=baseline_experiment,
        candidate_experiment=candidate_experiment,
        models_config=models_config,
        reviewer_models_config=reviewer_models_config,
        operation_models_config=operation_models_config,
        command_prefix=command_prefix,
    )
    emit("meta-harness recipe", result, start_time=start)


@app.command("process")
def process_command(
    task_text: str = typer.Argument(..., help="Natural-language task request"),
    process_id: str | None = typer.Option(None, "--process-id", help="Stable process id"),
    brief: Path | None = typer.Option(None, "--brief", help="Problem-space brief JSON"),
    world: Path | None = typer.Option(None, "--world", help="Task-world JSON"),
    task_run: Path | None = typer.Option(None, "--task-run", help="Task-run evidence JSON"),
    operation_plan: Path | None = typer.Option(None, "--operation-plan", help="Operation plan JSON"),
    governance_proposal: Path | None = typer.Option(None, "--governance-proposal", help="Governance proposal JSON"),
    governance_decision: Path | None = typer.Option(None, "--governance-decision", help="Governance decision JSON"),
    output_dir: Path | None = typer.Option(
        None,
        "--output-dir",
        "--output",
        help="Directory for generated process artifacts",
    ),
    ledger: Path | None = typer.Option(None, "--ledger", help="Process ledger JSONL path"),
    intake_model: list[str] | None = typer.Option(None, "--intake-model", help="Intake model endpoint spec"),
    intake_models_config: Path | None = typer.Option(None, "--intake-models-config", help="Intake endpoint config"),
    world_model: list[str] | None = typer.Option(None, "--world-model", help="World-generation model endpoint spec"),
    world_models_config: Path | None = typer.Option(None, "--world-models-config", help="World endpoint config"),
    review_model: list[str] | None = typer.Option(None, "--review-model", help="Reviewer model endpoint spec"),
    review_models_config: Path | None = typer.Option(None, "--review-models-config", help="Reviewer endpoint config"),
    operation_model: list[str] | None = typer.Option(None, "--operation-model", help="Operation model endpoint spec"),
    operation_models_config: Path | None = typer.Option(
        None,
        "--operation-models-config",
        help="Operation endpoint config",
    ),
) -> None:
    """Run the pauseable meta-harness process runtime."""
    start = time.monotonic()
    result = run_process(
        task_text=task_text,
        process_id=process_id,
        problem_space_brief=_load_optional_json(brief),
        world=_load_optional_json(world),
        task_run=_load_optional_json(task_run),
        operation_plan=_load_optional_json(operation_plan),
        governance_proposal=_load_optional_json(governance_proposal),
        governance_decision=_load_optional_json(governance_decision),
        intake_endpoints=_load_stage_endpoints(intake_model, intake_models_config),
        world_generation_endpoints=_load_stage_endpoints(world_model, world_models_config),
        review_endpoints=_load_stage_endpoints(review_model, review_models_config),
        operation_endpoints=_load_stage_endpoints(operation_model, operation_models_config),
        output_dir=output_dir,
        ledger_path=ledger,
    )

    def _render(data: dict[str, Any]) -> None:
        print_success(f"Meta-harness process {data['process_id']} -> {data['status']}")

    emit("meta-harness process", result, start_time=start, human_renderer=_render)


def _load_stage_endpoints(specs: list[str] | None, config: Path | None) -> list[Any]:
    endpoints = []
    if config is not None:
        endpoints.extend(load_model_endpoints(config))
    endpoints.extend(parse_model_endpoint(spec) for spec in specs or [])
    return endpoints


def _require_endpoints(specs: list[str] | None, config: Path | None) -> list[Any]:
    endpoints = _load_stage_endpoints(specs, config)
    if not endpoints:
        raise typer.BadParameter("at least one --model or --models-config entry is required")
    return endpoints


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        msg = f"expected JSON object in {path}"
        raise typer.BadParameter(msg)
    return payload


def _load_optional_json(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    return _load_json(path)


def _load_worlds(paths: list[Path] | None) -> list[dict[str, Any]]:
    if not paths:
        raise typer.BadParameter("at least one --world entry is required")
    return [_load_json(path) for path in paths]


def _load_queue(paths: list[Path] | None) -> list[dict[str, Any]]:
    return [_load_json(path) for path in paths or []]


def _task_text(task_text: str | None, task_file: Path | None) -> str:
    if task_text and task_file:
        raise typer.BadParameter("use --task-text or --task-file, not both")
    if task_file is not None:
        text = task_file.read_text(encoding="utf-8").strip()
    else:
        text = (task_text or "").strip()
    if not text:
        raise typer.BadParameter("one of --task-text or --task-file is required")
    return text


def _queue_resolver(
    queue: list[dict[str, Any]],
    label: str,
) -> Callable[[dict[str, Any]], dict[str, Any]] | None:
    if not queue:
        return None

    def resolve(_request: dict[str, Any]) -> dict[str, Any]:
        if not queue:
            raise typer.BadParameter(f"no queued {label} artifact available")
        return queue.pop(0)

    return resolve


def _governance_queue_resolver(
    proposals: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
) -> Callable[[dict[str, Any]], dict[str, Any]] | None:
    if not proposals and not decisions:
        return None

    def resolve(_request: dict[str, Any]) -> dict[str, Any]:
        if not proposals or not decisions:
            raise typer.BadParameter("no queued governance action available")
        return {
            "proposal": proposals.pop(0),
            "decision": decisions.pop(0),
        }

    return resolve


def _emit_model_result(command: str, result: dict[str, Any], start: float, allow_provider_errors: bool) -> None:
    errors = None
    if _has_model_errors(result) and not allow_provider_errors:
        errors = ["one or more model providers failed"]
    emit(command, result, errors=errors, start_time=start)


def _has_model_errors(result: dict[str, Any]) -> bool:
    return any(item.get("status") == "error" for item in result.get("results", []))
