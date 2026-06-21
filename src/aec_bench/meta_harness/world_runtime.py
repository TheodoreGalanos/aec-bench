# ABOUTME: Coordinates the full prose-to-world runtime with pauseable stage outputs.
# ABOUTME: Calls supplied resolvers through explicit boundaries and records every stage in an append-only ledger.

from __future__ import annotations

from pathlib import Path
from typing import Any

from aec_bench.meta_harness.harbor_task import materialize_harbor_task_package
from aec_bench.meta_harness.ledger import append_ledger_entry
from aec_bench.meta_harness.logic_profile import evaluate_logic_profile
from aec_bench.meta_harness.model_runner import (
    ModelEndpoint,
    attach_review_to_run,
    run_intake_models,
    run_operation_models,
    run_review_models,
    run_world_generation_models,
)
from aec_bench.meta_harness.operation_orchestrator import run_operation_orchestrator
from aec_bench.meta_harness.world_process import (
    apply_governance_decision,
    build_governance_review_packet,
    build_problem_brief_request,
    build_world_generation_request,
)


def run_process(
    *,
    task_text: str,
    process_id: str | None = None,
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
) -> dict[str, Any]:
    intake_request = build_problem_brief_request(
        task_text=task_text,
        attachments=attachments,
        process_id=process_id,
    )
    resolved_process_id = intake_request["process_id"]
    resolved_ledger_path = _ledger_path(output_dir, ledger_path)
    result: dict[str, Any] = {
        "process_id": resolved_process_id,
        "status": intake_request["status"],
        "intake_request": intake_request,
        "ledger_path": str(resolved_ledger_path) if resolved_ledger_path else None,
    }
    _record(
        resolved_ledger_path,
        process_id=resolved_process_id,
        stage="problem_space_intake",
        status=intake_request["status"],
    )

    if problem_space_brief is None and intake_endpoints:
        intake_run = run_intake_models(
            task_text=task_text,
            attachments=attachments,
            endpoints=intake_endpoints,
            process_id=resolved_process_id,
        )
        result["intake_model_run"] = intake_run
        problem_space_brief = _first_complete(intake_run, "problem_space_brief")

    if problem_space_brief is None:
        return result

    result["problem_space_brief"] = problem_space_brief
    _record(
        resolved_ledger_path,
        process_id=resolved_process_id,
        stage="problem_space_brief",
        status="complete",
        summary={"brief_id": problem_space_brief.get("brief_id")},
    )

    world_generation_request = build_world_generation_request(
        brief=problem_space_brief,
        source_world=world,
        process_id=resolved_process_id,
    )
    result["world_generation_request"] = world_generation_request
    result["status"] = world_generation_request["status"]
    _record(
        resolved_ledger_path,
        process_id=resolved_process_id,
        stage="world_generation_request",
        status=world_generation_request["status"],
    )

    if world is None and world_generation_endpoints:
        world_run = run_world_generation_models(
            brief=problem_space_brief,
            endpoints=world_generation_endpoints,
            process_id=resolved_process_id,
        )
        result["world_generation_model_run"] = world_run
        response = _first_complete(world_run, "world_generation_response")
        world = response.get("world") if response else None

    if world is None:
        return result

    result["world"] = world
    _record(
        resolved_ledger_path,
        process_id=resolved_process_id,
        stage="world",
        status="complete",
        summary={"world_id": world.get("world_id")},
    )

    if output_dir is not None:
        harbor_summary = materialize_harbor_task_package(
            output_dir=output_dir / "harbor_task",
            brief=problem_space_brief,
            worlds=[world],
            task_id=resolved_process_id,
        )
        result["harbor_task_package"] = harbor_summary
        _record(
            resolved_ledger_path,
            process_id=resolved_process_id,
            stage="harbor_task_package",
            status=harbor_summary["status"],
            artifact_refs=[str(output_dir / "harbor_task")],
        )

    if task_run is None:
        result["status"] = "awaiting_task_run"
        return result

    result["task_run"] = task_run
    _record(
        resolved_ledger_path,
        process_id=resolved_process_id,
        stage="task_run",
        status="complete",
        summary={"run_id": task_run.get("run_id")},
    )

    task_run = _run_review_if_needed(
        world=world,
        task_run=task_run,
        review_endpoints=review_endpoints,
        result=result,
    )
    result["task_run"] = task_run
    evidence = task_run.get("evidence", task_run)
    logic_evaluation = evaluate_logic_profile(world.get("logic_profile", {}), evidence).to_dict()
    result["logic_evaluation"] = logic_evaluation
    _record(
        resolved_ledger_path,
        process_id=resolved_process_id,
        stage="logic_evaluation",
        status=logic_evaluation["overall_status"],
    )

    operation_run = _run_operation_stage(
        brief=problem_space_brief,
        world=world,
        operation_plan=operation_plan,
        operation_endpoints=operation_endpoints,
    )
    result["operation_run"] = operation_run
    _record(
        resolved_ledger_path,
        process_id=resolved_process_id,
        stage="operation_orchestration",
        status=operation_run["status"],
    )

    if operation_run["status"] == "awaiting_agent_plan":
        result["status"] = "awaiting_operation_plan"
        return result

    governance_packet = build_governance_review_packet(
        brief=problem_space_brief,
        source_world=world,
        operation_run=operation_run,
        process_id=resolved_process_id,
    )
    result["governance_review"] = governance_packet
    _record(
        resolved_ledger_path,
        process_id=resolved_process_id,
        stage="governance_review",
        status=governance_packet["status"],
        summary={"candidate_count": len(governance_packet["candidates"])},
    )

    if governance_proposal is None or governance_decision is None:
        result["status"] = "awaiting_governance_decision"
        return result

    governance = apply_governance_decision(
        brief=problem_space_brief,
        source_world=world,
        proposal=governance_proposal,
        decision=governance_decision,
        process_id=resolved_process_id,
    )
    result["governance"] = governance
    result["status"] = governance["status"]
    _record(
        resolved_ledger_path,
        process_id=resolved_process_id,
        stage="governance_application",
        status=governance["status"],
    )
    return result


