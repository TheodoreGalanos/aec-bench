# ABOUTME: Drives deterministic preflight submissions through the real SSC-03 hydraulic operations.
# ABOUTME: Lets calibration campaigns smoke action-driven packages without model calls or static action IDs.

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, cast

from aec_bench.meta_harness.evidence_lifecycle import (
    execute_lifecycle_operation,
    read_evidence_lifecycle_state,
)
from aec_bench.meta_harness.evidence_lifecycle_episode import (
    InProcessLifecycleEpisodeEnvironment,
    LifecycleEpisodeEnvironment,
    LifecycleEpisodeRequest,
    LifecycleEpisodeResult,
    LifecycleEpisodeUsage,
)
from aec_bench.task_world_templates.lifecycles.ssc03_hydraulic_interaction import (
    validated_ssc03_hydraulic_interaction_variant,
)
from aec_bench.task_world_templates.lifecycles.ssc03_hydraulic_interaction_verifier import (
    SCENARIO_IDS,
    ClaimBoundary,
)

_CLAIM_BOUNDARY = ClaimBoundary(
    evidence_class="benchmark_owned_synthetic_screening",
    solver_fidelity="not_swmm_equivalent",
    authority_status="no_authority_approval",
    standards_status="no_standards_compliance_claim",
    project_evidence_status="not_project_design_evidence",
    model_evidence_status="no_model_performance_holdout_or_transfer_result",
    learning_status="no_post_training_or_continual_learning_result",
).model_dump(mode="json")


def build_ssc03_hydraulic_smoke_environment(package_dir: Path) -> LifecycleEpisodeEnvironment:
    """Build a verifier-independent environment for one validated public hydraulic package."""
    package = Path(package_dir)
    validated_ssc03_hydraulic_interaction_variant(package)

    def execute(request: LifecycleEpisodeRequest) -> LifecycleEpisodeResult:
        write_ssc03_hydraulic_smoke_submission(
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


def write_ssc03_hydraulic_smoke_submission(
    package_dir: Path,
    run_dir: Path,
    checkpoint_id: str,
    session_id: str,
    submission_path: Path,
) -> None:
    """Write one deterministic task submission without advancing the host checkpoint."""
    package = Path(package_dir)
    run = Path(run_dir)
    variant = validated_ssc03_hydraulic_interaction_variant(package)
    variant_id = str(variant["variant_id"])
    if checkpoint_id == "baseline_analysis":
        submission = _baseline_submission(package, run, session_id=session_id)
    elif checkpoint_id == "revision_analysis":
        submission = _revision_submission(
            package,
            run,
            session_id=session_id,
            variant_id=variant_id,
        )
    elif checkpoint_id == "closeout_review":
        submission = _closeout_submission(package, run)
    else:
        raise ValueError(f"unsupported hydraulic smoke checkpoint: {checkpoint_id}")
    _write_json(Path(submission_path), submission)


def _baseline_submission(package: Path, run: Path, *, session_id: str) -> dict[str, Any]:
    actions = _execute_calculation_operations(
        package,
        run,
        checkpoint_id="baseline_analysis",
        session_id=session_id,
    )
    decisions = [_decision(run, actions, scenario_id=scenario_id, revision=False) for scenario_id in SCENARIO_IDS]
    return {
        "checkpoint_id": "baseline_analysis",
        "visible_source_state_sha256": _visible_source_sha256(run),
        "selected_operations": _selected_operations(actions),
        "accepted_decisions": decisions,
        "readiness_decision": _readiness(decisions),
        "claim_boundary": copy.deepcopy(_CLAIM_BOUNDARY),
    }


def _revision_submission(
    package: Path,
    run: Path,
    *,
    session_id: str,
    variant_id: str,
) -> dict[str, Any]:
    baseline = _read_json(run / "episodes" / "baseline_analysis" / "submission.json")
    baseline_decisions = cast(list[dict[str, Any]], baseline["accepted_decisions"])
    revision_action = _execute_operation(
        package,
        run,
        checkpoint_id="revision_analysis",
        operation_id="source-revision.current",
        session_id=session_id,
    )
    actions = _execute_calculation_operations(
        package,
        run,
        checkpoint_id="revision_analysis",
        session_id=session_id,
    )
    baseline_by_scenario = {str(decision["scenario_id"]): decision for decision in baseline_decisions}
    decisions: list[dict[str, Any]] = []
    supersession_lineage: list[dict[str, str]] = []
    for scenario_id in SCENARIO_IDS:
        replacement = _decision(run, actions, scenario_id=scenario_id, revision=True)
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
        "visible_source_state_sha256": _visible_source_sha256(run),
        "selected_operations": {
            **_selected_operations(actions),
            "source-revision.current": str(revision_action["action_id"]),
        },
        "accepted_decisions": decisions,
        "supersession_lineage": supersession_lineage,
        "readiness_decision": _readiness(decisions),
        "claim_boundary": copy.deepcopy(_CLAIM_BOUNDARY),
    }


