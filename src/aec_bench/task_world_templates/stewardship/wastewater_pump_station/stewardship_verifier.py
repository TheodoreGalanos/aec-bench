# ABOUTME: Replays recorded pump-station proposals through the task-owned verifier.
# ABOUTME: Reports integrity facts without mutating the run or exposing private results.

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from aec_bench.contracts.world_interface import (
    WorldActorActionRequest,
    WorldInterfaceError,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.actor_interface import (
    PUMP_STATION_ACTOR_WORKSPACE_TOOL_ID_V2,
    pump_station_proposal_from_validated_arguments_v2,
    validate_pump_station_actor_arguments_v2,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_runtime import (
    project_coupled_information_set,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.evidence_health import (
    PumpStationEvidenceTreatmentRequest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_models import (
    PumpStationCoupledModel,
    PumpStationModel,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_treatments import (
    PumpStationPhysicalTreatmentActivationRequest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_identity import (
    stewardship_state_id,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    ProposalContext,
    PumpStationCoupledStewardshipState,
    PumpStationObligationStatus,
    PumpStationProposal,
    PumpStationProposalError,
    PumpStationRestrictionStatus,
    PumpStationStewardshipState,
    PumpStationTransition,
    PumpStationTransitionV4,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_state_machine import (
    apply_evidence_treatment_schedule,
    apply_physical_treatment_activation,
    apply_stewardship_control_v4,
    apply_stewardship_proposal,
    apply_stewardship_proposal_v4,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_views import (
    PumpStationInformationSet,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_commands import (
    decode_pump_station_v4_command,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_models import (
    PUMP_STATION_RECORD_VERSIONS_V1,
    PUMP_STATION_RECORD_VERSIONS_V2,
    PUMP_STATION_RECORD_VERSIONS_V3,
    PumpStationCommandV4,
    PumpStationRecordVersions,
    PumpStationWorldRunError,
)


@dataclass(frozen=True, slots=True)
class PumpStationRunStep:
    """One recorded bound proposal and its resulting transition."""

    proposal: PumpStationProposal | None
    information_set: PumpStationInformationSet | None
    transition: PumpStationTransition
    control_request: PumpStationEvidenceTreatmentRequest | PumpStationPhysicalTreatmentActivationRequest | None = None

    def __post_init__(self) -> None:
        actor_step = self.proposal is not None and self.information_set is not None
        control_step = self.control_request is not None
        if actor_step == control_step:
            raise ValueError("run step requires exactly one actor or control input")
        if self.proposal is None and self.information_set is not None:
            raise ValueError("control run step cannot contain an information set")


@dataclass(frozen=True, slots=True)
class PumpStationVerificationReport:
    """Private host result of deterministic task replay and integrity checks."""

    valid: bool
    issues: tuple[str, ...]
    replayed_transition_ids: tuple[str, ...]
    final_state_id: str
    active_restriction_ids: tuple[str, ...]
    open_obligation_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PumpStationRunStepV4:
    """One recorded V4 command and its complete replay evidence."""

    command: PumpStationCommandV4
    proposal: PumpStationProposal | None
    information_set: PumpStationInformationSet | None
    transition: PumpStationTransitionV4

    def __post_init__(self) -> None:
        actor_step = self.command.kind == "actor"
        if actor_step != (self.proposal is not None and self.information_set is not None):
            raise ValueError("V4 actor step requires one proposal and information set")


@dataclass(frozen=True, slots=True)
class PumpStationVerificationReportV4:
    """Private result of independent V4 command and transition replay."""

    valid: bool
    issues: tuple[str, ...]
    replayed_transition_ids: tuple[str, ...]
    final_state_id: str


def verify_stewardship_run(
    model: PumpStationModel,
    initial_state: PumpStationStewardshipState,
    steps: tuple[PumpStationRunStep, ...],
    *,
    record_versions: PumpStationRecordVersions | None = None,
) -> PumpStationVerificationReport:
    """Replay immutable run steps from the declared initial state."""
    selected_versions = (
        record_versions
        or {
            "pump-station-stewardship-state.v1": PUMP_STATION_RECORD_VERSIONS_V1,
            "pump-station-stewardship-state.v2": PUMP_STATION_RECORD_VERSIONS_V2,
            "pump-station-stewardship-state.v3": PUMP_STATION_RECORD_VERSIONS_V3,
        }[initial_state.state_version]
    )
    expected_state_version = {
        PUMP_STATION_RECORD_VERSIONS_V1: "pump-station-stewardship-state.v1",
        PUMP_STATION_RECORD_VERSIONS_V2: "pump-station-stewardship-state.v2",
        PUMP_STATION_RECORD_VERSIONS_V3: "pump-station-stewardship-state.v3",
    }[selected_versions]
    state = initial_state
    issues: list[str] = []
    if initial_state.state_version != expected_state_version:
        issues.append("initial-state-version-mismatch")
    replayed_transition_ids: list[str] = []
    for step in steps:
        transition_id = step.transition.receipt.transition_id
        try:
            if step.control_request is not None:
                if isinstance(
                    step.control_request,
                    PumpStationPhysicalTreatmentActivationRequest,
                ):
                    replayed = apply_physical_treatment_activation(
                        state,
                        step.control_request,
                    )
                else:
                    replayed = apply_evidence_treatment_schedule(
                        state,
                        step.control_request,
                    )
            else:
                if step.proposal is None or step.information_set is None:
                    issues.append(f"transition-replay-error:{transition_id}:run-step-shape")
                    break
                replayed = apply_stewardship_proposal(
                    model,
                    state,
                    step.proposal,
                    information_set=step.information_set,
                )
        except PumpStationProposalError as error:
            issues.append(f"transition-replay-error:{transition_id}:{error.code}")
            break
        replayed_transition_ids.append(replayed.receipt.transition_id)
        if replayed != step.transition:
            issues.append(f"transition-replay-mismatch:{transition_id}")
            break
        state = replayed.state
    return PumpStationVerificationReport(
        valid=not issues and len(replayed_transition_ids) == len(steps),
        issues=tuple(issues),
        replayed_transition_ids=tuple(replayed_transition_ids),
        final_state_id=stewardship_state_id(state),
        active_restriction_ids=tuple(
            restriction.restriction_id
            for restriction in state.restrictions
            if restriction.status is PumpStationRestrictionStatus.ACTIVE
        ),
        open_obligation_ids=tuple(
            obligation.obligation_id
            for obligation in state.obligations
            if obligation.status is not PumpStationObligationStatus.FULFILLED
        ),
    )


def verify_stewardship_run_v4(
    model: PumpStationCoupledModel,
    initial_state: PumpStationCoupledStewardshipState,
    steps: tuple[PumpStationRunStepV4, ...],
    *,
    expected_final_state_id: str,
    expected_task_world_id: str,
    expected_run_id: str,
    expected_episode_id: str,
    expected_world_branch_id: str,
    expected_actor_id: str,
    expected_source_artifact_ids: tuple[str, ...],
) -> PumpStationVerificationReportV4:
    """Replay each V4 command from the persisted opening state and exact model."""
    state = initial_state
    issues: list[str] = []
    replayed_transition_ids: list[str] = []
    for step in steps:
        command = step.command
        try:
            observed_scope = (
                command.task_world_id,
                command.run_id,
                command.episode_id,
                command.world_branch_id,
            )
            expected_scope = (
                expected_task_world_id,
                expected_run_id,
                expected_episode_id,
                expected_world_branch_id,
            )
            if observed_scope != expected_scope:
                raise ValueError("command-scope differs from the verified run")
            if command.based_on_sequence != state.sequence or command.base_state_id != state.state_id:
                raise ValueError("command-parent differs from the replayed state")
            decoded_command = decode_pump_station_v4_command(command)
            if command.kind == "actor":
                if step.proposal is None or step.information_set is None:
                    raise ValueError("actor step lacks proposal evidence")
                if not isinstance(decoded_command, WorldActorActionRequest):
                    raise ValueError("actor command decoded as a root control")
                request = decoded_command
                expected_information_set = project_coupled_information_set(
                    state,
                    episode_id=expected_episode_id,
                    world_branch_id=expected_world_branch_id,
                    actor_id=expected_actor_id,
                    agent_tenure_id=request.binding.agent_tenure_id,
                    source_artifact_ids=expected_source_artifact_ids,
                    workspace_tool_ids=(PUMP_STATION_ACTOR_WORKSPACE_TOOL_ID_V2,),
                )
                if step.information_set != expected_information_set:
                    raise ValueError("actor-view or information-set content differs")
                arguments = validate_pump_station_actor_arguments_v2(
                    command.action_name,
                    cast(dict[str, object], request.arguments),
                )
                reason = arguments.get("reason")
                if not isinstance(reason, str):
                    raise ValueError("actor reason is missing")
                expected_proposal = pump_station_proposal_from_validated_arguments_v2(
                    action_name=command.action_name,
                    arguments=arguments,
                    context=ProposalContext(
                        proposal_id=command.request_id,
                        agent_tenure_id=request.binding.agent_tenure_id,
                        based_on_sequence=command.based_on_sequence,
                        base_view_id=request.binding.actor_view_id,
                        information_set_id=request.binding.information_set_id,
                        reason=reason,
                    ),
                )
                if expected_proposal != step.proposal:
                    raise ValueError("stored actor proposal differs from its command")
                replayed = apply_stewardship_proposal_v4(
                    model,
                    state,
                    step.proposal,
                    information_set=step.information_set,
                )
            else:
                if isinstance(decoded_command, WorldActorActionRequest):
                    raise ValueError("root-control command decoded as an actor request")
                replayed = apply_stewardship_control_v4(state, decoded_command)
        except (
            PumpStationProposalError,
            PumpStationWorldRunError,
            WorldInterfaceError,
            TypeError,
            ValueError,
        ) as error:
            issues.append(f"transition-replay-error:{step.transition.receipt.transition_id}:{error}")
            break
        replayed_transition_ids.append(replayed.receipt.transition_id)
        if replayed != step.transition:
            issues.append(f"transition-replay-mismatch:{step.transition.receipt.transition_id}")
            break
        state = replayed.state
    final_state_id = stewardship_state_id(state)
    if not issues and final_state_id != expected_final_state_id:
        issues.append("terminal-state-mismatch")
    return PumpStationVerificationReportV4(
        valid=not issues and len(replayed_transition_ids) == len(steps),
        issues=tuple(issues),
        replayed_transition_ids=tuple(replayed_transition_ids),
        final_state_id=final_state_id,
    )