def _ledger_path(output_dir: Path | None, ledger_path: Path | None) -> Path | None:
    if ledger_path is not None:
        return ledger_path
    if output_dir is not None:
        return output_dir / "process_ledger.jsonl"
    return None


def _run_review_if_needed(
    *,
    world: dict[str, Any],
    task_run: dict[str, Any],
    review_endpoints: list[ModelEndpoint] | None,
    result: dict[str, Any],
) -> dict[str, Any]:
    evidence = task_run.get("evidence", task_run)
    if not review_endpoints or evidence.get("agentic_review"):
        return task_run

    review_run = run_review_models(world, task_run, review_endpoints)
    result["review_model_run"] = review_run
    review = _first_complete(review_run, "review")
    if review is None:
        return task_run
    return attach_review_to_run(task_run, review)


def _run_operation_stage(
    *,
    brief: dict[str, Any],
    world: dict[str, Any],
    operation_plan: dict[str, Any] | None,
    operation_endpoints: list[ModelEndpoint] | None,
) -> dict[str, Any]:
    if operation_plan is not None:
        return run_operation_orchestrator(
            brief=brief,
            worlds=[world],
            operation_plan=operation_plan,
        ).to_dict()
    if operation_endpoints:
        model_run = run_operation_models(
            brief=brief,
            worlds=[world],
            endpoints=operation_endpoints,
        )
        operation_result = _first_complete_result(model_run)
        if operation_result is not None:
            return {
                "status": operation_result["status"],
                "request": None,
                "execution": operation_result.get("execution"),
                "model_run": model_run,
            }
        return {
            "status": "operation_model_error",
            "request": None,
            "execution": None,
            "model_run": model_run,
        }
    return run_operation_orchestrator(brief=brief, worlds=[world]).to_dict()


def _first_complete(output: dict[str, Any], key: str) -> Any | None:
    result = _first_complete_result(output)
    return result.get(key) if result else None


def _first_complete_result(output: dict[str, Any]) -> dict[str, Any] | None:
    for result in output.get("results", []):
        if result.get("status") in {"complete", "certified"}:
            return result
    return None


def _record(
    ledger_path: Path | None,
    *,
    process_id: str,
    stage: str,
    status: str,
    summary: dict[str, Any] | None = None,
    artifact_refs: list[str] | None = None,
) -> None:
    if ledger_path is None:
        return
    append_ledger_entry(
        ledger_path,
        process_id=process_id,
        stage=stage,
        status=status,
        summary=summary,
        artifact_refs=artifact_refs,
    )
