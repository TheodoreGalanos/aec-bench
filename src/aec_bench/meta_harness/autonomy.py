# ABOUTME: Supervises the pauseable meta-harness runtime across bounded autonomous cycles.
# ABOUTME: Resolves waiting states, scores outcomes, gates governance, and records loop history.

from __future__ import annotations

import copy
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aec_bench.meta_harness.ledger import append_ledger_entry
from aec_bench.meta_harness.model_runner import ModelEndpoint
from aec_bench.meta_harness.world_runtime import run_process

GOVERNANCE_SCOPES = {"run_only", "world_schema", "world_generator"}
SELECTION_STRATEGIES = {"hill_climb", "none"}

BriefResolver = Callable[[dict[str, Any]], dict[str, Any]]
WorldResolver = Callable[[dict[str, Any]], dict[str, Any]]
TaskRunResolver = Callable[[dict[str, Any]], dict[str, Any]]
OperationPlanResolver = Callable[[dict[str, Any]], dict[str, Any]]
GovernanceResolver = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class AutonomyConfig:
    max_iterations: int = 10
    batch_size: int = 1
    improvement_threshold: float = 0.02
    stagnation_window: int = 3
    max_world_regenerations: int = 4
    max_governance_actions: int = 8
    max_cost_usd: float | None = None
    auto_accept_scopes: tuple[str, ...] = ("run_only",)
    require_human_for: tuple[str, ...] = ("world_schema", "world_generator")
    selection_strategy: str = "hill_climb"

    def __post_init__(self) -> None:
        for field_name in [
            "max_iterations",
            "batch_size",
            "stagnation_window",
            "max_governance_actions",
        ]:
            value = getattr(self, field_name)
            if value <= 0:
                raise ValueError(f"{field_name} must be greater than zero")
        if self.max_world_regenerations < 0:
            raise ValueError("max_world_regenerations must be zero or greater")
        if self.improvement_threshold < 0:
            raise ValueError("improvement_threshold must be zero or greater")
        if self.max_cost_usd is not None and self.max_cost_usd < 0:
            raise ValueError("max_cost_usd must be zero or greater")
        if self.selection_strategy not in SELECTION_STRATEGIES:
            raise ValueError(f"selection_strategy must be one of {sorted(SELECTION_STRATEGIES)}")

        auto_accept_scopes = _normalise_scopes(self.auto_accept_scopes)
        require_human_for = _normalise_scopes(self.require_human_for)
        overlap = set(auto_accept_scopes) & set(require_human_for)
        if overlap:
            scopes = ", ".join(sorted(overlap))
            raise ValueError(f"cannot both auto-accept and require human for: {scopes}")

        object.__setattr__(self, "auto_accept_scopes", auto_accept_scopes)
        object.__setattr__(self, "require_human_for", require_human_for)

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_iterations": self.max_iterations,
            "batch_size": self.batch_size,
            "improvement_threshold": self.improvement_threshold,
            "stagnation_window": self.stagnation_window,
            "max_world_regenerations": self.max_world_regenerations,
            "max_governance_actions": self.max_governance_actions,
            "max_cost_usd": self.max_cost_usd,
            "auto_accept_scopes": list(self.auto_accept_scopes),
            "require_human_for": list(self.require_human_for),
            "selection_strategy": self.selection_strategy,
        }


