# ABOUTME: Unit-tests the current task-local pump proposal values and actor argument boundary.
# ABOUTME: Proves proposals are immutable and obsolete action shapes fail current validation.

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from aec_bench.contracts.world_interface import WorldInterfaceError
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.actor_interface import (
    pump_station_proposal_from_validated_arguments,
    validate_pump_station_actor_arguments,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    ProposalContext,
    RequestDutyAssignment,
)


def _context(*, reason: str = "Use the declared duty order.") -> ProposalContext:
    return ProposalContext(
        proposal_id="proposal-current",
        agent_tenure_id="pump-station-actor-tenure",
        based_on_sequence=0,
        base_view_id="view-current",
        information_set_id="information-current",
        reason=reason,
    )


def test_current_proposal_is_immutable_and_unversioned() -> None:
    proposal = RequestDutyAssignment(
        context=_context(),
        ordered_pump_ids=("pump-a", "pump-b"),
    )

    assert not hasattr(proposal, "schema_version")
    assert not hasattr(proposal, "content_sha256")
    with pytest.raises(FrozenInstanceError):
        proposal.__setattr__("ordered_pump_ids", ("pump-b",))


def test_current_actor_arguments_build_one_task_local_proposal() -> None:
    arguments: dict[str, object] = {
        "reason": "Use the declared duty order.",
        "ordered_pump_ids": ("pump-a", "pump-b"),
    }

    validated = validate_pump_station_actor_arguments("request_duty_assignment", arguments)
    proposal = pump_station_proposal_from_validated_arguments(
        action_name="request_duty_assignment",
        arguments=validated,
        context=_context(),
    )

    assert isinstance(proposal, RequestDutyAssignment)
    assert proposal.ordered_pump_ids == ("pump-a", "pump-b")


@pytest.mark.parametrize("action_name", ["transfer_duty", "request_conditional_deferral"])
def test_obsolete_actor_actions_fail_current_validation(action_name: str) -> None:
    with pytest.raises(WorldInterfaceError, match="unknown-actor-action"):
        validate_pump_station_actor_arguments(action_name, {"reason": "obsolete"})
