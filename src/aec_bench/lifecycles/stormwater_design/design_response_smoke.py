# ABOUTME: Drives both bounded intervention policies through the real four-checkpoint lifecycle.
# ABOUTME: Provides credential-free task proofs with production operations and immutable submissions.

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
from aec_bench.lifecycles.stormwater_design.design_response import (
    build_hydraulic_design_response_resolver,
    validated_hydraulic_design_response_package,
)
from aec_bench.lifecycles.stormwater_design.hydraulic_evidence import SCENARIO_IDS
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
from aec_bench.lifecycles.stormwater_design.hydraulics.interventions import get_hydraulic_intervention


def build_hydraulic_design_response_smoke_environment(
    package_dir: Path,
    *,
    selected_intervention_id: str = "controlled_orifice_resize",
) -> LifecycleEpisodeEnvironment:
    """Build a credential-free environment for one declared intervention policy."""
    package = Path(package_dir)
    validated_hydraulic_design_response_package(package)
    intervention = get_hydraulic_intervention(selected_intervention_id)

    def execute(request: LifecycleEpisodeRequest) -> LifecycleEpisodeResult:
        write_hydraulic_design_response_smoke_submission(
            package,
            Path(request.run_dir),
            request.checkpoint_id,
            request.session_id,
            Path(request.submission_path),
            selected_intervention_id=intervention.intervention_id,
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
            resolved_model=f"hydraulic-intervention-smoke:{intervention.intervention_id}",
            configuration={
                "source": "registered_task_smoke",
                "selected_intervention_id": intervention.intervention_id,
            },
            usage=LifecycleEpisodeUsage(),
        )

    return InProcessLifecycleEpisodeEnvironment(
        executor=execute,
        requested_model=f"hydraulic-intervention-smoke:{intervention.intervention_id}",
    )


def write_hydraulic_design_response_smoke_submission(
    package_dir: Path,
    run_dir: Path,
    checkpoint_id: str,
    session_id: str,
    submission_path: Path,
    *,
    selected_intervention_id: str,
) -> None:
    """Write one deterministic task submission without advancing the host checkpoint."""
    package = Path(package_dir)
    run = Path(run_dir)
    validated_hydraulic_design_response_package(package)
    intervention = get_hydraulic_intervention(selected_intervention_id)
    operation_resolver = build_hydraulic_design_response_resolver(package, run)
    if checkpoint_id == "problem_analysis":
        submission = _problem_submission(
            package,
            run,
            session_id=session_id,
            operation_resolver=operation_resolver,
        )
    elif checkpoint_id == "intervention_selection":
        submission = _selection_submission(run, intervention.intervention_id)
    elif checkpoint_id == "intervention_analysis":
        submission = _intervention_submission(
            package,
            run,
            session_id=session_id,
            intervention_id=intervention.intervention_id,
            operation_resolver=operation_resolver,
        )
    elif checkpoint_id == "closeout_review":
        submission = _closeout_submission(
            package,
            run,
            intervention.intervention_id,
            operation_resolver=operation_resolver,
        )
    else:
        raise ValueError(f"unsupported hydraulic intervention smoke checkpoint: {checkpoint_id}")
    write_json_object(Path(submission_path), submission)


def _problem_submission(
    package: Path,
    run: Path,
    *,
    session_id: str,
    operation_resolver: LifecycleOperationResolver,
) -> dict[str, Any]:
    actions = execute_calculation_operations(
        package,
        run,
        checkpoint_id="problem_analysis",
        session_id=session_id,
        operation_resolver=operation_resolver,
    )
    decisions = [
        build_scenario_decision(run, actions, scenario_id=scenario_id, phase="problem") for scenario_id in SCENARIO_IDS
    ]
    return {
        "checkpoint_id": "problem_analysis",
        "visible_source_state_sha256": visible_source_sha256(run),
        "selected_operations": selected_operations(actions),
        "accepted_decisions": decisions,
        "readiness_decision": readiness(decisions),
        "claim_boundary": copy.deepcopy(CLAIM_BOUNDARY),
    }


