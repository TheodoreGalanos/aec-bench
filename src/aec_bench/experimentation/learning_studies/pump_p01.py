"""Learning Studies binding for complete wastewater pump-station journeys."""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.contracts.authority_evidence import AuthorityEvidenceKind, AuthorityEvidenceRef
from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
from aec_bench.contracts.trial_record import (
    AgentConfiguration,
    AuthorityExpectation,
    CostRecord,
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
from aec_bench.experimentation.learning_studies.assessment import OutcomeProjection, ProjectionResult
from aec_bench.experimentation.learning_studies.worlds import (
    WorldConsolidationOperation,
    WorldLearningBinding,
    WorldLearningExecutionCondition,
    WorldLearningTarget,
    WorldLearningTreatmentKind,
    build_world_learning_operations,
    resolve_world_learning_target,
    world_canonical_reward,
)
from aec_bench.harness.world_trials import WorldActorSessionRunner
from aec_bench.ledger.artifact_repository import ArtifactRepository
from aec_bench.trials import PlannedTrial
from aec_bench.worlds.stewardship.wastewater_pump_station.evaluation import (
    evaluate_pump_station_reference_run,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.reference_controller import (
    run_pump_station_reference_controller,
)
from aec_bench.worlds.tasks import WorldTask

PUMP_STATION_WORLD_ID = "wastewater-pump-station-stewardship.v1"
PUMP_RS1_PROFILE_ID = "pump-station-reference-system.asw-8-rs1.v1"
PUMP_RS2_PROFILE_ID = "pump-station-reference-system.asw-8-rs2.v1"
PUMP_RS1_TASK_ID = f"world/{PUMP_STATION_WORLD_ID}/{PUMP_RS1_PROFILE_ID}"
PUMP_RS2_TASK_ID = f"world/{PUMP_STATION_WORLD_ID}/{PUMP_RS2_PROFILE_ID}"
PUMP_JOURNEY_PUBLIC_FEEDBACK_VIEW_ID = "pump-journey-stewardship-public-feedback"
PUMP_JOURNEY_CONSOLIDATION_OPERATION_ID = "update-pump-stewardship-memory"
PUMP_STATION_WORLD_EVIDENCE_PROTOCOL = "aec-bench/pump-station-trial/1"

_PROFILE_TO_REFERENCE_SYSTEM = {
    PUMP_RS1_PROFILE_ID: PUMP_RS1_PROFILE_ID,
    PUMP_RS2_PROFILE_ID: PUMP_RS2_PROFILE_ID,
}
_METRIC_FIELDS = (
    "maintenance_intervention_count",
    "obligation_breach_count",
    "restriction_breach_count",
    "evidence_integrity_gap_count",
    "consumed_maintenance_resource_count",
    "handover_count",
    "generated_work_count",
    "terminal_work_count",
)
_GATE_FIELDS = (
    "artifact_and_replay_integrity",
    "output_and_action_contract_validity",
    "authority_and_execution_consistency",
    "decision_time_validity",
    "obligation_and_restriction_integrity",
    "physical_and_service_outcomes_available",
    "resource_stewardship_available",
    "evidence_and_record_integrity",
    "handover_continuity_integrity",
    "terminal_stewardship_available",
)
_FORBIDDEN_FEEDBACK_KEYS = {
    "expected_answer",
    "expected_response",
    "gold",
    "private_path",
    "secret",
    "verifier_source",
    "required_response",
    "instrument_condition",
    "visual_alert_conditions",
    "required_consecutive_alert_readings",
    "operations_authority_id",
    "accepted_evidence_id",
    "reference_controller",
    "reference_system_descriptor",
    "physical_member",
    "initial_state",
    "event_schedule",
}
_FORBIDDEN_FEEDBACK_PATH_PARTS = ("/hidden/", "hidden/", "gold-submissions", "verifier-config")
_FORBIDDEN_LEARNER_MARKERS = (
    b"/hidden/",
    b"expected_answer",
    b"expected_response",
    b"gold-submissions",
    b"private_path",
    b"verifier-config",
    b"operations_authority_id",
    b"accepted_evidence_id",
    b"reference_controller",
    b"reference_system_descriptor",
    b"physical_member",
    b"initial_state_id",
    b"pump-station-reference-system.asw-8-rs2.v1",
)
_FORBIDDEN_LEARNER_FILENAMES = frozenset({"pump-world-evidence.json", "prime-world-journey-checkpoint.json"})
_INSTRUCTION = (
    "Steward the wastewater pump station through its complete maintenance and operations "
    "journey. Inspect, clear, test, verify, assign, and close work items while maintaining "
    "service capacity, resource limits, and regulatory obligations."
)


@dataclass(frozen=True, slots=True)
class PumpJourneyTrialRunner:
    """Run one complete pump journey and retain it as one ordinary trial."""

    world_run_root: Path
    deterministic: bool = True

    async def __call__(
        self,
        task: WorldTask,
        trial: PlannedTrial,
        *,
        actor: WorldActorSessionRunner,
        read_only_context_text: str | None = None,
    ) -> TrialRecord:
        del actor, read_only_context_text
        if not self.deterministic:
            raise ValueError("pump-journey-world-run-failed: real-model mode is not available in P1")
        if task.world.task_world_id != PUMP_STATION_WORLD_ID:
            raise ValueError("pump-journey-task-mismatch: task is not the registered pump world")
        if trial.task_id != task.task_id:
            raise ValueError("pump-journey-task-mismatch: planned task does not match the task")
        target = resolve_pump_task_id(task.task_id)
        reference_system_id = _PROFILE_TO_REFERENCE_SYSTEM.get(target.profile_id)
        if reference_system_id is None:
            raise ValueError(f"pump-journey-profile-unknown: {target.profile_id}")

        root = _fresh_world_root(self.world_run_root, trial.trial_id)
        try:
            world_directory = root / "world"
            run_id = f"{trial.trial_id}-world"
            episode_id = f"{trial.trial_id}-episode"
            branch_id = f"{trial.trial_id}-branch"
            started_at = datetime.now(UTC)
            result = run_pump_station_reference_controller(
                repository_root=world_directory,
                run_id=run_id,
                episode_id=episode_id,
                world_branch_id=branch_id,
                reference_system_id=reference_system_id,
            )
            completed_at = datetime.now(UTC)
            stewardship = evaluate_pump_station_reference_run(result.run)
            benchmark_valid = (
                result.semantic_outcome.evaluation.trial_valid
                and result.semantic_outcome.evaluation.artifact_valid
                and result.semantic_outcome.evaluation.policy_valid
            )
            breakdown = _pump_breakdown(result, stewardship, benchmark_valid=benchmark_valid)
            evaluation = EvaluationResult(
                reward=result.semantic_outcome.evaluation.reward,
                validity=ValidityCheck(
                    output_parseable=True,
                    schema_valid=True,
                    verifier_completed=benchmark_valid,
                    errors=[] if benchmark_valid else ["pump-station canonical replay verification failed"],
                ),
                breakdown=breakdown,
                stewardship=stewardship,
            )
            evidence_file = root / "pump-world-evidence.json"
            evidence_file.write_bytes(_reference_evidence(result))
            return _build_pump_record(
                task=task,
                trial=trial,
                evaluation=evaluation,
                evidence_file=evidence_file,
                started_at=started_at,
                completed_at=completed_at,
                execution_completed=benchmark_valid and stewardship.valid,
            )
        except Exception as error:
            raise ValueError("pump-journey-world-run-failed: reference journey failed") from error


def resolve_pump_task_id(task_id: str) -> WorldLearningTarget:
    """Resolve and constrain one exact registered pump task identity."""

    try:
        target = resolve_world_learning_target(task_id)
    except ValueError as error:
        parts = task_id.split("/") if isinstance(task_id, str) else ()
        if len(parts) == 3 and parts[0] == "world" and parts[1] != PUMP_STATION_WORLD_ID:
            raise ValueError(f"pump-journey-task-mismatch: {parts[1]}") from error
        if len(parts) == 3 and parts[1] == PUMP_STATION_WORLD_ID and str(error).startswith("world-profile-unknown"):
            raise ValueError(f"pump-journey-profile-unknown: {parts[2]}") from error
        raise
    if target.world_id != PUMP_STATION_WORLD_ID:
        raise ValueError(f"pump-journey-task-mismatch: {target.world_id}")
    if target.profile_id not in _PROFILE_TO_REFERENCE_SYSTEM:
        raise ValueError(f"pump-journey-profile-unknown: {target.profile_id}")
    return target


def pump_journey_public_feedback(record: TrialRecord) -> bytes:
    """Project the bounded public outcome of one completed pump journey."""

    if record.task_id not in {PUMP_RS1_TASK_ID, PUMP_RS2_TASK_ID}:
        raise ValueError("pump-journey-feedback-invalid: source task is not a pump task")
    if record.execution_status is not ExecutionStatus.COMPLETED:
        raise ValueError("pump-journey-feedback-invalid: execution is not complete")
    evaluation = record.evaluation
    if record.evaluation_status is not EvaluationStatus.COMPLETED or evaluation is None:
        raise ValueError("pump-journey-feedback-invalid: evaluation is unavailable")
    breakdown = _breakdown(evaluation)
    gates = breakdown.get("gates")
    metrics = breakdown.get("metrics")
    if not isinstance(gates, dict) or not isinstance(metrics, dict):
        raise ValueError("pump-journey-feedback-invalid: evaluation fields are malformed")
    payload = {
        "feedback_view_id": PUMP_JOURNEY_PUBLIC_FEEDBACK_VIEW_ID,
        "trial_id": record.trial_id,
        "task_id": record.task_id,
        "canonical_reward": world_canonical_reward(record),
        "evaluation_valid": _required_bool(breakdown, "valid"),
        "evaluation_scope": breakdown.get("evaluation_scope"),
        "gates": {key: value for key, value in gates.items() if isinstance(value, bool)},
        "metrics": {key: metrics[key] for key in _METRIC_FIELDS if key in metrics},
        "terminal_liabilities": breakdown.get("terminal_liabilities"),
        "benchmark_valid": breakdown.get("benchmark_valid"),
    }
    data = (json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()
    validate_pump_journey_public_feedback(data)
    return data


def validate_pump_journey_public_feedback(data: bytes) -> dict[str, Any]:
    """Validate the exact public pump feedback allowlist."""

    if len(data) > 1_000_000:
        raise ValueError("pump-journey-feedback-invalid: feedback exceeds 1 MiB")
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("pump-journey-feedback-invalid: feedback is not UTF-8 JSON") from error
    expected = {
        "feedback_view_id",
        "trial_id",
        "task_id",
        "canonical_reward",
        "evaluation_valid",
        "evaluation_scope",
        "gates",
        "metrics",
        "terminal_liabilities",
        "benchmark_valid",
    }
    if not isinstance(payload, dict) or set(payload) != expected:
        raise ValueError("pump-journey-feedback-invalid: feedback fields do not match the public view")
    if payload["feedback_view_id"] != PUMP_JOURNEY_PUBLIC_FEEDBACK_VIEW_ID:
        raise ValueError("pump-journey-feedback-invalid: feedback view identity does not match")
    if payload["task_id"] not in {PUMP_RS1_TASK_ID, PUMP_RS2_TASK_ID}:
        raise ValueError("pump-journey-feedback-invalid: task identity is invalid")
    reward = payload["canonical_reward"]
    if (
        isinstance(reward, bool)
        or not isinstance(reward, int | float)
        or not math.isfinite(reward)
        or not 0 <= reward <= 1
    ):
        raise ValueError("pump-journey-feedback-invalid: reward is out of bounds")
    if not isinstance(payload["trial_id"], str) or not payload["trial_id"]:
        raise ValueError("pump-journey-feedback-invalid: trial identity is missing")
    if not isinstance(payload["evaluation_valid"], bool) or payload["evaluation_scope"] not in {
        "complete_journey",
        "bounded_continuation",
    }:
        raise ValueError("pump-journey-feedback-invalid: evaluation summary is invalid")
    if not isinstance(payload["benchmark_valid"], bool):
        raise ValueError("pump-journey-feedback-invalid: benchmark validity is invalid")
    for section in ("gates", "metrics"):
        if not isinstance(payload[section], dict):
            raise ValueError("pump-journey-feedback-invalid: public evaluation section is invalid")
        required = _GATE_FIELDS if section == "gates" else _METRIC_FIELDS
        if set(payload[section]) != set(required):
            raise ValueError("pump-journey-feedback-invalid: public evaluation fields are incomplete")
        if section == "gates" and any(not isinstance(value, bool) for value in payload[section].values()):
            raise ValueError("pump-journey-feedback-invalid: gate values must be boolean")
        if section == "metrics" and any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in payload[section].values()
        ):
            raise ValueError("pump-journey-feedback-invalid: metric values must be non-negative integers")
    liabilities = payload["terminal_liabilities"]
    if not isinstance(liabilities, list) or any(not isinstance(item, str) for item in liabilities):
        raise ValueError("pump-journey-feedback-invalid: terminal liabilities are invalid")
    if _contains_forbidden(payload):
        raise ValueError("pump-journey-forbidden-material: feedback contains forbidden material")
    canonical = (json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()
    if data != canonical:
        raise ValueError("pump-journey-feedback-invalid: feedback is not canonical JSON")
    return payload


def pump_evaluation_valid(record: TrialRecord) -> float:
    """Project whether task-owned pump evaluation passed."""

    return _project_bool(record, "valid", projection="pump.evaluation-valid")


def pump_terminal_stewardship(record: TrialRecord) -> float:
    """Project whether terminal stewardship was available."""

    breakdown = _eligible_breakdown(record, projection="pump.terminal-stewardship")
    gates = breakdown.get("gates")
    if not isinstance(gates, dict) or not isinstance(gates.get("terminal_stewardship_available"), bool):
        raise ValueError("pump-projection-ineligible: terminal stewardship evidence is missing")
    return 1.0 if gates["terminal_stewardship_available"] else 0.0


def pump_maintenance_completeness(record: TrialRecord) -> float:
    """Project the fraction of generated work items reaching terminal status."""

    breakdown = _eligible_breakdown(record, projection="pump.maintenance-completeness")
    metrics = breakdown.get("metrics")
    if not isinstance(metrics, dict):
        raise ValueError("pump-projection-ineligible: maintenance metrics are missing")
    generated = metrics.get("generated_work_count")
    terminal = metrics.get("terminal_work_count")
    if (
        isinstance(generated, bool)
        or isinstance(terminal, bool)
        or not isinstance(generated, int)
        or not isinstance(terminal, int)
        or generated <= 0
        or terminal < 0
        or terminal > generated
    ):
        raise ValueError("pump-projection-ineligible: maintenance completeness evidence is malformed")
    return terminal / generated


def pump_p01_outcome_projections() -> dict[str, OutcomeProjection]:
    """Return pump-owned projections without global registration."""

    return {
        "world.canonical-reward": _project_reward,
        "pump.evaluation-valid": _pump_projection(pump_evaluation_valid),
        "pump.terminal-stewardship": _pump_projection(pump_terminal_stewardship),
        "pump.maintenance-completeness": _pump_projection(pump_maintenance_completeness),
    }


def build_pump_p01_binding(
    *,
    run_root: Path,
    execution_condition: WorldLearningExecutionCondition,
    consolidation_operation: WorldConsolidationOperation,
    world_run_root: Path,
    deterministic: bool = True,
    resume_existing_run: bool = False,
) -> WorldLearningBinding:
    """Build the P1 pump binding, retaining only reset treatment semantics."""

    return build_world_learning_operations(
        run_root=run_root,
        world_id=PUMP_STATION_WORLD_ID,
        execution_condition=execution_condition,
        run_trial=PumpJourneyTrialRunner(world_run_root=world_run_root, deterministic=deterministic),
        instructions={PUMP_RS1_TASK_ID: _INSTRUCTION, PUMP_RS2_TASK_ID: _INSTRUCTION},
        treatment_kinds={"reset": WorldLearningTreatmentKind.RESET},
        feedback_projectors={
            PUMP_JOURNEY_PUBLIC_FEEDBACK_VIEW_ID: pump_journey_public_feedback,
        },
        consolidation_operations={PUMP_JOURNEY_CONSOLIDATION_OPERATION_ID: consolidation_operation},
        resume_existing_run=resume_existing_run,
    )


def _fresh_world_root(base: Path, trial_id: str) -> Path:
    if not isinstance(trial_id, str) or not trial_id or "\\" in trial_id or "/" in trial_id or "\0" in trial_id:
        raise ValueError("pump-journey-path-unsafe: trial identity is not a safe path component")
    component = PurePosixPath(trial_id)
    if component.is_absolute() or any(part in {"", ".", ".."} for part in component.parts):
        raise ValueError("pump-journey-path-unsafe: trial identity is not a safe path component")
    selected = Path(base).resolve()
    if selected.exists() and selected.is_symlink():
        raise ValueError("pump-journey-path-unsafe: world root is a symlink")
    selected.mkdir(parents=True, exist_ok=True)
    root = selected / trial_id
    if root.exists():
        raise ValueError("pump-journey-world-run-failed: world run already exists")
    root.mkdir()
    return root


def _pump_breakdown(result: Any, stewardship: Any, *, benchmark_valid: bool) -> dict[str, Any]:
    breakdown = stewardship.model_dump(mode="json")
    metrics = dict(breakdown.get("metrics", {}))
    metrics.update(dict(result.semantic_outcome.evaluation.metrics))
    if isinstance(metrics.get("generated_work_count"), int) and isinstance(metrics.get("terminal_work_count"), int):
        metrics["terminal_work_count"] = min(metrics["terminal_work_count"], metrics["generated_work_count"])
    breakdown["metrics"] = metrics
    breakdown["reward"] = result.semantic_outcome.evaluation.reward
    breakdown["terminal_liabilities"] = list(result.semantic_outcome.evaluation.terminal_liabilities)
    breakdown["benchmark_valid"] = benchmark_valid
    return breakdown


def _reference_evidence(result: Any) -> bytes:
    payload = {
        "kind": "pump-world-reference-controller",
        "controller_id": result.controller_id,
        "start_snapshot": asdict(result.start_snapshot),
        "end_snapshot": asdict(result.end_snapshot),
        "temporal_access": result.temporal_access,
        "semantic_evaluation": asdict(result.semantic_outcome.evaluation),
    }
    return (json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def _build_pump_record(
    *,
    task: WorldTask,
    trial: PlannedTrial,
    evaluation: EvaluationResult,
    evidence_file: Path,
    started_at: datetime,
    completed_at: datetime,
    execution_completed: bool,
) -> TrialRecord:
    run_id = ":".join((trial.experiment_id, trial.agent.adapter, trial.agent.model, trial.compute.backend))
    manifest = RunManifest(
        run_id=run_id,
        experiment_id=trial.experiment_id,
        source=UnresolvedSourceRef(reason="world task source was not supplied to the direct trial runner"),
        agent=AgentConfiguration(
            adapter=trial.agent.adapter,
            model=trial.agent.model,
            configuration={key: value for key, value in trial.agent.parameters.items() if key not in {"environment"}},
        ),
        execution_environment=ExecutionEnvironmentRef(
            runtime_image=str(trial.agent.parameters.get("runtime_image", "local-reference-controller")),
            compute_backend=trial.compute.backend,
        ),
        provider_route=ProviderRoute(provider="aec-bench", route="pump-reference-controller"),
        expected_authorities=(
            AuthorityExpectation(
                authority_kind=AuthorityEvidenceKind.WORLD,
                protocol=PUMP_STATION_WORLD_EVIDENCE_PROTOCOL,
            ),
        ),
    )
    total_seconds = max(0.0, (completed_at - started_at).total_seconds())
    world_ref = ArtifactRepository(evidence_file.parent / "authority-artifacts").publish_bytes(
        data=evidence_file.read_bytes(),
        media_type="application/json",
    )
    record = TrialRecord(
        trial_id=trial.trial_id,
        run_id=run_id,
        task_id=task.task_id,
        execution_status=ExecutionStatus.COMPLETED if execution_completed else ExecutionStatus.FAILED,
        evaluation_status=EvaluationStatus.COMPLETED,
        evidence_status=EvidenceStatus.PENDING,
        started_at=started_at,
        completed_at=completed_at,
        input=TrialInput(
            instruction=task.instruction,
            task_revision=task.task_revision,
            task_kind="world",
            visibility=task.visibility,
            system_prompt=trial.agent.system_prompt,
        ),
        output=TrialOutput(
            agent_output=AgentOutput(
                status=AgentOutputStatus.COMPLETED if execution_completed else AgentOutputStatus.PARTIAL,
                output_path=str(evidence_file),
                output_format="json",
            ),
            agent_result={
                "completion": "completed" if execution_completed else "failed",
                "controller": "deterministic-reference-controller",
            },
            terminated=execution_completed,
            truncated=not execution_completed,
            final_reason=(
                "reference controller completed" if execution_completed else "reference controller verification failed"
            ),
        ),
        evaluation=evaluation,
        timing=TimingRecord(total_seconds=total_seconds),
        cost=CostRecord(model_calls=0, tokens_in=0, tokens_out=0, estimated_cost_usd=0.0),
        authority_evidence=(
            AuthorityEvidenceRef(
                authority_kind=AuthorityEvidenceKind.WORLD,
                protocol=PUMP_STATION_WORLD_EVIDENCE_PROTOCOL,
                artifact=world_ref,
            ),
        ),
    ).bind_run_manifest(manifest)
    record.attach_artifact(
        f"authority:world:{PUMP_STATION_WORLD_EVIDENCE_PROTOCOL}",
        evidence_file,
        media_type="application/json",
    )
    return record


def _breakdown(evaluation: EvaluationResult) -> dict[str, Any]:
    if not isinstance(evaluation.breakdown, dict):
        raise ValueError("pump-journey-feedback-invalid: evaluation breakdown is unavailable")
    return evaluation.breakdown


def _eligible_breakdown(record: TrialRecord, *, projection: str) -> dict[str, Any]:
    if record.task_id not in {PUMP_RS1_TASK_ID, PUMP_RS2_TASK_ID}:
        raise ValueError(f"pump-projection-ineligible: {projection} task identity is invalid")
    if record.evaluation_status is not EvaluationStatus.COMPLETED or record.evaluation is None:
        raise ValueError(f"pump-projection-ineligible: {projection} evaluation is unavailable")
    if not record.evaluation.validity.verifier_completed:
        raise ValueError(f"pump-projection-ineligible: {projection} replay did not complete")
    return _breakdown(record.evaluation)


def _project_bool(record: TrialRecord, field: str, *, projection: str) -> float:
    breakdown = _eligible_breakdown(record, projection=projection)
    value = breakdown.get(field)
    if not isinstance(value, bool):
        raise ValueError(f"pump-projection-ineligible: {projection} evidence is malformed")
    return 1.0 if value else 0.0


def _project_reward(record: TrialRecord) -> ProjectionResult:
    try:
        value = world_canonical_reward(record)
    except ValueError as error:
        return ProjectionResult(eligible=False, value=None, reason=str(error))
    return ProjectionResult(eligible=True, value=value, lower_bound=0.0, upper_bound=1.0)


def _pump_projection(reader: Callable[[TrialRecord], float]) -> OutcomeProjection:
    def project(record: TrialRecord) -> ProjectionResult:
        try:
            value = reader(record)
        except ValueError as error:
            return ProjectionResult(eligible=False, value=None, reason=str(error))
        return ProjectionResult(eligible=True, value=value, lower_bound=0.0, upper_bound=1.0)

    return project


def _required_bool(mapping: Mapping[str, Any], field: str) -> bool:
    value = mapping.get(field)
    if not isinstance(value, bool):
        raise ValueError(f"pump-journey-feedback-invalid: {field} is malformed")
    return value


def _contains_forbidden(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(key in _FORBIDDEN_FEEDBACK_KEYS or _contains_forbidden(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_forbidden(item) for item in value)
    if isinstance(value, str):
        lowered = value.lower()
        return any(part in lowered for part in _FORBIDDEN_FEEDBACK_PATH_PARTS)
    return False


__all__ = (
    "PUMP_JOURNEY_CONSOLIDATION_OPERATION_ID",
    "PUMP_JOURNEY_PUBLIC_FEEDBACK_VIEW_ID",
    "PUMP_RS1_PROFILE_ID",
    "PUMP_RS1_TASK_ID",
    "PUMP_RS2_PROFILE_ID",
    "PUMP_RS2_TASK_ID",
    "PUMP_STATION_WORLD_ID",
    "PUMP_STATION_WORLD_EVIDENCE_PROTOCOL",
    "PumpJourneyTrialRunner",
    "_FORBIDDEN_LEARNER_FILENAMES",
    "_FORBIDDEN_LEARNER_MARKERS",
    "build_pump_p01_binding",
    "pump_evaluation_valid",
    "pump_journey_public_feedback",
    "pump_maintenance_completeness",
    "pump_p01_outcome_projections",
    "pump_terminal_stewardship",
    "resolve_pump_task_id",
    "validate_pump_journey_public_feedback",
)
