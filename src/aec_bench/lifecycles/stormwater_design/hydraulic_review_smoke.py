# ABOUTME: Drives deterministic preflight submissions through the real hydraulic operations.
# ABOUTME: Lets calibration campaigns smoke action-driven packages without model calls or static action IDs.

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, cast

from aec_bench.lifecycles.runtime.episode import (
    InProcessLifecycleEpisodeEnvironment,
    LifecycleEpisodeEnvironment,
    LifecycleEpisodeRequest,
    LifecycleEpisodeResult,
    LifecycleEpisodeUsage,
)
from aec_bench.lifecycles.runtime.operation_protocol import LifecycleOperationResolver
from aec_bench.lifecycles.stormwater_design.hydraulic_evidence import SCENARIO_IDS
from aec_bench.lifecycles.stormwater_design.hydraulic_review import (
    build_hydraulic_operation_resolver,
    validated_hydraulic_review_variant,
)
from aec_bench.lifecycles.stormwater_design.hydraulic_smoke import (
    CLAIM_BOUNDARY,
    build_scenario_decision,
    execute_calculation_operations,
    execute_operation,
    read_json_object,
    readiness,
    run_references,
    selected_operations,
    visible_source_sha256,
    write_json_object,
)


def build_hydraulic_review_smoke_environment(package_dir: Path) -> LifecycleEpisodeEnvironment:
    """Build a verifier-independent environment for one validated public hydraulic package."""
    package = Path(package_dir)
    validated_hydraulic_review_variant(package)

    def execute(request: LifecycleEpisodeRequest) -> LifecycleEpisodeResult:
        write_hydraulic_review_smoke_submission(
            package,
            Path(request.run_dir),
            request.checkpoint_id,
            request.session_id,
            Path(request.submission_path),
        )
        return LifecycleEpisodeResult(
            episode_id=request.episode_id,
            attempt_id=request.attempt_id,
            session_id=request.session_id,
            checkpoint_ids=request.checkpoint_ids,
            execution_mode=request.execution_mode,
            memory_visibility_policy=request.memory_visibility_policy,
            status="completed",
            requested_adapter=request.requested_adapter,
            requested_model=request.requested_model,
            max_turns_per_session=request.max_turns_per_session,
            adapter="in_process",
            resolved_model="hydraulic-smoke",
            configuration={"source": "registered_task_smoke"},
            usage=LifecycleEpisodeUsage(),
        )

    return InProcessLifecycleEpisodeEnvironment(
        executor=execute,
        requested_model="hydraulic-smoke",
    )


def write_hydraulic_review_smoke_submission(
    package_dir: Path,
    run_dir: Path,
    checkpoint_id: str,
    session_id: str,
    submission_path: Path,
) -> None:
    """Write one deterministic task submission without advancing the host checkpoint."""
    package = Path(package_dir)
    run = Path(run_dir)
    variant = validated_hydraulic_review_variant(package)
    variant_id = str(variant["variant_id"])
    operation_resolver = build_hydraulic_operation_resolver(package, run)
    if checkpoint_id == "baseline_analysis":
        submission = _baseline_submission(
            package,
            run,
            session_id=session_id,
            operation_resolver=operation_resolver,
        )
    elif checkpoint_id == "revision_analysis":
        submission = _revision_submission(
            package,
            run,
            session_id=session_id,
            variant_id=variant_id,
            operation_resolver=operation_resolver,
        )
    elif checkpoint_id == "closeout_review":
        submission = _closeout_submission(package, run, operation_resolver=operation_resolver)
    else:
        raise ValueError(f"unsupported hydraulic smoke checkpoint: {checkpoint_id}")
    write_json_object(Path(submission_path), submission)


def _baseline_submission(
    package: Path,
    run: Path,
    *,
    session_id: str,
    operation_resolver: LifecycleOperationResolver,
) -> dict[str, Any]:
    actions = execute_calculation_operations(
        package,
        run,
        checkpoint_id="baseline_analysis",
        session_id=session_id,
        operation_resolver=operation_resolver,
    )
    decisions = [
        build_scenario_decision(run, actions, scenario_id=scenario_id, phase="baseline") for scenario_id in SCENARIO_IDS
    ]
    return {
        "checkpoint_id": "baseline_analysis",
        "visible_source_state_sha256": visible_source_sha256(run),
        "selected_operations": selected_operations(actions),
        "accepted_decisions": decisions,
        "readiness_decision": readiness(decisions),
        "claim_boundary": copy.deepcopy(CLAIM_BOUNDARY),
    }