def run_autonomous_process(
    *,
    task_text: str,
    process_id: str | None = None,
    config: AutonomyConfig | None = None,
    attachments: list[dict[str, Any]] | None = None,
    problem_space_brief: dict[str, Any] | None = None,
    world: dict[str, Any] | None = None,
    task_run: dict[str, Any] | None = None,
    operation_plan: dict[str, Any] | None = None,
    governance_proposal: dict[str, Any] | None = None,
    governance_decision: dict[str, Any] | None = None,
    intake_endpoints: list[ModelEndpoint] | None = None,
    world_generation_endpoints: list[ModelEndpoint] | None = None,
    review_endpoints: list[ModelEndpoint] | None = None,
    operation_endpoints: list[ModelEndpoint] | None = None,
    output_dir: Path | None = None,
    ledger_path: Path | None = None,
    brief_resolver: BriefResolver | None = None,
    world_resolver: WorldResolver | None = None,
    task_run_resolver: TaskRunResolver | None = None,
    operation_plan_resolver: OperationPlanResolver | None = None,
    governance_resolver: GovernanceResolver | None = None,
) -> dict[str, Any]:
    resolved_config = config or AutonomyConfig()
    resolved_process_id = process_id or "process.autonomous"
    resolved_ledger_path = _ledger_path(output_dir, ledger_path)

    current_brief = problem_space_brief
    current_world = world
    current_task_run = task_run
    current_operation_plan = operation_plan
    current_governance_proposal = governance_proposal
    current_governance_decision = governance_decision

    score_history: list[float] = []
    iteration_records: list[dict[str, Any]] = []
    best_score: float | None = None
    best_iteration: int | None = None
    selected_world: dict[str, Any] | None = copy.deepcopy(current_world)
    run_directives: list[dict[str, Any]] = []
    world_regenerations = 0
    governance_actions = 0
    total_cost_usd = 0.0
    last_result: dict[str, Any] | None = None

    for iteration in range(1, resolved_config.max_iterations + 1):
        iteration_result = _run_iteration(
            iteration=iteration,
            task_text=task_text,
            process_id=resolved_process_id,
            attachments=attachments,
            problem_space_brief=current_brief,
            world=current_world,
            task_run=current_task_run,
            operation_plan=current_operation_plan,
            governance_proposal=current_governance_proposal,
            governance_decision=current_governance_decision,
            intake_endpoints=intake_endpoints,
            world_generation_endpoints=world_generation_endpoints,
            review_endpoints=review_endpoints,
            operation_endpoints=operation_endpoints,
            output_dir=output_dir,
            ledger_path=resolved_ledger_path,
            config=resolved_config,
            governance_actions=governance_actions,
            run_directives=run_directives,
            brief_resolver=brief_resolver,
            world_resolver=world_resolver,
            task_run_resolver=task_run_resolver,
            operation_plan_resolver=operation_plan_resolver,
            governance_resolver=governance_resolver,
        )
        last_result = iteration_result["runtime_result"]
        current_brief = iteration_result["problem_space_brief"]
        current_world = iteration_result["world"]
        current_task_run = iteration_result["task_run"]
        current_operation_plan = iteration_result["operation_plan"]
        current_governance_proposal = iteration_result["governance_proposal"]
        current_governance_decision = iteration_result["governance_decision"]
        governance_actions = iteration_result["governance_actions"]

        non_improving_candidate = False
        score = score_process_result(last_result) if _has_task_evidence(last_result) else None
        if score is not None:
            score_value = score["value"]
            previous_best_score = best_score
            score_history.append(score_value)
            if _should_select_candidate(score_value, previous_best_score, resolved_config):
                best_score = score_value
                best_iteration = iteration
                selected_world = copy.deepcopy(current_world) if isinstance(current_world, dict) else None
            elif (
                resolved_config.selection_strategy == "hill_climb"
                and world_regenerations > 0
                and previous_best_score is not None
            ):
                non_improving_candidate = True

        _attach_autonomy_state(last_result, run_directives=run_directives, selected_world=selected_world)
        iteration_record = {
            "iteration": iteration,
            "status": iteration_result["status"],
            "runtime_status": last_result.get("status"),
            "score": score,
            "resolution_steps": iteration_result["resolution_steps"],
            "world_id": current_world.get("world_id") if isinstance(current_world, dict) else None,
        }
        iteration_records.append(iteration_record)
        _record_autonomy(
            resolved_ledger_path,
            process_id=resolved_process_id,
            stage="autonomy_iteration",
            status=iteration_result["status"],
            summary={
                "iteration": iteration,
                "runtime_status": last_result.get("status"),
                "score": score["value"] if score else None,
            },
        )

        if iteration_result["status"] != "complete":
            return _finish(
                status=iteration_result["status"],
                stop_reason=iteration_result["status"],
                config=resolved_config,
                process_id=resolved_process_id,
                iteration_records=iteration_records,
                score_history=score_history,
                best_score=best_score,
                best_iteration=best_iteration,
                world_regenerations=world_regenerations,
                governance_actions=governance_actions,
                total_cost_usd=total_cost_usd,
                last_result=last_result,
                ledger_path=resolved_ledger_path,
                extra=iteration_result.get("extra"),
            )

        total_cost_usd += _estimate_cost_usd(last_result)
        if resolved_config.max_cost_usd is not None and total_cost_usd > resolved_config.max_cost_usd:
            return _finish(
                status="max_cost",
                stop_reason="max_cost",
                config=resolved_config,
                process_id=resolved_process_id,
                iteration_records=iteration_records,
                score_history=score_history,
                best_score=best_score,
                best_iteration=best_iteration,
                world_regenerations=world_regenerations,
                governance_actions=governance_actions,
                total_cost_usd=total_cost_usd,
                last_result=last_result,
                ledger_path=resolved_ledger_path,
            )

        if non_improving_candidate:
            return _finish(
                status="no_improvement",
                stop_reason="no_improvement",
                config=resolved_config,
                process_id=resolved_process_id,
                iteration_records=iteration_records,
                score_history=score_history,
                best_score=best_score,
                best_iteration=best_iteration,
                world_regenerations=world_regenerations,
                governance_actions=governance_actions,
                total_cost_usd=total_cost_usd,
                last_result=last_result,
                ledger_path=resolved_ledger_path,
            )

        if _is_converged(score_history, resolved_config):
            return _finish(
                status="converged",
                stop_reason="converged",
                config=resolved_config,
                process_id=resolved_process_id,
                iteration_records=iteration_records,
                score_history=score_history,
                best_score=best_score,
                best_iteration=best_iteration,
                world_regenerations=world_regenerations,
                governance_actions=governance_actions,
                total_cost_usd=total_cost_usd,
                last_result=last_result,
                ledger_path=resolved_ledger_path,
            )

        if last_result.get("status") == "accepted_for_world_generation":
            if world_regenerations >= resolved_config.max_world_regenerations:
                return _finish(
                    status="max_world_regenerations",
                    stop_reason="max_world_regenerations",
                    config=resolved_config,
                    process_id=resolved_process_id,
                    iteration_records=iteration_records,
                    score_history=score_history,
                    best_score=best_score,
                    best_iteration=best_iteration,
                    world_regenerations=world_regenerations,
                    governance_actions=governance_actions,
                    total_cost_usd=total_cost_usd,
                    last_result=last_result,
                    ledger_path=resolved_ledger_path,
                )
            request = last_result["governance"]["world_generation_request"]
            if world_resolver is None:
                return _finish(
                    status="awaiting_world_generation",
                    stop_reason="awaiting_world_generation",
                    config=resolved_config,
                    process_id=resolved_process_id,
                    iteration_records=iteration_records,
                    score_history=score_history,
                    best_score=best_score,
                    best_iteration=best_iteration,
                    world_regenerations=world_regenerations,
                    governance_actions=governance_actions,
                    total_cost_usd=total_cost_usd,
                    last_result=last_result,
                    ledger_path=resolved_ledger_path,
                )
            current_world = world_resolver(request)
            world_regenerations += 1
            current_task_run = None
            current_operation_plan = None
            current_governance_proposal = None
            current_governance_decision = None
            continue

        if last_result.get("status") == "accepted_for_run":
            directive = last_result.get("governance", {}).get("run_directive")
            if isinstance(directive, dict):
                run_directives.append(copy.deepcopy(directive))
            current_task_run = None
            current_operation_plan = None
            current_governance_proposal = None
            current_governance_decision = None
            _attach_autonomy_state(last_result, run_directives=run_directives, selected_world=selected_world)
            continue

        return _finish(
            status=last_result.get("status", "complete"),
            stop_reason=last_result.get("status", "complete"),
            config=resolved_config,
            process_id=resolved_process_id,
            iteration_records=iteration_records,
            score_history=score_history,
            best_score=best_score,
            best_iteration=best_iteration,
            world_regenerations=world_regenerations,
            governance_actions=governance_actions,
            total_cost_usd=total_cost_usd,
            last_result=last_result,
            ledger_path=resolved_ledger_path,
        )

    return _finish(
        status="max_iterations",
        stop_reason="max_iterations",
        config=resolved_config,
        process_id=resolved_process_id,
        iteration_records=iteration_records,
        score_history=score_history,
        best_score=best_score,
        best_iteration=best_iteration,
        world_regenerations=world_regenerations,
        governance_actions=governance_actions,
        total_cost_usd=total_cost_usd,
        last_result=last_result or {},
        ledger_path=resolved_ledger_path,
    )


