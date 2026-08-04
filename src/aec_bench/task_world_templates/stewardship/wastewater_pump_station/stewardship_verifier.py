# ABOUTME: Replays recorded pump-station actions through the task-owned verifier.
# ABOUTME: Reports integrity facts without mutating the run or exposing private results.

from __future__ import annotations

from dataclasses import dataclass

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.actor_interface import (
    PUMP_STATION_ACTOR_WORKSPACE_TOOL_ID,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_runtime import (
    apply_control,
    project_coupled_information_set,
    transition,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_work import (
    PumpStationBacklogStatus,
    resource_conservation,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_models import (
    PumpStationCoupledModel,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_identity import (
    stewardship_content_id,
    stewardship_state_id,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    PumpStationActionError,
    PumpStationCoupledTransition,
    PumpStationStewardshipState,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_models import (
    PumpStationCommand,
    PumpStationWorldRunError,
)


@dataclass(frozen=True, slots=True)
class PumpStationCoupledRunStep:
    """One recorded current command and its transition evidence."""

    command: PumpStationCommand
    transition: PumpStationCoupledTransition


@dataclass(frozen=True, slots=True)
class PumpStationDutyConservationReport:
    """Derived service, runtime, and collateral balances."""

    required_capacity_seconds: int
    served_capacity_seconds: int
    unserved_capacity_seconds: int
    assigned_capacity_seconds: int
    surplus_capacity_seconds: int
    service_runtime_seconds: int
    test_runtime_seconds: int
    total_pump_runtime_delta_seconds: int
    collateral_runtime_seconds: int
    required_residual_seconds: int
    assigned_residual_seconds: int
    runtime_residual_seconds: int
    collateral_residual_seconds: int
    valid: bool


@dataclass(frozen=True, slots=True)
class PumpStationResourceConservationReport:
    """Derived current resource-pool balance."""

    reusable_pool_count: int
    consumable_pool_count: int
    failed_pool_ids: tuple[str, ...]
    valid: bool


@dataclass(frozen=True, slots=True)
class PumpStationWorkConservationReport:
    """Derived durable work-identity balance."""

    opening_ids: tuple[str, ...]
    generated_ids: tuple[str, ...]
    terminal_ids: tuple[str, ...]
    closing_ids: tuple[str, ...]
    residual_ids: tuple[str, ...]
    valid: bool


@dataclass(frozen=True, slots=True)
class PumpStationLiabilityConservationReport:
    """Derived canonical liability-owner identity balance."""

    opening_ids: tuple[str, ...]
    created_ids: tuple[str, ...]
    discharged_ids: tuple[str, ...]
    transferred_ids: tuple[str, ...]
    closing_ids: tuple[str, ...]
    residual_ids: tuple[str, ...]
    valid: bool


@dataclass(frozen=True, slots=True)
class PumpStationConservationReport:
    """Four independently derived coupled conservation sections."""

    duty: PumpStationDutyConservationReport
    resources: PumpStationResourceConservationReport
    work: PumpStationWorkConservationReport
    liabilities: PumpStationLiabilityConservationReport

    @property
    def valid(self) -> bool:
        """Return whether every conservation section is valid."""
        return self.duty.valid and self.resources.valid and self.work.valid and self.liabilities.valid

    @property
    def content_id(self) -> str:
        """Return the canonical report identity."""
        return stewardship_content_id(self)


@dataclass(frozen=True, slots=True)
class PumpStationCoupledVerificationReport:
    """Private result of independent coupled command and transition replay."""

    valid: bool
    replay_valid: bool
    actor_actions_valid: bool
    host_controls_valid: bool
    issues: tuple[str, ...]
    replayed_transition_ids: tuple[str, ...]
    final_state_id: str
    conservation: PumpStationConservationReport

    @property
    def content_id(self) -> str:
        """Return the canonical verification-report identity."""
        return stewardship_content_id(self)


def derive_pump_station_conservation_report(
    opening_state: PumpStationStewardshipState,
    terminal_state: PumpStationStewardshipState,
) -> PumpStationConservationReport:
    """Derive four coupled balances from the declared opening and terminal states."""
    required = served = unserved = assigned = surplus = 0
    service_runtime = test_runtime = total_runtime_delta = collateral = 0
    for interval in terminal_state.operating_intervals:
        elapsed = interval.elapsed_seconds
        assigned_capacity = len(interval.service_running_pump_ids)
        served_capacity = min(interval.required_service_scu, assigned_capacity)
        required += interval.required_service_scu * elapsed
        served += served_capacity * elapsed
        unserved += (interval.required_service_scu - served_capacity) * elapsed
        assigned += assigned_capacity * elapsed
        surplus += max(0, assigned_capacity - interval.required_service_scu) * elapsed
        for delta in interval.pump_deltas:
            service_runtime += delta.service_runtime_seconds
            test_runtime += delta.test_runtime_seconds
            if delta.opening_exposure is not None and delta.closing_exposure is not None:
                total_runtime_delta += delta.closing_exposure.runtime_seconds - delta.opening_exposure.runtime_seconds
            collateral += delta.collateral_runtime_seconds
    recorded_collateral = sum(row[2] for row in terminal_state.collateral_runtime)
    duty = PumpStationDutyConservationReport(
        required_capacity_seconds=required,
        served_capacity_seconds=served,
        unserved_capacity_seconds=unserved,
        assigned_capacity_seconds=assigned,
        surplus_capacity_seconds=surplus,
        service_runtime_seconds=service_runtime,
        test_runtime_seconds=test_runtime,
        total_pump_runtime_delta_seconds=total_runtime_delta,
        collateral_runtime_seconds=collateral,
        required_residual_seconds=required - served - unserved,
        assigned_residual_seconds=assigned - served - surplus,
        runtime_residual_seconds=total_runtime_delta - service_runtime - test_runtime,
        collateral_residual_seconds=recorded_collateral - collateral,
        valid=(
            required == served + unserved
            and assigned == served + surplus
            and total_runtime_delta == service_runtime + test_runtime
            and recorded_collateral == collateral
        ),
    )

    resource_result = resource_conservation(
        terminal_state.resources,
        terminal_state.resource_reservations,
    )
    reusable_pool_count = sum(hasattr(pool, "capacity") for pool in terminal_state.resources.pools)
    resources = PumpStationResourceConservationReport(
        reusable_pool_count=reusable_pool_count,
        consumable_pool_count=len(terminal_state.resources.pools) - reusable_pool_count,
        failed_pool_ids=resource_result.failure_pool_ids,
        valid=resource_result.valid,
    )

    opening_work_ids = {item.item_id for item in opening_state.backlog}
    generated_work_ids = {record.backlog_item_id for record in terminal_state.generation_records}
    terminal_work_ids = set(terminal_state.terminal_work_item_ids)
    closing_work_ids = {
        item.item_id
        for item in terminal_state.backlog
        if item.status
        in {
            PumpStationBacklogStatus.OPEN,
            PumpStationBacklogStatus.PLANNED,
            PumpStationBacklogStatus.IN_PROGRESS,
            PumpStationBacklogStatus.BLOCKED,
            PumpStationBacklogStatus.COMPLETED,
        }
    }
    work_left = opening_work_ids | generated_work_ids
    work_right = terminal_work_ids | closing_work_ids
    work = PumpStationWorkConservationReport(
        opening_ids=tuple(sorted(opening_work_ids)),
        generated_ids=tuple(sorted(generated_work_ids)),
        terminal_ids=tuple(sorted(terminal_work_ids)),
        closing_ids=tuple(sorted(closing_work_ids)),
        residual_ids=tuple(sorted(work_left ^ work_right)),
        valid=work_left == work_right and not (terminal_work_ids & closing_work_ids),
    )

    opening_liability_ids = set(opening_state.active_liability_ids)
    created_liability_ids = set(terminal_state.created_liability_ids) - opening_liability_ids
    discharged_liability_ids = set(terminal_state.discharged_liability_ids)
    transferred_liability_ids: set[str] = set()
    closing_liability_ids = set(terminal_state.active_liability_ids)
    liability_left = opening_liability_ids | created_liability_ids
    liability_right = discharged_liability_ids | transferred_liability_ids | closing_liability_ids
    liabilities = PumpStationLiabilityConservationReport(
        opening_ids=tuple(sorted(opening_liability_ids)),
        created_ids=tuple(sorted(created_liability_ids)),
        discharged_ids=tuple(sorted(discharged_liability_ids)),
        transferred_ids=(),
        closing_ids=tuple(sorted(closing_liability_ids)),
        residual_ids=tuple(sorted(liability_left ^ liability_right)),
        valid=(liability_left == liability_right and not (discharged_liability_ids & closing_liability_ids)),
    )
    return PumpStationConservationReport(
        duty=duty,
        resources=resources,
        work=work,
        liabilities=liabilities,
    )


def verify_coupled_stewardship_run(
    model: PumpStationCoupledModel,
    initial_state: PumpStationStewardshipState,
    steps: tuple[PumpStationCoupledRunStep, ...],
    *,
    expected_final_state_id: str,
    expected_task_world_id: str,
    expected_run_id: str,
    expected_episode_id: str,
    expected_world_branch_id: str,
    expected_actor_id: str,
    expected_source_artifact_ids: tuple[str, ...],
    initial_sequence: int = 0,
) -> PumpStationCoupledVerificationReport:
    """Replay each coupled command from the persisted opening state and exact model."""
    state = initial_state
    sequence = initial_sequence
    actor_actions_valid = all(
        step.command.action is not None
        and step.command.control is None
        and step.transition.receipt.actor_action
        and step.transition.receipt.request_id == step.command.request_id
        for step in steps
        if step.command.kind == "actor"
    )
    host_controls_valid = all(
        step.command.action is None
        and step.command.control is not None
        and not step.transition.receipt.actor_action
        and step.transition.receipt.request_id == step.command.request_id
        for step in steps
        if step.command.kind != "actor"
    )
    replay_issues: list[str] = []
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
            if command.based_on_sequence != sequence or command.base_state_id != state.state_id:
                raise ValueError("command-parent differs from the replayed state")
            if command.kind == "actor":
                if (
                    command.action is None
                    or command.agent_tenure_id is None
                    or command.actor_view_id is None
                    or command.information_set_id is None
                ):
                    raise ValueError("actor command lacks private decision context")
                expected_information_set = project_coupled_information_set(
                    state,
                    sequence=sequence,
                    episode_id=expected_episode_id,
                    world_branch_id=expected_world_branch_id,
                    actor_id=expected_actor_id,
                    agent_tenure_id=command.agent_tenure_id,
                    source_artifact_ids=expected_source_artifact_ids,
                    workspace_tool_ids=(PUMP_STATION_ACTOR_WORKSPACE_TOOL_ID,),
                )
                if (
                    command.actor_view_id != expected_information_set.base_view.view_id
                    or command.information_set_id != expected_information_set.information_set_id
                ):
                    raise ValueError("actor-view or information-set content differs")
                replayed = transition(
                    state,
                    sequence=sequence + 1,
                    request_id=command.request_id,
                    action=command.action,
                    model=model,
                )
            else:
                if command.control is None:
                    raise ValueError("root-control command lacks its control")
                replayed = apply_control(state, command.control, sequence=sequence + 1)
        except (
            PumpStationActionError,
            PumpStationWorldRunError,
            TypeError,
            ValueError,
        ) as error:
            replay_issues.append(f"transition-replay-error:{step.transition.receipt.transition_id}:{error}")
            break
        replayed_transition_ids.append(replayed.receipt.transition_id)
        if replayed != step.transition:
            replay_issues.append(f"transition-replay-mismatch:{step.transition.receipt.transition_id}")
            break
        state = replayed.state
        sequence = replayed.receipt.sequence
    final_state_id = stewardship_state_id(state)
    if not replay_issues and final_state_id != expected_final_state_id:
        replay_issues.append("terminal-state-mismatch")
    replay_valid = not replay_issues and len(replayed_transition_ids) == len(steps)
    conservation = derive_pump_station_conservation_report(initial_state, state)
    issues: list[str] = []
    if not actor_actions_valid:
        issues.append("actor-action-integrity")
    if not host_controls_valid:
        issues.append("host-control-integrity")
    issues.extend(replay_issues)
    if not conservation.duty.valid:
        issues.append("duty-conservation")
    if not conservation.resources.valid:
        issues.append("resource-conservation")
    if not conservation.work.valid:
        issues.append("work-conservation")
    if not conservation.liabilities.valid:
        issues.append("liability-conservation")
    return PumpStationCoupledVerificationReport(
        valid=(replay_valid and actor_actions_valid and host_controls_valid and conservation.valid),
        replay_valid=replay_valid,
        actor_actions_valid=actor_actions_valid,
        host_controls_valid=host_controls_valid,
        issues=tuple(issues),
        replayed_transition_ids=tuple(replayed_transition_ids),
        final_state_id=final_state_id,
        conservation=conservation,
    )