def _revision_submission(
    package: Path,
    run: Path,
    *,
    session_id: str,
    variant_id: str,
    operation_resolver: LifecycleOperationResolver,
) -> dict[str, Any]:
    baseline = read_json_object(run / "episodes" / "baseline_analysis" / "submission.json")
    baseline_decisions = cast(list[dict[str, Any]], baseline["accepted_decisions"])
    revision_action = execute_operation(
        package,
        run,
        checkpoint_id="revision_analysis",
        operation_id="source-revision.current",
        session_id=session_id,
        operation_resolver=operation_resolver,
    )
    actions = execute_calculation_operations(
        package,
        run,
        checkpoint_id="revision_analysis",
        session_id=session_id,
        operation_resolver=operation_resolver,
    )
    baseline_by_scenario = {str(decision["scenario_id"]): decision for decision in baseline_decisions}
    decisions: list[dict[str, Any]] = []
    supersession_lineage: list[dict[str, str]] = []
    for scenario_id in SCENARIO_IDS:
        replacement = build_scenario_decision(run, actions, scenario_id=scenario_id, phase="revision")
        baseline_decision = baseline_by_scenario[scenario_id]
        changed = _decision_action_ids(replacement) != _decision_action_ids(baseline_decision)
        decisions.append(replacement if changed else baseline_decision)
        if changed:
            supersession_lineage.append(
                {
                    "scenario_id": scenario_id,
                    "superseded_decision_id": str(baseline_decision["decision_id"]),
                    "replacement_decision_id": str(replacement["decision_id"]),
                }
            )
    return {
        "checkpoint_id": "revision_analysis",
        "revision_id": variant_id,
        "visible_source_state_sha256": visible_source_sha256(run),
        "selected_operations": {
            **selected_operations(actions),
            "source-revision.current": str(revision_action["action_id"]),
        },
        "accepted_decisions": decisions,
        "supersession_lineage": supersession_lineage,
        "readiness_decision": readiness(decisions),
        "claim_boundary": copy.deepcopy(CLAIM_BOUNDARY),
    }


def _closeout_submission(
    package: Path,
    run: Path,
    *,
    operation_resolver: LifecycleOperationResolver,
) -> dict[str, Any]:
    revision = read_json_object(run / "episodes" / "revision_analysis" / "submission.json")
    selected_operations = cast(dict[str, str], revision["selected_operations"])
    decisions = cast(list[dict[str, Any]], revision["accepted_decisions"])
    supersession_lineage = cast(list[dict[str, str]], revision["supersession_lineage"])
    visible_source_state_sha256 = str(revision["visible_source_state_sha256"])
    readiness = str(revision["readiness_decision"])
    run_reference, report_reference = run_references(
        package,
        run,
        selected_operations,
        operation_resolver=operation_resolver,
    )
    return {
        "checkpoint_id": "closeout_review",
        "visible_source_state_sha256": visible_source_state_sha256,
        "selected_operations": selected_operations,
        "run_reference": run_reference,
        "report_reference": report_reference,
        "accepted_decisions": decisions,
        "supersession_lineage": supersession_lineage,
        "readiness_decision": readiness,
        "claim_boundary": copy.deepcopy(CLAIM_BOUNDARY),
        "memo": {
            "visible_source_state_sha256": visible_source_state_sha256,
            "run_reference": copy.deepcopy(run_reference),
            "report_reference": copy.deepcopy(report_reference),
            "decision_ids": {str(decision["scenario_id"]): str(decision["decision_id"]) for decision in decisions},
            "supersession_lineage": supersession_lineage,
            "readiness_decision": readiness,
            "claim_boundary": copy.deepcopy(CLAIM_BOUNDARY),
        },
    }


def _decision_action_ids(decision: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(decision["hydrology_action_id"]),
        str(decision["detention_action_id"]),
        str(decision["hgl_action_id"]),
    )