def score_process_result(result: dict[str, Any]) -> dict[str, Any]:
    evidence = _evidence(result)
    verifier_reward = _verifier_reward(evidence)
    logic_certified = 1.0 if result.get("logic_evaluation", {}).get("overall_status") == "certified" else 0.0
    review = evidence.get("agentic_review", {}) if isinstance(evidence, dict) else {}
    review_complete = 1.0 if review.get("status") in {"complete", "certified"} else 0.0
    evidence_completeness = _evidence_completeness(evidence)
    governance_churn_penalty = _governance_churn_penalty(result)
    unresolved_wait_penalty = 0.1 if str(result.get("status", "")).startswith("awaiting_") else 0.0
    value = (
        0.55 * verifier_reward
        + 0.20 * logic_certified
        + 0.15 * review_complete
        + 0.10 * evidence_completeness
        - governance_churn_penalty
        - unresolved_wait_penalty
    )
    value = max(0.0, min(1.0, value))
    return {
        "value": round(value, 6),
        "components": {
            "verifier_reward": verifier_reward,
            "logic_certified": logic_certified,
            "review_complete": review_complete,
            "evidence_completeness": evidence_completeness,
            "governance_churn_penalty": governance_churn_penalty,
            "unresolved_wait_penalty": unresolved_wait_penalty,
        },
    }


