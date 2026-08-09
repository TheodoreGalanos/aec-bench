# ABOUTME: Unit-tests the current task-local pump actions and installed argument boundary.
# ABOUTME: Proves actions are immutable and obsolete action shapes fail current validation.

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from aec_bench.contracts.world_interface import WorldInterfaceError
from aec_bench.worlds.stewardship.wastewater_pump_station.actor_interface import (
    parse_pump_station_action,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.stewardship_models import (
    RequestDutyAssignment,
)


def test_current_action_is_immutable_and_unversioned() -> None:
    action = RequestDutyAssignment(
        reason="Use the declared duty order.",
        ordered_pump_ids=("pump-a", "pump-b"),
    )

    assert not hasattr(action, "schema_version")
    assert not hasattr(action, "content_sha256")
    with pytest.raises(FrozenInstanceError):
        action.__setattr__("ordered_pump_ids", ("pump-b",))


def test_current_actor_arguments_build_one_task_local_action() -> None:
    arguments: dict[str, object] = {
        "reason": "Use the declared duty order.",
        "ordered_pump_ids": ("pump-a", "pump-b"),
    }

    action = parse_pump_station_action("request_duty_assignment", arguments)

    assert isinstance(action, RequestDutyAssignment)
    assert action.ordered_pump_ids == ("pump-a", "pump-b")


@pytest.mark.parametrize("action_name", ["transfer_duty", "request_conditional_deferral"])
def test_obsolete_actor_actions_fail_current_validation(action_name: str) -> None:
    with pytest.raises(WorldInterfaceError, match="unknown-actor-action"):
        parse_pump_station_action(action_name, {"reason": "obsolete"})
