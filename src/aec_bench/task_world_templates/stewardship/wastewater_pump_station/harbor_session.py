# ABOUTME: Runs reference or model controllers through the pump-station session tools.
# ABOUTME: Writes requests, results, model evidence, verification, and artifact inventory.

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, cast

from aec_bench.adapters.base import AdapterRequest, AdapterResult
from aec_bench.contracts.world_interface import WorldActorActionRequest
from aec_bench.contracts.world_session import (
    StewardshipStateSnapshotRef,
    WorldSessionExecutionKind,
    WorldSessionOpenMode,
    WorldSessionRequest,
    WorldSessionResult,
)
from aec_bench.harness.world_session import open_world_session
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.evidence_health import (
    PUMP_STATION_EVIDENCE_TREATMENT_VERSION_V1,
    PUMP_STATION_EVIDENCE_VISIBILITY_POLICY_V1,
    PumpStationEvidenceTreatmentClass,
    PumpStationEvidenceTreatmentRequest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_export import (
    PUMP_STATION_HARBOR_EXECUTION_KIND,
    PumpStationHarborBridge,
    is_pump_station_harbor_inventory_artifact,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_treatments import (
    PUMP_STATION_PHYSICAL_TREATMENT_DECISION_RIGHT,
    PUMP_STATION_PHYSICAL_TREATMENT_VERSION,
    PUMP_STATION_PHYSICAL_TREATMENT_VISIBILITY,
    PumpStationPhysicalTreatmentClass,
    PumpStationPhysicalTreatmentRequest,
    PumpStationTreatmentSeverity,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_controller import (
    PUMP_STATION_REFERENCE_SYSTEM_CONTROLLER_ID,
    PumpStationReferenceControllerResult,
    run_pump_station_reference_controller,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.rollout_control import (
    PumpStationRolloutControl,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.rollout_models import (
    PumpStationPhysicalTreatmentActivationReceipt,
    PumpStationRolloutChildRequest,
    PumpStationRolloutGroupRequest,
    PumpStationRolloutLineage,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_verifier import (
    PumpStationVerificationReport,
    PumpStationVerificationReportV4,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_views import (
    PumpStationActorHistoryEntry,
    create_structured_handover,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.temporal_evidence import (
    TemporalEvidenceCapability,
    TemporalEvidenceRepository,
    TemporalEvidenceVerificationReport,
    verify_temporal_evidence_repository,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_control import (
    PumpStationEvidenceControlRequest,
    PumpStationEvidenceControlResult,
    PumpStationWorldControl,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_models import (
    PumpStationStateSnapshotRef,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_session import (
    PUMP_STATION_EVIDENCE_HEALTH_TOOL_NAMES,
    PUMP_STATION_RICH_WORK_TOOL_NAMES,
    PUMP_STATION_TASK_WORLD_ID,
    PUMP_STATION_TEMPORAL_EVIDENCE_TOOL_NAMES,
    PUMP_STATION_TOOL_NAMES,
    PumpStationWorldSession,
    PumpStationWorldSessionFactory,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_session_activation import (
    PumpStationSessionActivationBinding,
)
from aec_bench.trajectory.writer import TrajectoryWriter

PUMP_STATION_REFERENCE_CONTROLLER_ID = "deterministic-reference-controller"
PUMP_STATION_MODEL_CONTROLLER_MODE = "model"
PUMP_STATION_MODEL_MAX_TURNS = 90
PUMP_STATION_HARBOR_RUN_SCHEMA_VERSION = "aecbench.pump-station-harbor-run.v1"


@dataclass(frozen=True)
class CompletedPumpStationReferenceSession:
    """Result of one provider-free reference session."""

    request: WorldSessionRequest
    result: WorldSessionResult
    verification: PumpStationVerificationReport | PumpStationVerificationReportV4
    output_dir: Path


@dataclass(frozen=True)
class CompletedPumpStationModelSession:
    """Result and adapter evidence from one model-controlled world session."""

    request: WorldSessionRequest
    result: WorldSessionResult
    verification: PumpStationVerificationReport | PumpStationVerificationReportV4
    adapter_result: AdapterResult
    output_dir: Path


@dataclass(frozen=True)
class CompletedPumpStationRolloutSession:
    """Local Harbor result for paired control and treated rollout children."""

    lineage: PumpStationRolloutLineage
    treatment_activation: PumpStationPhysicalTreatmentActivationReceipt
    control_verification: PumpStationVerificationReport
    treated_verification: PumpStationVerificationReport
    output_dir: Path


@dataclass(frozen=True)
class CompletedPumpStationRolloutModelSession:
    """Bounded model check over one existing isolated rollout child."""

    result: WorldSessionResult
    verification: PumpStationVerificationReport
    adapter_result: AdapterResult
    output_dir: Path


def run_pump_station_rollout_model_session(
    *,
    control: PumpStationRolloutControl,
    group_id: str,
    child_id: str,
    output_dir: Path,
    session_identity: str,
    model: str,
    forbidden_private_tokens: tuple[str, ...],
    max_turns: int = 4,
    registry: Any | None = None,
) -> CompletedPumpStationRolloutModelSession:
    """Let one model inspect and act on a child without private rollout metadata."""

    identity = session_identity.strip()
    model_name = model.strip()
    if not identity or not model_name:
        raise ValueError("rollout model session requires identity and model")
    if max_turns < 1:
        raise ValueError("rollout model session max turns must be positive")
    destination = Path(output_dir)
    if destination.exists():
        raise FileExistsError(f"rollout model output already exists: {destination}")
    destination.mkdir(parents=True)
    session = control.open_actor_session(
        group_id=group_id,
        child_id=child_id,
        session_id=f"session.{identity}",
        agent_tenure_id=f"tenure.{identity}",
    )
    trajectory = TrajectoryWriter(path=str(destination / "trajectory.jsonl"))
    try:
        resolved_registry = registry or _local_adapter_registry()
        adapter = resolved_registry.build(
            adapter_kind="tool_loop",
            model_name=model_name,
            workspace=str(destination),
            trajectory_writer=trajectory,
            native_tools=session.native_tools,
            enable_bash=False,
        )
        adapter_result = adapter.execute(
            AdapterRequest(
                instruction=(
                    "Observe the station. Use the closed tools to make one supported "
                    "condition assessment. If current evidence is not sufficient, request "
                    "one condition check or inspection. Do not infer a hidden cause. Stop "
                    "after the diagnostic action and give a short factual summary."
                ),
                system_prompt=(
                    "You are the accountable wastewater pump-station steward. Use only "
                    "the current actor view and declared tools. Never invent hidden state, "
                    "future events, other runs, or treatment causes."
                ),
                tools=list(session.tool_specs),
                configuration={"max_turns": max_turns},
                output_path=str(destination / "output.md"),
                output_format="markdown",
            )
        )
    finally:
        trajectory.close()
    private_surface = "\n".join(
        (
            adapter_result.raw_output_text or "",
            *(entry.content or "" for entry in adapter_result.transcript),
        )
    )
    leaked = tuple(token for token in forbidden_private_tokens if token and token in private_surface)
    if leaked:
        raise ValueError(f"rollout model output exposed private tokens: {leaked}")
    verification = cast(PumpStationVerificationReport, session.verify())
    _write_model_evidence(
        destination=destination,
        adapter_result=adapter_result,
        model=model_name,
        max_turns=max_turns,
    )
    _write_json(
        destination / "world-session-result.json",
        session.result.model_dump(mode="json"),
    )
    _write_json(
        destination / "verification-report.json",
        _verification_payload(verification),
    )
    _write_json(
        destination / "privacy-check.json",
        {
            "forbidden_token_count": len(forbidden_private_tokens),
            "leaked_tokens": list(leaked),
            "passed": not leaked,
        },
    )
    return CompletedPumpStationRolloutModelSession(
        result=session.result,
        verification=verification,
        adapter_result=adapter_result,
        output_dir=destination,
    )


def run_pump_station_rollout_reference_session(
    *,
    bridge: PumpStationHarborBridge,
    output_dir: Path,
    session_identity: str,
) -> CompletedPumpStationRolloutSession:
    """Run paired isolated rollout children and one governed treatment through Harbor."""

    if not bridge.evidence_health:
        raise ValueError("pump-station Harbor bridge does not enable evidence health")
    identity = session_identity.strip()
    if not identity:
        raise ValueError("pump-station Harbor rollout identity is required")
    destination = Path(output_dir)
    if destination.exists():
        raise FileExistsError(f"world-session output already exists: {destination}")
    destination.mkdir(parents=True)
    parent_root = destination / "parent-world"
    parent = PumpStationWorldSessionFactory(
        parent_root,
        package_root=bridge.package_root,
        evidence_health=True,
    ).open(_world_session_request(f"{identity}.parent"))
    parent_snapshot = parent.run.snapshot()
    request = PumpStationRolloutGroupRequest(
        request_id=f"rollout.{identity}",
        group_id=f"group.{identity}",
        task_world_id=PUMP_STATION_TASK_WORLD_ID,
        authority_id="harbor-rollout-control",
        parent_snapshot=parent_snapshot,
        origin_verification_id="harbor-verified-current-world-state",
        information_boundary_id="pump-station-actor-view.v3",
        event_schedule_id="harbor-fixed-future-schedule.v1",
        fixed_future_condition_id="harbor-fixed-future.v1",
        future_condition_seed=41,
        split_group_id=f"split.{identity}",
        children=(
            PumpStationRolloutChildRequest(
                child_id="control",
                run_id=f"run.{identity}.control",
                world_branch_id=f"branch.{identity}.control",
                agent_condition_id="reference-controller.control",
                agent_seed=101,
            ),
            PumpStationRolloutChildRequest(
                child_id="treated",
                run_id=f"run.{identity}.treated",
                world_branch_id=f"branch.{identity}.treated",
                agent_condition_id="reference-controller.treated",
                agent_seed=202,
            ),
        ),
    )
    control = PumpStationRolloutControl(
        parent_repository_root=parent_root,
        rollout_repository_root=destination / "rollouts",
        authorised_principal_ids=("harbor-rollout-control",),
        package_root=bridge.package_root,
        evidence_health=True,
    )
    lineage = control.create_group(request)
    control_child = control.open_actor_session(
        group_id=request.group_id,
        child_id="control",
        session_id=f"session.{identity}.control",
        agent_tenure_id=f"tenure.{identity}.control",
    )
    treated_child = control.open_actor_session(
        group_id=request.group_id,
        child_id="treated",
        session_id=f"session.{identity}.treated",
        agent_tenure_id=f"tenure.{identity}.treated",
    )
    treated_snapshot = treated_child.run.snapshot()
    treatment = PumpStationPhysicalTreatmentRequest(
        request_id=f"treatment.{identity}.recurrence",
        task_world_id=PUMP_STATION_TASK_WORLD_ID,
        authority_id="harbor-rollout-control",
        group_id=request.group_id,
        child_id="treated",
        child_run_id=treated_snapshot.run_id,
        child_episode_id=treated_snapshot.episode_id,
        child_world_branch_id=treated_snapshot.world_branch_id,
        base_state_id=treated_snapshot.state_id,
        base_commit_id=treated_snapshot.commit_id,
        based_on_sequence=treated_snapshot.sequence,
        parent_state_id=parent_snapshot.state_id,
        treatment_class=PumpStationPhysicalTreatmentClass.RECURRENT_OBSTRUCTION,
        treatment_version=PUMP_STATION_PHYSICAL_TREATMENT_VERSION,
        affected_pump_ids=("pump-a",),
        activation_calendar_seconds=treated_child.run.state.physical.calendar_seconds,
        severity=PumpStationTreatmentSeverity.MODERATE,
        random_stream_id=f"harbor-stream.{identity}",
        random_seed=41,
        visibility_policy=PUMP_STATION_PHYSICAL_TREATMENT_VISIBILITY,
        decision_right_id=PUMP_STATION_PHYSICAL_TREATMENT_DECISION_RIGHT,
    )
    control.schedule_treatment(treatment)
    treatment_activation = control.recover_treatment(
        group_id=request.group_id,
        child_id="treated",
        treatment_request_id=treatment.request_id,
    )
    control_verification = cast(PumpStationVerificationReport, control_child.verify())
    treated_verification = cast(PumpStationVerificationReport, treated_child.verify())
    if not control_verification.valid or not treated_verification.valid:
        raise ValueError("local Harbor rollout children did not replay")
    _write_json(destination / "rollout-lineage.json", asdict(lineage))
    _write_json(
        destination / "treatment-activation.json",
        asdict(treatment_activation),
    )
    _write_json(
        destination / "control-verification.json",
        _verification_payload(control_verification),
    )
    _write_json(
        destination / "treated-verification.json",
        _verification_payload(treated_verification),
    )
    return CompletedPumpStationRolloutSession(
        lineage=lineage,
        treatment_activation=treatment_activation,
        control_verification=control_verification,
        treated_verification=treated_verification,
        output_dir=destination,
    )


def run_pump_station_reference_session(
    *,
    bridge: PumpStationHarborBridge,
    output_dir: Path,
    session_identity: str,
) -> CompletedPumpStationReferenceSession:
    """Execute the complete reference trajectory without a model-provider call."""

    if bridge.profile_ref is not None:
        return _run_registered_reference_session(
            bridge=bridge,
            output_dir=output_dir,
            session_identity=session_identity,
        )

    identity = session_identity.strip()
    if not identity:
        raise ValueError("pump-station Harbor session identity is required")
    destination = Path(output_dir)
    if destination.exists():
        raise FileExistsError(f"world-session output already exists: {destination}")
    destination.mkdir(parents=True)
    repository_root = destination / "world-run"
    request = WorldSessionRequest(
        execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
        open_mode=WorldSessionOpenMode.START,
        session_id=f"session.{identity}",
        task_world_id=PUMP_STATION_TASK_WORLD_ID,
        agent_tenure_id=f"tenure.{identity}",
        run_id=f"run.{identity}",
        episode_id=f"episode.{identity}",
        world_branch_id=f"branch.{identity}",
    )
    session = cast(
        PumpStationWorldSession,
        open_world_session(
            request,
            PumpStationWorldSessionFactory(
                repository_root,
                package_root=bridge.package_root,
            ),
        ),
    )
    start_snapshot = session.result.snapshot
    _execute_reference_trajectory(session)
    verification = session.verify()
    if not verification.valid:
        raise ValueError("deterministic pump-station reference session did not verify")
    _write_json(
        destination / "world-session-request.json",
        request.model_dump(mode="json"),
    )
    _write_json(
        destination / "world-session-result.json",
        session.result.model_dump(mode="json"),
    )
    _write_json(
        destination / "verification-report.json",
        _verification_payload(verification),
    )
    _write_json(
        destination / "artifact-inventory.json",
        _artifact_inventory(
            bridge=bridge,
            output_dir=destination,
            start_snapshot=start_snapshot.model_dump(mode="json"),
            end_snapshot=session.result.snapshot.model_dump(mode="json"),
        ),
    )
    return CompletedPumpStationReferenceSession(
        request=request,
        result=session.result,
        verification=verification,
        output_dir=destination,
    )


def _run_registered_reference_session(
    *,
    bridge: PumpStationHarborBridge,
    output_dir: Path,
    session_identity: str,
) -> CompletedPumpStationReferenceSession:
    profile_ref = bridge.profile_ref
    if profile_ref is None or bridge.reference_system_root is None:
        raise ValueError("registered Harbor bridge authority is incomplete")
    identity = session_identity.strip()
    if not identity:
        raise ValueError("pump-station Harbor session identity is required")
    destination = Path(output_dir)
    if destination.exists():
        raise FileExistsError(f"world-session output already exists: {destination}")
    destination.mkdir(parents=True)
    repository_root = destination / "world-run"
    controller = run_pump_station_reference_controller(
        repository_root=repository_root,
        run_id=f"run.{identity}",
        episode_id=f"episode.{identity}",
        world_branch_id=f"branch.{identity}",
    )
    selected = controller.run.repository.load_selected_session_activation()
    window_start = _session_window_start(controller.run.repository, selected)
    request = WorldSessionRequest(
        execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
        open_mode=WorldSessionOpenMode.RESUME,
        session_id=selected.session_id,
        task_world_id=PUMP_STATION_TASK_WORLD_ID,
        agent_tenure_id=selected.agent_tenure_id,
        run_id=selected.run_id,
        episode_id=selected.episode_id,
        world_branch_id=selected.world_branch_id,
        start_snapshot=_activation_snapshot(window_start),
    )
    terminal = cast(
        PumpStationWorldSession,
        open_world_session(
            request.model_copy(update={"start_snapshot": _snapshot_ref(controller.end_snapshot)}),
            PumpStationWorldSessionFactory(
                repository_root,
                profile_ref=profile_ref,
            ),
        ),
    )
    verification = terminal.verify()
    if not verification.valid:
        raise ValueError("registered pump-station reference session did not verify")
    temporal_verification = _verify_registered_temporal_evidence(controller)
    if not temporal_verification.valid:
        raise ValueError("registered pump-station temporal evidence did not verify")
    _write_session_evidence(
        destination=destination,
        request=request,
        result=terminal.result,
        verification=verification,
    )
    _write_json(
        destination / "temporal-verification-report.json",
        temporal_verification.model_dump(mode="json"),
    )
    _write_json(
        destination / "artifact-inventory.json",
        _artifact_inventory(
            bridge=bridge,
            output_dir=destination,
            controller_id=PUMP_STATION_REFERENCE_SYSTEM_CONTROLLER_ID,
            start_snapshot=_activation_snapshot(window_start).model_dump(mode="json"),
            end_snapshot=terminal.result.snapshot.model_dump(mode="json"),
            tool_names=terminal.result.tool_names,
        ),
    )
    return CompletedPumpStationReferenceSession(
        request=request,
        result=terminal.result,
        verification=verification,
        output_dir=destination,
    )


def _session_window_start(
    repository: PumpStationWorldRunRepository,
    selected: PumpStationSessionActivationBinding,
) -> PumpStationSessionActivationBinding:
    start = selected
    while start.prior_binding_id is not None:
        prior = repository.load_session_activation(start.prior_binding_id)
        if (prior.session_id, prior.agent_tenure_id) != (selected.session_id, selected.agent_tenure_id):
            break
        start = prior
    return start


def _verify_registered_temporal_evidence(
    controller: PumpStationReferenceControllerResult,
) -> TemporalEvidenceVerificationReport:
    proposal_bindings = {
        step.proposal.context.proposal_id: (
            step.proposal.context.information_set_id,
            step.proposal.context.base_view_id,
        )
        for step in controller.run.repository.v4_steps()
        if step.proposal is not None
    }
    return verify_temporal_evidence_repository(
        TemporalEvidenceRepository(controller.run.repository.root / "temporal-evidence"),
        package=controller.run.package,
        proposal_bindings=proposal_bindings,
    )


def _activation_snapshot(binding: PumpStationSessionActivationBinding) -> StewardshipStateSnapshotRef:
    return StewardshipStateSnapshotRef(
        run_id=binding.run_id,
        episode_id=binding.episode_id,
        world_branch_id=binding.world_branch_id,
        sequence=binding.sequence,
        state_id=binding.state_id,
        commit_id=binding.commit_id,
    )


def _snapshot_ref(snapshot: PumpStationStateSnapshotRef) -> StewardshipStateSnapshotRef:
    return StewardshipStateSnapshotRef(
        run_id=snapshot.run_id,
        episode_id=snapshot.episode_id,
        world_branch_id=snapshot.world_branch_id,
        sequence=snapshot.sequence,
        state_id=snapshot.state_id,
        commit_id=snapshot.commit_id,
    )


def run_pump_station_rich_work_reference_session(
    *,
    bridge: PumpStationHarborBridge,
    output_dir: Path,
    session_identity: str,
) -> CompletedPumpStationReferenceSession:
    """Execute the rich overlapping-work trajectory without a model provider."""
    if not bridge.rich_work_processes:
        raise ValueError("pump-station Harbor bridge does not enable rich work")
    identity = session_identity.strip()
    if not identity:
        raise ValueError("pump-station Harbor session identity is required")
    destination = Path(output_dir)
    if destination.exists():
        raise FileExistsError(f"world-session output already exists: {destination}")
    destination.mkdir(parents=True)
    repository_root = destination / "world-run"
    start_request = _world_session_request(identity)
    factory = PumpStationWorldSessionFactory(
        repository_root,
        package_root=bridge.package_root,
        rich_work_processes=True,
    )
    first = cast(
        PumpStationWorldSession,
        open_world_session(start_request, factory),
    )
    start_snapshot = first.result.snapshot
    suspended_snapshot = _execute_rich_work_until_handover(first)
    resume_request = WorldSessionRequest(
        execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
        open_mode=WorldSessionOpenMode.RESUME,
        session_id=f"session.{identity}.handover",
        task_world_id=PUMP_STATION_TASK_WORLD_ID,
        agent_tenure_id=f"tenure.{identity}.handover",
        run_id=start_request.run_id,
        episode_id=start_request.episode_id,
        world_branch_id=start_request.world_branch_id,
        start_snapshot=suspended_snapshot,
    )
    second = cast(
        PumpStationWorldSession,
        open_world_session(resume_request, factory),
    )
    second.install_structured_handover(
        create_structured_handover(
            second.actor_view,
            from_tenure_id=start_request.agent_tenure_id,
            history=cast(
                tuple[PumpStationActorHistoryEntry, ...],
                first.actor_history,
            ),
            maximum_history_entries=32,
        )
    )
    _execute_rich_work_after_handover(second)
    verification = second.verify()
    if not verification.valid:
        raise ValueError("rich-work pump-station reference session did not verify")
    _write_session_evidence(
        destination=destination,
        request=resume_request,
        result=second.result,
        verification=verification,
    )
    _write_json(
        destination / "artifact-inventory.json",
        _artifact_inventory(
            bridge=bridge,
            output_dir=destination,
            start_snapshot=start_snapshot.model_dump(mode="json"),
            end_snapshot=second.result.snapshot.model_dump(mode="json"),
            tool_names=PUMP_STATION_RICH_WORK_TOOL_NAMES,
        ),
    )
    return CompletedPumpStationReferenceSession(
        request=resume_request,
        result=second.result,
        verification=verification,
        output_dir=destination,
    )


def run_pump_station_evidence_health_reference_session(
    *,
    bridge: PumpStationHarborBridge,
    output_dir: Path,
    session_identity: str,
) -> CompletedPumpStationReferenceSession:
    """Execute one provider-free evidence-health trajectory through local Harbor."""
    if not bridge.evidence_health:
        raise ValueError("pump-station Harbor bridge does not enable evidence health")
    identity = session_identity.strip()
    if not identity:
        raise ValueError("pump-station Harbor session identity is required")
    destination = Path(output_dir)
    if destination.exists():
        raise FileExistsError(f"world-session output already exists: {destination}")
    destination.mkdir(parents=True)
    repository_root = destination / "world-run"
    start_request = _world_session_request(identity)
    factory = PumpStationWorldSessionFactory(
        repository_root,
        package_root=bridge.package_root,
        evidence_health=True,
        temporal_evidence=bridge.temporal_evidence,
    )
    first = cast(
        PumpStationWorldSession,
        open_world_session(start_request, factory),
    )
    start_snapshot = first.result.snapshot
    run_snapshot = first.run.snapshot()
    decision_point = min(
        event.scheduled_seconds
        for event in first.run.state.scheduled_events
        if event.event_type.value == "decision_point"
    )
    treatment_request = PumpStationEvidenceTreatmentRequest(
        request_id="treatment-reference-calibration",
        run_id=run_snapshot.run_id,
        episode_id=run_snapshot.episode_id,
        world_branch_id=run_snapshot.world_branch_id,
        base_state_id=run_snapshot.state_id,
        base_commit_id=run_snapshot.commit_id,
        based_on_sequence=run_snapshot.sequence,
        treatment_class=PumpStationEvidenceTreatmentClass.CALIBRATION_LAPSE,
        treatment_version=PUMP_STATION_EVIDENCE_TREATMENT_VERSION_V1,
        target_source_id="station-condition-sensor",
        effective_decision_point_seconds=decision_point,
        visibility_policy=PUMP_STATION_EVIDENCE_VISIBILITY_POLICY_V1,
    )
    scheduled = PumpStationWorldControl(
        repository_root,
        authorised_principal_ids=("harbor-evidence-control",),
        package_root=bridge.package_root,
        evidence_health=True,
    ).execute(
        PumpStationEvidenceControlRequest(
            request_id=treatment_request.request_id,
            operation="schedule_evidence_treatment",
            task_world_id=PUMP_STATION_TASK_WORLD_ID,
            authority_id="harbor-evidence-control",
            treatment_request=treatment_request,
        )
    )
    if not isinstance(scheduled, PumpStationEvidenceControlResult):
        raise TypeError("evidence-health control returned the wrong result type")
    scheduled_snapshot = scheduled.receipt.result_snapshot
    if scheduled_snapshot is None:
        raise ValueError("evidence-health schedule returned no snapshot")
    activation_request = WorldSessionRequest(
        execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
        open_mode=WorldSessionOpenMode.RESUME,
        session_id=f"session.{identity}.activation",
        task_world_id=PUMP_STATION_TASK_WORLD_ID,
        agent_tenure_id=start_request.agent_tenure_id,
        run_id=start_request.run_id,
        episode_id=start_request.episode_id,
        world_branch_id=start_request.world_branch_id,
        start_snapshot=scheduled_snapshot,
    )
    activation_session = cast(
        PumpStationWorldSession,
        open_world_session(activation_request, factory),
    )
    activation_session.continue_operation(
        "proposal-reference-activation",
        "Continue to the declared evidence-health decision point.",
    )
    handover_request = WorldSessionRequest(
        execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
        open_mode=WorldSessionOpenMode.RESUME,
        session_id=f"session.{identity}.handover",
        task_world_id=PUMP_STATION_TASK_WORLD_ID,
        agent_tenure_id=f"tenure.{identity}.handover",
        run_id=start_request.run_id,
        episode_id=start_request.episode_id,
        world_branch_id=start_request.world_branch_id,
        start_snapshot=activation_session.result.snapshot,
    )
    recipient = cast(
        PumpStationWorldSession,
        open_world_session(handover_request, factory),
    )
    recipient.install_structured_handover(
        create_structured_handover(
            recipient.actor_view,
            from_tenure_id=start_request.agent_tenure_id,
            history=cast(
                tuple[PumpStationActorHistoryEntry, ...],
                activation_session.actor_history,
            ),
            maximum_history_entries=8,
        )
    )
    if bridge.temporal_evidence:
        search = json.loads(
            recipient.search_evidence(
                "search-reference-maintenance",
                "pump obstruction procedure",
                "procedures",
                5,
            )
        )["receipt"]
        references = search.get("references")
        if not isinstance(references, list) or not references:
            raise ValueError("temporal reference session returned no documentary evidence")
        reference = str(references[0]["opaque_reference"])
        recipient.fetch_evidence("fetch-reference-maintenance", reference)
        recipient.invoke_actor_action(
            WorldActorActionRequest(
                request_id="proposal-reference-condition-check",
                action_name="request_condition_check",
                binding=recipient.current_actor_binding,
                arguments={
                    "reason": "Record the visible sensor condition after documentary review.",
                    "pump_id": "pump-a",
                    "relied_on_evidence_refs": [reference],
                },
            )
        )
    else:
        recipient.request_condition_check(
            "proposal-reference-condition-check",
            "Record the visible sensor condition after handover.",
            "pump-a",
        )
    recipient.request_inspection(
        "proposal-reference-physical-inspection",
        "Request the separate physical inspection after the sensor check.",
        "pump-b",
    )
    verification = recipient.verify()
    if not verification.valid:
        raise ValueError("evidence-health pump-station reference session did not verify")
    _write_session_evidence(
        destination=destination,
        request=handover_request,
        result=recipient.result,
        verification=verification,
    )
    if bridge.temporal_evidence:
        temporal_verification = recipient.verify_temporal_evidence()
        if not temporal_verification.valid:
            raise ValueError("temporal-evidence reference session did not verify")
        _write_json(
            destination / "temporal-verification-report.json",
            temporal_verification.model_dump(mode="json"),
        )
    _write_json(
        destination / "artifact-inventory.json",
        _artifact_inventory(
            bridge=bridge,
            output_dir=destination,
            start_snapshot=start_snapshot.model_dump(mode="json"),
            end_snapshot=recipient.result.snapshot.model_dump(mode="json"),
            tool_names=(
                PUMP_STATION_TEMPORAL_EVIDENCE_TOOL_NAMES
                if bridge.temporal_evidence
                else PUMP_STATION_EVIDENCE_HEALTH_TOOL_NAMES
            ),
        ),
    )
    return CompletedPumpStationReferenceSession(
        request=handover_request,
        result=recipient.result,
        verification=verification,
        output_dir=destination,
    )


def _rich_state(session: PumpStationWorldSession) -> dict[str, Any]:
    payload = json.loads(session.observe_pump_station())
    return cast(dict[str, Any], payload["current_state"])


def _rich_process(
    state: dict[str, Any],
    kind: str,
    pump_id: str,
) -> dict[str, Any]:
    processes = cast(list[dict[str, Any]], state["processes"])
    return next(item for item in processes if item["kind"] == kind and item["pump_id"] == pump_id)


def _continue_rich_until(
    session: PumpStationWorldSession,
    *,
    prefix: str,
    predicate: Any,
) -> dict[str, Any]:
    for index in range(1, 16):
        session.continue_operation(
            f"{prefix}-{index:02d}",
            "Advance to the next declared event.",
        )
        state = _rich_state(session)
        if predicate(state):
            return state
    raise ValueError("rich-work reference event did not arrive")


def _execute_rich_work_until_handover(
    session: PumpStationWorldSession,
) -> Any:
    reason = "Execute the deterministic rich-work stewardship journey."
    verification = json.loads(
        session.request_post_maintenance_verification(
            "proposal-verification",
            reason,
            "pump-a",
        )
    )["view"]["current_state"]
    verification_process = _rich_process(
        verification,
        "post_maintenance_verification",
        "pump-a",
    )
    session.request_inspection("proposal-inspection", reason, "pump-b")
    session.transfer_duty("proposal-transfer", reason)
    ready = _continue_rich_until(
        session,
        prefix="proposal-ready",
        predicate=lambda state: state["resources"]["repair_kit_available"],
    )
    dependency = next(
        item
        for item in cast(list[dict[str, Any]], ready["dependencies"])
        if item["process_id"] == verification_process["process_id"] and item["kind"] == "administrative_closeout"
    )
    evidence = next(
        item
        for item in cast(list[dict[str, Any]], ready["evidence"])
        if item["kind"] == "functional_checks" and item["pump_id"] == "pump-a"
    )
    session.request_dependency_waiver(
        "proposal-waiver",
        reason,
        str(verification_process["process_id"]),
        str(dependency["dependency_id"]),
        str(evidence["evidence_id"]),
    )
    session.resume_process(
        "proposal-resume-verification",
        reason,
        str(verification_process["process_id"]),
    )
    _continue_rich_until(
        session,
        prefix="proposal-withdraw",
        predicate=lambda state: _rich_process(
            state,
            "post_maintenance_verification",
            "pump-a",
        )["status"]
        == "suspended",
    )
    return session.result.snapshot


def _execute_rich_work_after_handover(
    session: PumpStationWorldSession,
) -> None:
    reason = "Continue the deterministic rich-work stewardship journey."
    restored = _continue_rich_until(
        session,
        prefix="proposal-restore",
        predicate=lambda state: state["resources"]["access_window_seconds"] > 0,
    )
    verification = _rich_process(
        restored,
        "post_maintenance_verification",
        "pump-a",
    )
    session.resume_process(
        "proposal-resume-after-handover",
        reason,
        str(verification["process_id"]),
    )
    _continue_rich_until(
        session,
        prefix="proposal-complete-verification",
        predicate=lambda state: not any(
            item["kind"] == "post_maintenance_verification" and item["pump_id"] == "pump-a"
            for item in cast(list[dict[str, Any]], state["processes"])
        ),
    )
    inspection = _rich_process(_rich_state(session), "inspection", "pump-b")
    session.resume_process(
        "proposal-resume-inspection",
        reason,
        str(inspection["process_id"]),
    )
    inspected = _continue_rich_until(
        session,
        prefix="proposal-complete-inspection",
        predicate=lambda state: any(
            item["kind"] == "inspection" and item["pump_id"] == "pump-b"
            for item in cast(list[dict[str, Any]], state["evidence"])
        ),
    )
    inspection_evidence = next(
        item
        for item in cast(list[dict[str, Any]], inspected["evidence"])
        if item["kind"] == "inspection" and item["pump_id"] == "pump-b"
    )
    session.request_obstruction_clearance(
        "proposal-clearance",
        reason,
        "pump-b",
        str(inspection_evidence["evidence_id"]),
    )
    _continue_rich_until(
        session,
        prefix="proposal-complete-clearance",
        predicate=lambda state: not state["resources"]["repair_kit_available"],
    )
    _continue_rich_until(
        session,
        prefix="proposal-complete-checks",
        predicate=lambda state: any(
            item["kind"] == "functional_checks" and item["pump_id"] == "pump-b"
            for item in cast(list[dict[str, Any]], state["evidence"])
        ),
    )


def run_pump_station_model_session(
    *,
    bridge: PumpStationHarborBridge,
    output_dir: Path,
    session_identity: str,
    model: str,
    max_turns: int = PUMP_STATION_MODEL_MAX_TURNS,
    registry: Any | None = None,
) -> CompletedPumpStationModelSession:
    """Let one model control the closed pump-station tools and persist the run."""

    identity = session_identity.strip()
    model_name = model.strip()
    if not identity:
        raise ValueError("pump-station model session identity is required")
    if not model_name:
        raise ValueError("pump-station model session requires a model")
    if max_turns < 1:
        raise ValueError("pump-station model session max turns must be positive")
    destination = Path(output_dir)
    if destination.exists():
        raise FileExistsError(f"world-session output already exists: {destination}")
    destination.mkdir(parents=True)
    request = _world_session_request(identity)
    session = _open_pump_station_session(
        request=request,
        repository_root=destination / "world-run",
        bridge=bridge,
    )
    start_snapshot = session.result.snapshot
    trajectory = TrajectoryWriter(path=str(destination / "trajectory.jsonl"))
    try:
        resolved_registry = registry or _local_adapter_registry()
        adapter = resolved_registry.build(
            adapter_kind="tool_loop",
            model_name=model_name,
            workspace=str(destination),
            trajectory_writer=trajectory,
            native_tools=session.native_tools,
            enable_bash=False,
        )
        adapter_result = adapter.execute(
            AdapterRequest(
                instruction=_model_instruction(
                    registered_profile=bridge.profile_ref is not None,
                    rich_work_processes=bridge.rich_work_processes,
                    temporal_evidence=bridge.temporal_evidence,
                ),
                system_prompt=_model_system_prompt(
                    registered_profile=bridge.profile_ref is not None,
                    rich_work_processes=bridge.rich_work_processes,
                    temporal_evidence=bridge.temporal_evidence,
                ),
                tools=list(session.tool_specs),
                configuration={"max_turns": max_turns},
                output_path=str(destination / "output.md"),
                output_format="markdown",
            )
        )
    finally:
        trajectory.close()
    verification = session.verify()
    _write_model_evidence(
        destination=destination,
        adapter_result=adapter_result,
        model=model_name,
        max_turns=max_turns,
    )
    _write_session_evidence(
        destination=destination,
        request=request,
        result=session.result,
        verification=verification,
    )
    if bridge.temporal_evidence:
        temporal_verification = session.verify_temporal_evidence()
        _write_json(
            destination / "temporal-verification-report.json",
            temporal_verification.model_dump(mode="json"),
        )
    _write_json(
        destination / "artifact-inventory.json",
        _artifact_inventory(
            bridge=bridge,
            output_dir=destination,
            controller_id=model_name,
            start_snapshot=start_snapshot.model_dump(mode="json"),
            end_snapshot=session.result.snapshot.model_dump(mode="json"),
            tool_names=session.result.tool_names,
        ),
    )
    return CompletedPumpStationModelSession(
        request=request,
        result=session.result,
        verification=verification,
        adapter_result=adapter_result,
        output_dir=destination,
    )


def _execute_reference_trajectory(session: PumpStationWorldSession) -> None:
    reason = "Execute the deterministic reference stewardship journey."
    session.request_conditional_deferral("proposal-01", reason, "pump-a")
    session.transfer_duty("proposal-02", reason)
    session.request_inspection("proposal-03", reason, "pump-a")
    inspection_completed = json.loads(session.continue_operation("proposal-04", reason))
    inspection_id = _evidence_id(inspection_completed, "inspection")
    session.continue_operation("proposal-05", reason)
    session.request_obstruction_clearance(
        "proposal-06",
        reason,
        "pump-a",
        inspection_id,
    )
    session.continue_operation("proposal-07", reason)
    checks_completed = json.loads(session.continue_operation("proposal-08", reason))
    functional_check_id = _evidence_id(checks_completed, "functional_checks")
    returned = json.loads(
        session.request_provisional_return(
            "proposal-09",
            reason,
            "pump-a",
            functional_check_id,
        )
    )
    work_orders = returned["view"]["current_state"]["work_orders"]
    if not isinstance(work_orders, list) or not work_orders:
        raise ValueError("reference session did not create a work order")
    work_order_id = str(work_orders[0]["work_order_id"])
    session.request_provisional_closure("proposal-10", reason, work_order_id)
    session.request_post_maintenance_verification(
        "proposal-11",
        reason,
        "pump-a",
    )
    session.continue_operation("proposal-12", reason)


def _evidence_id(transition: dict[str, Any], kind: str) -> str:
    evidence = transition["view"]["current_state"]["evidence"]
    if not isinstance(evidence, list):
        raise ValueError("reference session evidence is not a list")
    for item in evidence:
        if isinstance(item, dict) and item.get("kind") == kind:
            value = item.get("evidence_id")
            if isinstance(value, str) and value:
                return value
    raise ValueError(f"reference session lacks {kind} evidence")


def _artifact_inventory(
    *,
    bridge: PumpStationHarborBridge,
    output_dir: Path,
    controller_id: str = PUMP_STATION_REFERENCE_CONTROLLER_ID,
    start_snapshot: dict[str, Any],
    end_snapshot: dict[str, Any],
    tool_names: tuple[str, ...] = PUMP_STATION_TOOL_NAMES,
) -> dict[str, Any]:
    artifacts: list[dict[str, Any]] = []
    for path in sorted(output_dir.rglob("*")):
        if not path.is_file() or not is_pump_station_harbor_inventory_artifact(
            output_dir,
            path,
        ):
            continue
        payload = path.read_bytes()
        artifacts.append(
            {
                "path": path.relative_to(output_dir).as_posix(),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size_bytes": len(payload),
            }
        )
    inventory = {
        "schema_version": PUMP_STATION_HARBOR_RUN_SCHEMA_VERSION,
        "execution_kind": PUMP_STATION_HARBOR_EXECUTION_KIND,
        "task_world_id": PUMP_STATION_TASK_WORLD_ID,
        "controller_id": controller_id,
        "export_manifest_sha256": bridge.export_manifest_sha256,
        "verifier_runtime_sha256": bridge.verifier_runtime_sha256,
        "package_content_id": bridge.package.package_content_id,
        "package_manifest_content_id": bridge.package.manifest_content_id,
        "tool_names": list(tool_names),
        "start_snapshot": start_snapshot,
        "end_snapshot": end_snapshot,
        "transition_count": end_snapshot["sequence"] - start_snapshot["sequence"],
        "artifacts": artifacts,
    }
    if bridge.temporal_evidence:
        capability = TemporalEvidenceCapability.model_validate(
            _read_json(output_dir / "world-run" / "temporal-evidence" / "capability.json")
        )
        temporal_report = TemporalEvidenceVerificationReport.model_validate(
            _read_json(output_dir / "temporal-verification-report.json")
        )
        inventory["temporal_evidence"] = {
            "profile": capability.profile,
            "capability_id": capability.content_sha256,
            "corpus_snapshot_id": capability.corpus_snapshot_id,
            "retrieval_policy_id": capability.retrieval_policy_id,
            "access_policy_id": capability.access_policy_id,
            "availability_schedule_id": capability.availability_schedule_id,
            "branch_namespace_policy_id": capability.branch_namespace_policy_id,
            "cost_policy_id": capability.simulated_cost_policy_id,
            "access_count": temporal_report.access_count,
            "reliance_count": temporal_report.reliance_count,
            "carrier_count": temporal_report.carrier_count,
            "verification_report_id": temporal_report.content_sha256,
        }
    return inventory


def _world_session_request(identity: str) -> WorldSessionRequest:
    return WorldSessionRequest(
        execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
        open_mode=WorldSessionOpenMode.START,
        session_id=f"session.{identity}",
        task_world_id=PUMP_STATION_TASK_WORLD_ID,
        agent_tenure_id=f"tenure.{identity}",
        run_id=f"run.{identity}",
        episode_id=f"episode.{identity}",
        world_branch_id=f"branch.{identity}",
    )


def _open_pump_station_session(
    *,
    request: WorldSessionRequest,
    repository_root: Path,
    bridge: PumpStationHarborBridge,
) -> PumpStationWorldSession:
    return cast(
        PumpStationWorldSession,
        open_world_session(
            request,
            PumpStationWorldSessionFactory(
                repository_root,
                profile_ref=bridge.profile_ref,
                package_root=bridge.package_root,
                rich_work_processes=bridge.rich_work_processes,
                evidence_health=bridge.evidence_health,
                temporal_evidence=bridge.temporal_evidence,
            ),
        ),
    )


def _local_adapter_registry() -> Any:
    from aec_bench.adapters.local_registry import LocalAdapterRegistry

    return LocalAdapterRegistry()


def _model_system_prompt(
    *,
    registered_profile: bool = False,
    rich_work_processes: bool = False,
    temporal_evidence: bool = False,
) -> str:
    if registered_profile:
        return (
            "You are the accountable wastewater pump-station steward. Use only "
            "the current actor view and declared closed tools. Do not infer latent "
            "pump health, hidden events, another branch, verifier expectations, or "
            "a prescribed action sequence."
        )
    if rich_work_processes:
        temporal_direction = (
            " Search and fetch relevant documentary evidence before the first consequential action."
            if temporal_evidence
            else ""
        )
        return (
            "You are the accountable wastewater pump-station steward. Use only "
            "the declared pump-station tools and live identifiers from the current "
            "actor view. Treat blocked, active, or suspended work as unfinished. "
            "Recheck dependencies and resources before resume or cancellation. "
            "Never invent evidence or hidden state. Stop only when Pump A has "
            "passed post-maintenance verification, Pump B has passed functional "
            "checks, and no live work or follow-up remains." + temporal_direction
        )
    return (
        "You are the accountable wastewater pump-station steward. "
        "Use only the declared pump-station tools. Work only from the current "
        "actor view and evidence returned by those tools. Never invent an "
        "identifier or evidence value. Give each proposal a unique proposal_id. "
        "A rejected proposal does not change the world; inspect the returned "
        "view and choose a permitted next action. Continue until the current "
        "view contains passed post-maintenance verification, no open stewardship "
        "obligation, and a provisionally closed work order. A supported run-in "
        "restriction can remain active. Then return a short factual summary."
    )


def _model_instruction(
    *,
    registered_profile: bool = False,
    rich_work_processes: bool = False,
    temporal_evidence: bool = False,
) -> str:
    if registered_profile:
        return (
            "Observe the three-pump station and its visible dates, service plan, "
            "shared resources, and work. Search documentary evidence only when it "
            "helps the current decision. Take no more than one supported stewardship "
            "action, give its reason in plain language, and use only identifiers from "
            "the actor view. Then stop with a short factual summary."
        )
    if rich_work_processes:
        temporal_direction = (
            " First search for the pump obstruction procedure and fetch one supplied reference."
            if temporal_evidence
            else ""
        )
        return (
            "Observe the pump station. Request post-maintenance verification for "
            "pump-a and inspection for pump-b, then transfer duty away from pump-b. "
            "Continue until access and the repair kit are available. Use the live "
            "accepted functional-check evidence and administrative-closeout "
            "dependency to request the permitted Pump A waiver, then resume Pump A "
            "verification. When access is withdrawn, continue until it returns and "
            "resume the suspended verification with its remaining duration. Complete "
            "Pump A verification, resume and complete Pump B inspection, then request "
            "obstruction clearance with the live inspection evidence. If work is "
            "suspended, wait for access and resume it. Continue through clearance and "
            "functional checks. Use a unique proposal identifier for every action." + temporal_direction
        )
    return (
        "Start by observing the pump station. Follow this order exactly and use "
        "the live identifiers from the current view: conditionally defer pump-a, "
        "transfer duty away from pump-a, inspect pump-a, continue until the "
        "inspection is complete, continue until access and the repair kit are "
        "available, clear the obstruction with the live inspection evidence, "
        "continue until clearance is complete, continue until functional checks "
        "are complete, provisionally return pump-a with the live passed "
        "functional-check evidence, request provisional closure before "
        "post-maintenance verification with the live work-order identifier, run "
        "post-maintenance verification for pump-a, and continue until verification "
        "is complete. Use a unique proposal identifier for each proposal. Do not "
        "start work on pump-b and do not repeat completed actions. Advance time "
        "only through the declared operation tool. Stop when the current view "
        "contains passed post-maintenance verification, no open stewardship "
        "obligation, and a provisionally closed work order."
    )


def _write_model_evidence(
    *,
    destination: Path,
    adapter_result: AdapterResult,
    model: str,
    max_turns: int,
) -> None:
    raw_output = adapter_result.raw_output_text or ""
    (destination / "output.md").write_text(raw_output, encoding="utf-8")
    _write_json(
        destination / "agent-result.json",
        {
            "status": adapter_result.agent_output.status.value,
            "model": model,
            "adapter": "tool_loop",
            "adapter_name": adapter_result.adapter_name,
            "resolved_model": adapter_result.resolved_model,
            "configuration_record": adapter_result.configuration_record,
            "max_turns": max_turns,
            "turns_used": adapter_result.turns_used,
            "input_tokens": adapter_result.usage_input_tokens or 0,
            "output_tokens": adapter_result.usage_output_tokens or 0,
            "cache_read_tokens": adapter_result.usage_cache_read_tokens or 0,
            "cache_write_tokens": adapter_result.usage_cache_write_tokens or 0,
            "failure_kind": (None if adapter_result.failure_kind is None else adapter_result.failure_kind.value),
            "provider_error": adapter_result.provider_error,
        },
    )
    with (destination / "conversation.jsonl").open("w", encoding="utf-8") as handle:
        for entry in adapter_result.transcript:
            handle.write(
                json.dumps(
                    {
                        "role": entry.role.value,
                        "event": entry.event.value,
                        "content": entry.content,
                        "tool_name": entry.tool_name,
                        "tool_call_id": entry.tool_call_id,
                    },
                    sort_keys=True,
                )
                + "\n"
            )


def _write_session_evidence(
    *,
    destination: Path,
    request: WorldSessionRequest,
    result: WorldSessionResult,
    verification: PumpStationVerificationReport | PumpStationVerificationReportV4,
) -> None:
    _write_json(
        destination / "world-session-request.json",
        request.model_dump(mode="json"),
    )
    _write_json(
        destination / "world-session-result.json",
        result.model_dump(mode="json"),
    )
    _write_json(
        destination / "verification-report.json",
        _verification_payload(verification),
    )


def _verification_payload(
    report: PumpStationVerificationReport | PumpStationVerificationReportV4,
) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(json.dumps(asdict(report))))


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return cast(dict[str, Any], payload)


__all__ = (
    "CompletedPumpStationRolloutModelSession",
    "CompletedPumpStationRolloutSession",
    "CompletedPumpStationReferenceSession",
    "CompletedPumpStationModelSession",
    "PUMP_STATION_HARBOR_RUN_SCHEMA_VERSION",
    "PUMP_STATION_MODEL_CONTROLLER_MODE",
    "PUMP_STATION_MODEL_MAX_TURNS",
    "PUMP_STATION_REFERENCE_CONTROLLER_ID",
    "run_pump_station_evidence_health_reference_session",
    "run_pump_station_model_session",
    "run_pump_station_rich_work_reference_session",
    "run_pump_station_reference_session",
    "run_pump_station_rollout_reference_session",
    "run_pump_station_rollout_model_session",
)