def estimate_process_cost_usd(result: dict[str, Any]) -> float:
    total = _cost_value(result)
    task_run = result.get("task_run")
    if isinstance(task_run, dict):
        total += _cost_value(task_run)
    for key in ("intake_model_run", "world_generation_model_run", "review_model_run"):
        model_run = result.get(key)
        if isinstance(model_run, dict):
            total += _cost_value(model_run)
    operation_run = result.get("operation_run")
    if isinstance(operation_run, dict):
        model_run = operation_run.get("model_run")
        if isinstance(model_run, dict):
            total += _cost_value(model_run)
    return round(total, 8)


def _run_iteration(
    *,
    iteration: int,
    task_text: str,
    process_id: str,
    attachments: list[dict[str, Any]] | None,
    problem_space_brief: dict[str, Any] | None,
    world: dict[str, Any] | None,
    task_run: dict[str, Any] | None,
    operation_plan: dict[str, Any] | None,
    governance_proposal: dict[str, Any] | None,
    governance_decision: dict[str, Any] | None,
    intake_endpoints: list[ModelEndpoint] | None,
    world_generation_endpoints: list[ModelEndpoint] | None,
    review_endpoints: list[ModelEndpoint] | None,
    operation_endpoints: list[ModelEndpoint] | None,
    output_dir: Path | None,
    ledger_path: Path | None,
    config: AutonomyConfig,
    governance_actions: int,
    run_directives: list[dict[str, Any]],
    brief_resolver: BriefResolver | None,
    world_resolver: WorldResolver | None,
    task_run_resolver: TaskRunResolver | None,
    operation_plan_resolver: OperationPlanResolver | None,
    governance_resolver: GovernanceResolver | None,
) -> dict[str, Any]:
    current_brief = problem_space_brief
    current_world = world
    current_task_run = task_run
    current_operation_plan = operation_plan
    current_governance_proposal = governance_proposal
    current_governance_decision = governance_decision
    resolution_steps: list[dict[str, Any]] = []

    for _step in range(1, 20):
        runtime_result = run_process(
            task_text=task_text,
            process_id=process_id,
            attachments=attachments,
            problem_space_brief=current_brief,
            world=current_world,
            task_run=current_task_run,
            operation_plan=current_operation_plan,
            governance_proposal=current_governance_proposal,
            governance_decision=current_governance_decision,
            intake_endpoints=intake_endpoints,
            world_generation_endpoints=world_generation_endpoints,
            review_endpoints=review_endpoints,
            operation_endpoints=operation_endpoints,
            output_dir=_iteration_output_dir(output_dir, iteration),
            ledger_path=ledger_path,
        )
        status = runtime_result["status"]

        if status == "awaiting_problem_space_brief" and brief_resolver is not None:
            current_brief = brief_resolver(runtime_result["intake_request"])
            resolution_steps.append({"status": status, "resolution": "problem_space_brief"})
            continue

        if status == "awaiting_world_generation" and world_resolver is not None:
            current_world = world_resolver(runtime_result["world_generation_request"])
            resolution_steps.append({"status": status, "resolution": "world"})
            continue

        if status == "awaiting_task_run" and task_run_resolver is not None:
            current_task_run = task_run_resolver(_task_run_request(runtime_result, config, run_directives))
            resolution_steps.append({"status": status, "resolution": "task_run"})
            continue

        if status == "awaiting_operation_plan" and operation_plan_resolver is not None:
            current_operation_plan = operation_plan_resolver(runtime_result)
            resolution_steps.append({"status": status, "resolution": "operation_plan"})
            continue

        if status == "awaiting_governance_decision" and governance_resolver is not None:
            if governance_actions >= config.max_governance_actions:
                return _iteration_result(
                    status="max_governance_actions",
                    runtime_result=runtime_result,
                    resolution_steps=resolution_steps,
                    problem_space_brief=current_brief,
                    world=current_world,
                    task_run=current_task_run,
                    operation_plan=current_operation_plan,
                    governance_proposal=current_governance_proposal,
                    governance_decision=current_governance_decision,
                    governance_actions=governance_actions,
                )
            governance_action = governance_resolver(runtime_result["governance_review"])
            proposal = governance_action["proposal"]
            decision = governance_action["decision"]
            if _requires_human_decision(config, proposal, decision):
                return _iteration_result(
                    status="awaiting_human_governance",
                    runtime_result=runtime_result,
                    resolution_steps=resolution_steps,
                    problem_space_brief=current_brief,
                    world=current_world,
                    task_run=current_task_run,
                    operation_plan=current_operation_plan,
                    governance_proposal=proposal,
                    governance_decision=decision,
                    governance_actions=governance_actions,
                    extra={"pending_proposal": proposal, "pending_decision": decision},
                )
            current_governance_proposal = proposal
            current_governance_decision = decision
            governance_actions += 1
            resolution_steps.append({"status": status, "resolution": "governance_decision"})
            continue

        terminal_status = "complete" if not status.startswith("awaiting_") else status
        return _iteration_result(
            status=terminal_status,
            runtime_result=runtime_result,
            resolution_steps=resolution_steps,
            problem_space_brief=current_brief or runtime_result.get("problem_space_brief"),
            world=current_world or runtime_result.get("world"),
            task_run=current_task_run or runtime_result.get("task_run"),
            operation_plan=current_operation_plan,
            governance_proposal=current_governance_proposal,
            governance_decision=current_governance_decision,
            governance_actions=governance_actions,
        )

    return _iteration_result(
        status="resolution_step_limit",
        runtime_result=runtime_result,
        resolution_steps=resolution_steps,
        problem_space_brief=current_brief,
        world=current_world,
        task_run=current_task_run,
        operation_plan=current_operation_plan,
        governance_proposal=current_governance_proposal,
        governance_decision=current_governance_decision,
        governance_actions=governance_actions,
    )