def _closeout_submission(package: Path, run: Path) -> dict[str, Any]:
    revision = _read_json(run / "episodes" / "revision_analysis" / "submission.json")
    selected_operations = cast(dict[str, str], revision["selected_operations"])
    decisions = cast(list[dict[str, Any]], revision["accepted_decisions"])
    supersession_lineage = cast(list[dict[str, str]], revision["supersession_lineage"])
    visible_source_state_sha256 = str(revision["visible_source_state_sha256"])
    readiness = str(revision["readiness_decision"])
    run_reference, report_reference = _run_references(package, run, selected_operations)
    return {
        "checkpoint_id": "closeout_review",
        "visible_source_state_sha256": visible_source_state_sha256,
        "selected_operations": selected_operations,
        "run_reference": run_reference,
        "report_reference": report_reference,
        "accepted_decisions": decisions,
        "supersession_lineage": supersession_lineage,
        "readiness_decision": readiness,
        "claim_boundary": copy.deepcopy(_CLAIM_BOUNDARY),
        "memo": {
            "visible_source_state_sha256": visible_source_state_sha256,
            "run_reference": copy.deepcopy(run_reference),
            "report_reference": copy.deepcopy(report_reference),
            "decision_ids": {str(decision["scenario_id"]): str(decision["decision_id"]) for decision in decisions},
            "supersession_lineage": supersession_lineage,
            "readiness_decision": readiness,
            "claim_boundary": copy.deepcopy(_CLAIM_BOUNDARY),
        },
    }


def _execute_calculation_operations(
    package: Path,
    run: Path,
    *,
    checkpoint_id: str,
    session_id: str,
) -> dict[str, dict[str, Any]]:
    actions: dict[str, dict[str, Any]] = {}
    for scenario_id in SCENARIO_IDS:
        for operation_id in (
            f"hydrology.{scenario_id}",
            f"detention-outlet.{scenario_id}.declared-outlet",
            f"network-hgl.{scenario_id}.declared-tailwater",
        ):
            actions[operation_id] = _execute_operation(
                package,
                run,
                checkpoint_id=checkpoint_id,
                operation_id=operation_id,
                session_id=session_id,
            )
    return actions


def _execute_operation(
    package: Path,
    run: Path,
    *,
    checkpoint_id: str,
    operation_id: str,
    session_id: str,
) -> dict[str, Any]:
    return execute_lifecycle_operation(
        package,
        run,
        checkpoint_id=checkpoint_id,
        operation_id=operation_id,
        visible_source_state_sha256=_visible_source_sha256(run),
        reason=f"Smoke {operation_id} against the declared source.",
        session_id=session_id,
    )


