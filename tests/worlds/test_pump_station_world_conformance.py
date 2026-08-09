# ABOUTME: Proves the registered pump transition uses the shared accepted/rejected world values.
# ABOUTME: Covers deterministic physics, rejection safety, hidden projection, and monotonic exposure.

from __future__ import annotations

from dataclasses import asdict
from typing import cast

import pytest
from hypothesis import given
from hypothesis import strategies as st

from aec_bench.worlds.runtime.world_logic import Transition
from aec_bench.worlds.stewardship.wastewater_pump_station import coupled_runtime
from aec_bench.worlds.stewardship.wastewater_pump_station.actor_interface import (
    parse_pump_station_action,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.coupled_runtime import (
    initial_state,
    observe,
    transition,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.physical_kernel import (
    coupled_pump_station_model_from_package,
    transition_coupled_pump_station,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.physical_models import (
    PumpStationCoupledModel,
    PumpStationCoupledOperatingInterval,
    PumpStationCoupledPhysicalState,
    PumpStationOperatingDelta,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.reference_package_reader import (
    REFERENCE_PROFILE_V2,
    load_reference_package,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.reference_system import (
    create_opening_physical_state,
)
from tests.worlds.world_conformance import assert_world_conformance


def _model() -> PumpStationCoupledModel:
    return coupled_pump_station_model_from_package(load_reference_package(profile_id=REFERENCE_PROFILE_V2))


def _interval(start: int, duration: int) -> PumpStationCoupledOperatingInterval:
    return PumpStationCoupledOperatingInterval(
        start_calendar_seconds=start,
        end_calendar_seconds=start + duration,
        required_service_scu=1,
        baseline_assignment_pump_ids=("pump-c",),
        actual_assignment_pump_ids=("pump-c",),
        service_running_pump_ids=("pump-c",),
        test_running_pump_ids=(),
        pump_deltas=cast(
            tuple[PumpStationOperatingDelta, PumpStationOperatingDelta, PumpStationOperatingDelta],
            tuple(
                PumpStationOperatingDelta(
                    pump_id=pump_id,
                    service_runtime_seconds=duration if pump_id == "pump-c" else 0,
                    test_runtime_seconds=0,
                    attributed_outage_episode_id=None,
                )
                for pump_id in ("pump-a", "pump-b", "pump-c")
            ),
        ),
    )


def _observe(state: PumpStationCoupledPhysicalState) -> tuple[object, ...]:
    return (
        state.calendar_seconds,
        tuple((pump.pump_id, pump.exposure) for pump in state.pumps),
        tuple(state.availability(pump.pump_id) for pump in state.pumps),
        state.service_running_pump_ids,
        state.test_running_pump_ids,
    )


def _assert_actor_safe(observation: tuple[object, ...]) -> None:
    assert "condition" not in repr(observation)


def test_pump_station_physical_world_conforms_to_shared_values() -> None:
    model = _model()
    opening = create_opening_physical_state()
    start = opening.calendar_seconds
    final_state = assert_world_conformance(
        initial_state=lambda _seed: create_opening_physical_state(),
        observe=_observe,
        transition=lambda state, action: transition_coupled_pump_station(model, state, action),
        actions=(_interval(start, 60), _interval(start + 60, 120)),
        invalid_action=_interval(start + 1, 60),
        assert_observation_safe=_assert_actor_safe,
    )

    for opening_pump, final_pump in zip(opening.pumps, final_state.pumps, strict=True):
        assert final_pump.exposure.runtime_seconds >= opening_pump.exposure.runtime_seconds
        assert final_pump.exposure.completed_starts >= opening_pump.exposure.completed_starts


def test_registered_pump_actor_transition_uses_physical_world_transition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    original = coupled_runtime.transition_coupled_pump_station

    def record_transition(model, state, action):
        nonlocal calls
        calls += 1
        return original(model, state, action)

    monkeypatch.setattr(coupled_runtime, "transition_coupled_pump_station", record_transition)
    initial = initial_state()
    initial_view = observe(initial)
    applied = transition(
        initial,
        request_id="kernel-route",
        action=parse_pump_station_action(
            "continue_operation",
            {"reason": "Advance through the registered actor transition."},
        ),
        model=_model(),
    )
    final_view = observe(applied.state, sequence=1)

    assert calls == 1
    assert applied.state.calendar_seconds > initial.calendar_seconds
    assert "condition" not in repr(asdict(initial_view))
    assert "condition" not in repr(asdict(final_view))


@given(
    first_duration=st.integers(min_value=1, max_value=7_200),
    second_duration=st.integers(min_value=1, max_value=7_200),
)
def test_pump_runtime_and_starts_never_decrease(first_duration: int, second_duration: int) -> None:
    model = _model()
    initial = create_opening_physical_state()
    first = transition_coupled_pump_station(
        model,
        initial,
        _interval(initial.calendar_seconds, first_duration),
    )
    assert isinstance(first, Transition)
    second = transition_coupled_pump_station(
        model,
        first.state,
        _interval(first.state.calendar_seconds, second_duration),
    )
    assert isinstance(second, Transition)

    for initial_pump, first_pump, second_pump in zip(
        initial.pumps,
        first.state.pumps,
        second.state.pumps,
        strict=True,
    ):
        assert initial_pump.exposure.runtime_seconds <= first_pump.exposure.runtime_seconds
        assert first_pump.exposure.runtime_seconds <= second_pump.exposure.runtime_seconds
        assert initial_pump.exposure.completed_starts <= first_pump.exposure.completed_starts
        assert first_pump.exposure.completed_starts <= second_pump.exposure.completed_starts