def _selection_submission(run: Path, intervention_id: str) -> dict[str, Any]:
    return {
        "checkpoint_id": "intervention_selection",
        "visible_source_state_sha256": visible_source_sha256(run),
        "selected_intervention_id": intervention_id,
        "selection_basis": (
            "Select one bounded outlet intervention before its calculated consequences are exposed, then verify "
            "both basin and downstream criteria."
        ),
        "claim_boundary": copy.deepcopy(CLAIM_BOUNDARY),
    }


def _intervention_submission(
    package: Path,
    run: Path,
    *,
    session_id: str,
    intervention_id: str,
    operation_resolver: LifecycleOperationResolver,
) -> dict[str, Any]:
    problem = read_json_object(run / "episodes" / "problem_analysis" / "submission.json")
    problem_decisions = cast(list[dict[str, Any]], problem["accepted_decisions"])
    activation = execute_operation(
        package,
        run,
        checkpoint_id="intervention_analysis",
        operation_id="source-intervention.selected",
        session_id=session_id,
        operation_resolver=operation_resolver,
    )
    actions = execute_calculation_operations(
        package,
        run,
        checkpoint_id="intervention_analysis",
        session_id=session_id,
        operation_resolver=operation_resolver,
    )
    decisions = [
        build_scenario_decision(run, actions, scenario_id=scenario_id, phase="intervention")
        for scenario_id in SCENARIO_IDS
    ]
    problem_by_scenario = {str(item["scenario_id"]): item for item in problem_decisions}
    supersession = [
        {
            "scenario_id": scenario_id,
            "superseded_decision_id": str(problem_by_scenario[scenario_id]["decision_id"]),
            "replacement_decision_id": f"decision.{scenario_id}.intervention",
        }
        for scenario_id in SCENARIO_IDS
    ]
    return {
        "checkpoint_id": "intervention_analysis",
        "selected_intervention_id": intervention_id,
        "visible_source_state_sha256": visible_source_sha256(run),
        "selected_operations": {
            **selected_operations(actions),
            "source-intervention.selected": str(activation["action_id"]),
        },
        "accepted_decisions": decisions,
        "supersession_lineage": supersession,
        "readiness_decision": readiness(decisions),
        "claim_boundary": copy.deepcopy(CLAIM_BOUNDARY),
    }


def _closeout_submission(
    package: Path,
    run: Path,
    intervention_id: str,
    *,
    operation_resolver: LifecycleOperationResolver,
) -> dict[str, Any]:
    intervention = read_json_object(run / "episodes" / "intervention_analysis" / "submission.json")
    selected_operations = cast(dict[str, str], intervention["selected_operations"])
    decisions = cast(list[dict[str, Any]], intervention["accepted_decisions"])
    supersession = cast(list[dict[str, str]], intervention["supersession_lineage"])
    visible_source = str(intervention["visible_source_state_sha256"])
    readiness = str(intervention["readiness_decision"])
    run_reference, report_reference = run_references(
        package,
        run,
        selected_operations,
        operation_resolver=operation_resolver,
    )
    memo = {
        "selected_intervention_id": intervention_id,
        "visible_source_state_sha256": visible_source,
        "run_reference": copy.deepcopy(run_reference),
        "report_reference": copy.deepcopy(report_reference),
        "decision_ids": {str(item["scenario_id"]): str(item["decision_id"]) for item in decisions},
        "supersession_lineage": supersession,
        "readiness_decision": readiness,
        "claim_boundary": copy.deepcopy(CLAIM_BOUNDARY),
    }
    return {
        "checkpoint_id": "closeout_review",
        "selected_intervention_id": intervention_id,
        "visible_source_state_sha256": visible_source,
        "selected_operations": selected_operations,
        "run_reference": run_reference,
        "report_reference": report_reference,
        "memo": memo,
        "accepted_decisions": decisions,
        "supersession_lineage": supersession,
        "readiness_decision": readiness,
        "claim_boundary": copy.deepcopy(CLAIM_BOUNDARY),
    }