def _decision(
    run: Path,
    actions: dict[str, dict[str, Any]],
    *,
    scenario_id: str,
    revision: bool,
) -> dict[str, Any]:
    hydrology = _origin_action_id(actions[f"hydrology.{scenario_id}"])
    detention = _origin_action_id(actions[f"detention-outlet.{scenario_id}.declared-outlet"])
    hgl = _origin_action_id(actions[f"network-hgl.{scenario_id}.declared-tailwater"])
    detention_result = _read_json(run / "lifecycle_operations" / detention / "artifacts" / "detention-outlet.json")
    hgl_result = _read_json(run / "lifecycle_operations" / hgl / "artifacts" / "network-hgl.json")
    criteria = dict(detention_result["criteria"]) | dict(hgl_result["criteria"])
    failed_criteria = sorted(key for key, passed in criteria.items() if not passed)
    phase = "revision" if revision else "baseline"
    return {
        "decision_id": f"decision.{scenario_id}.{phase}",
        "scenario_id": scenario_id,
        "hydrology_action_id": hydrology,
        "detention_action_id": detention,
        "hgl_action_id": hgl,
        "hydraulic_run_id": detention_result["hydraulic_run_id"],
        "screening_outcome": "criteria_not_met" if failed_criteria else "criteria_met",
        "failed_criteria": failed_criteria,
    }


def _decision_action_ids(decision: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(decision["hydrology_action_id"]),
        str(decision["detention_action_id"]),
        str(decision["hgl_action_id"]),
    )


def _selected_operations(actions: dict[str, dict[str, Any]]) -> dict[str, str]:
    return {operation_id: str(action["action_id"]) for operation_id, action in sorted(actions.items())}


def _readiness(decisions: list[dict[str, Any]]) -> str:
    return (
        "not_screening_ready"
        if any(decision["screening_outcome"] == "criteria_not_met" for decision in decisions)
        else "screening_ready"
    )


def _run_references(
    package: Path,
    run: Path,
    selected_operations: dict[str, str],
) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    actions_by_id = {
        str(action["action_id"]): action
        for checkpoint in read_evidence_lifecycle_state(package, run)["checkpoint_runs"]
        for action in checkpoint["operation_actions"]
    }
    runs: dict[str, dict[str, str]] = {}
    reports: dict[str, dict[str, str]] = {}
    for scenario_id in SCENARIO_IDS:
        detention_operation = f"detention-outlet.{scenario_id}.declared-outlet"
        hgl_operation = f"network-hgl.{scenario_id}.declared-tailwater"
        selected_detention = actions_by_id[selected_operations[detention_operation]]
        selected_hgl = actions_by_id[selected_operations[hgl_operation]]
        detention = _origin_action_id(selected_detention)
        hgl = _origin_action_id(selected_hgl)
        detention_result = _read_json(run / "lifecycle_operations" / detention / "artifacts" / "detention-outlet.json")
        hgl_result = _read_json(run / "lifecycle_operations" / hgl / "artifacts" / "network-hgl.json")
        report = run / "lifecycle_operations" / hgl / "artifacts" / "report.md"
        runs[scenario_id] = {
            "selected_operation_action_id": str(selected_detention["action_id"]),
            "canonical_detention_action_id": detention,
            "hydraulic_run_id": str(detention_result["hydraulic_run_id"]),
            "run_manifest_sha256": str(detention_result["hydraulic_run_manifest_sha256"]),
        }
        reports[scenario_id] = {
            "selected_operation_action_id": str(selected_hgl["action_id"]),
            "canonical_hgl_action_id": hgl,
            "hydraulic_run_id": str(hgl_result["hydraulic_run_id"]),
            "report_sha256": hashlib.sha256(report.read_bytes()).hexdigest(),
        }
    return runs, reports


def _origin_action_id(action: dict[str, Any]) -> str:
    return str(action.get("retained_from_action_id") or action["action_id"])


def _visible_source_sha256(run: Path) -> str:
    source = _read_json(run / "workspace" / "hydraulics" / "current-source.json")
    return str(source["visible_source_state_sha256"])


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return cast(dict[str, Any], payload)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