def _iteration_result(
    *,
    status: str,
    runtime_result: dict[str, Any],
    resolution_steps: list[dict[str, Any]],
    problem_space_brief: dict[str, Any] | None,
    world: dict[str, Any] | None,
    task_run: dict[str, Any] | None,
    operation_plan: dict[str, Any] | None,
    governance_proposal: dict[str, Any] | None,
    governance_decision: dict[str, Any] | None,
    governance_actions: int,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "runtime_result": runtime_result,
        "resolution_steps": resolution_steps,
        "problem_space_brief": problem_space_brief,
        "world": world,
        "task_run": task_run,
        "operation_plan": operation_plan,
        "governance_proposal": governance_proposal,
        "governance_decision": governance_decision,
        "governance_actions": governance_actions,
        "extra": extra or {},
    }


def _finish(
    *,
    status: str,
    stop_reason: str,
    config: AutonomyConfig,
    process_id: str,
    iteration_records: list[dict[str, Any]],
    score_history: list[float],
    best_score: float | None,
    best_iteration: int | None,
    world_regenerations: int,
    governance_actions: int,
    total_cost_usd: float,
    last_result: dict[str, Any],
    ledger_path: Path | None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _record_autonomy(
        ledger_path,
        process_id=process_id,
        stage="autonomy_stop",
        status=status,
        summary={
            "stop_reason": stop_reason,
            "iterations_completed": len(iteration_records),
            "world_regenerations": world_regenerations,
            "governance_actions": governance_actions,
        },
    )
    result = {
        "process_id": process_id,
        "status": status,
        "stop_reason": stop_reason,
        "config": config.to_dict(),
        "iterations_completed": len(iteration_records),
        "iteration_records": iteration_records,
        "score_history": score_history,
        "best_score": best_score,
        "best_iteration": best_iteration,
        "world_regenerations": world_regenerations,
        "governance_actions": governance_actions,
        "total_cost_usd": round(total_cost_usd, 6),
        "last_result": last_result,
        "ledger_path": str(ledger_path) if ledger_path else None,
    }
    autonomy_state = last_result.get("autonomy_state", {})
    run_directives = autonomy_state.get("run_directives", [])
    if isinstance(run_directives, list):
        result["run_directive_count"] = len(run_directives)
        result["run_directives"] = copy.deepcopy(run_directives)
    if autonomy_state.get("selected_world_id") is not None:
        result["selected_world_id"] = autonomy_state["selected_world_id"]
    if extra:
        result.update(extra)
    return result


def _normalise_scopes(scopes: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    result = tuple(scopes)
    for scope in result:
        if scope not in GOVERNANCE_SCOPES:
            raise ValueError(f"unknown governance scope: {scope}")
    return result


def _requires_human_decision(
    config: AutonomyConfig,
    proposal: dict[str, Any],
    decision: dict[str, Any],
) -> bool:
    decided_by = str(decision.get("decided_by", "")).lower()
    if decision.get("status") == "needs_human_review":
        return decided_by != "human"
    if decision.get("status") != "accepted":
        return False
    if proposal.get("requires_human_approval") is True and decided_by != "human":
        return True
    scope = decision.get("scope")
    if decided_by == "human":
        return False
    if scope in config.require_human_for:
        return True
    return scope not in config.auto_accept_scopes


def _task_run_request(
    runtime_result: dict[str, Any],
    config: AutonomyConfig,
    run_directives: list[dict[str, Any]],
) -> dict[str, Any]:
    request = copy.deepcopy(runtime_result)
    request["autonomy_request"] = {
        "batch_size": config.batch_size,
        "run_directives": copy.deepcopy(run_directives),
        "selection_strategy": config.selection_strategy,
    }
    return request


def _should_select_candidate(
    score_value: float,
    previous_best_score: float | None,
    config: AutonomyConfig,
) -> bool:
    if previous_best_score is None:
        return True
    if config.selection_strategy == "hill_climb":
        return score_value > previous_best_score + config.improvement_threshold
    return score_value > previous_best_score


def _attach_autonomy_state(
    result: dict[str, Any],
    *,
    run_directives: list[dict[str, Any]],
    selected_world: dict[str, Any] | None,
) -> None:
    state = result.setdefault("autonomy_state", {})
    state["run_directives"] = copy.deepcopy(run_directives)
    state["selected_world_id"] = selected_world.get("world_id") if selected_world else None


def _has_task_evidence(result: dict[str, Any]) -> bool:
    return bool(result.get("task_run"))


def _evidence(result: dict[str, Any]) -> dict[str, Any]:
    task_run = result.get("task_run") or {}
    evidence = task_run.get("evidence", task_run) if isinstance(task_run, dict) else {}
    return evidence if isinstance(evidence, dict) else {}


def _verifier_reward(evidence: dict[str, Any]) -> float:
    score = evidence.get("score", {})
    if not isinstance(score, dict):
        return 0.0
    reward = score.get("reward")
    if isinstance(reward, int | float):
        return max(0.0, min(1.0, float(reward)))
    if score.get("passed") is True:
        return 1.0
    if score.get("passed") is False:
        return 0.0
    return 0.0


def _evidence_completeness(evidence: dict[str, Any]) -> float:
    checks = [
        bool(evidence.get("score")),
        bool(evidence.get("artifacts")),
        bool(evidence.get("agentic_review")),
    ]
    return sum(1 for item in checks if item) / len(checks)


def _governance_churn_penalty(result: dict[str, Any]) -> float:
    governance = result.get("governance", {})
    decision = governance.get("decision", {}) if isinstance(governance, dict) else {}
    if result.get("status") == "accepted_for_world_generation":
        return 0.05
    if decision.get("scope") in {"world_schema", "world_generator"}:
        return 0.05
    return 0.0


def _is_converged(score_history: list[float], config: AutonomyConfig) -> bool:
    if len(score_history) < config.stagnation_window + 1:
        return False
    recent = score_history[-config.stagnation_window :]
    return (max(recent) - min(recent)) <= config.improvement_threshold


def _estimate_cost_usd(result: dict[str, Any]) -> float:
    return estimate_process_cost_usd(result)


def _cost_value(payload: dict[str, Any]) -> float:
    cost = payload.get("cost")
    if isinstance(cost, int | float):
        return float(cost)
    if isinstance(cost, dict):
        estimated = cost.get("estimated_cost_usd")
        if isinstance(estimated, int | float):
            return float(estimated)
    cost_usd = payload.get("cost_usd")
    if isinstance(cost_usd, int | float):
        return float(cost_usd)
    return 0.0


def _ledger_path(output_dir: Path | None, ledger_path: Path | None) -> Path | None:
    if ledger_path is not None:
        return ledger_path
    if output_dir is not None:
        return output_dir / "process_ledger.jsonl"
    return None


def _iteration_output_dir(output_dir: Path | None, iteration: int) -> Path | None:
    if output_dir is None:
        return None
    return output_dir / f"iteration-{iteration}"


def _record_autonomy(
    ledger_path: Path | None,
    *,
    process_id: str,
    stage: str,
    status: str,
    summary: dict[str, Any],
) -> None:
    if ledger_path is None:
        return
    append_ledger_entry(
        ledger_path,
        process_id=process_id,
        stage=stage,
        status=status,
        summary=summary,
    )
