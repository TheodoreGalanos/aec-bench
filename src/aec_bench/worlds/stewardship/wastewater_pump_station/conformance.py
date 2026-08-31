# ABOUTME: Supplies the pump-station scenario for the shared world conformance kit.
# ABOUTME: Uses the durable reference controller for order, replay, terminal, and evaluation proofs.

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

from aec_bench.contracts.world_interface import WorldActorActionRequest
from aec_bench.worlds.conformance import WorldConformanceCase, WorldConformanceScenario
from aec_bench.worlds.stewardship.wastewater_pump_station.episode_runtime import PumpStationEpisodeHost
from aec_bench.worlds.stewardship.wastewater_pump_station.evaluation import evaluate_pump_station_reference_run
from aec_bench.worlds.stewardship.wastewater_pump_station.physical_kernel import (
    coupled_pump_station_model_from_package,
    transition_coupled_pump_station,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.physical_models import (
    PumpExposure,
    PumpStationCoupledModel,
    PumpStationCoupledOperatingInterval,
    PumpStationCoupledPhysicalState,
    PumpStationOperatingDelta,
    PumpStationPumpAvailability,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.reference_controller import (
    run_pump_station_reference_controller,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.reference_package_reader import (
    REFERENCE_PROFILE_V2,
    load_reference_package,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.reference_system import (
    PUMP_STATION_REFERENCE_SYSTEM_ID,
    create_opening_physical_state,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run_serialization import (
    load_pump_station_artifact,
    pump_station_artifact_bytes,
)

type PumpStationConformanceObservation = tuple[
    int,
    tuple[tuple[str, PumpExposure], ...],
    tuple[PumpStationPumpAvailability, ...],
    tuple[str, ...],
    tuple[str, ...],
]


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


def _observe(state: PumpStationCoupledPhysicalState) -> PumpStationConformanceObservation:
    return (
        state.calendar_seconds,
        tuple((pump.pump_id, pump.exposure) for pump in state.pumps),
        tuple(state.availability(pump.pump_id) for pump in state.pumps),
        state.service_running_pump_ids,
        state.test_running_pump_ids,
    )


def _assert_actor_safe(observation: PumpStationConformanceObservation) -> None:
    assert "condition" not in repr(observation)


def _assert_state_valid(state: PumpStationCoupledPhysicalState) -> None:
    assert isinstance(state, PumpStationCoupledPhysicalState)
    assert len(state.pumps) == 3


def _state_codec(state: PumpStationCoupledPhysicalState) -> bytes:
    return pump_station_artifact_bytes(state)


def _state_decoder(encoded: bytes) -> PumpStationCoupledPhysicalState:
    return load_pump_station_artifact(encoded, PumpStationCoupledPhysicalState)


def _observation_codec(observation: PumpStationConformanceObservation) -> bytes:
    return pump_station_artifact_bytes(observation)


def _observation_decoder(encoded: bytes) -> PumpStationConformanceObservation:
    return cast(
        PumpStationConformanceObservation,
        load_pump_station_artifact(encoded, PumpStationConformanceObservation),
    )


def _assert_owner_conformance(seed: int) -> None:
    with (
        TemporaryDirectory(prefix=f"aec-bench-pump-conformance-{seed}-first-") as first_root,
        TemporaryDirectory(prefix=f"aec-bench-pump-conformance-{seed}-second-") as second_root,
    ):
        run_kwargs = {
            "run_id": f"pump-conformance-{seed}-run",
            "episode_id": f"pump-conformance-{seed}-episode",
            "world_branch_id": f"pump-conformance-{seed}-branch",
            "reference_system_id": PUMP_STATION_REFERENCE_SYSTEM_ID,
        }
        first = run_pump_station_reference_controller(Path(first_root) / "run", **run_kwargs)
        second = run_pump_station_reference_controller(Path(second_root) / "run", **run_kwargs)
        assert first.semantic_outcome == second.semantic_outcome
        assert first.run.state == second.run.state

        steps = first.run.repository.command_steps()
        assert len(steps) == 25
        report = first.run.verify()
        assert tuple(step.transition.receipt.transition_id for step in steps) == report.replayed_transition_ids
        assert tuple(step.command.based_on_sequence for step in steps) == tuple(range(25))

        host = PumpStationEpisodeHost(Path(first_root) / "run")
        observation = host.observe()
        before = first.run.snapshot()
        rejected = host.invoke(
            WorldActorActionRequest(
                request_id=f"pump-conformance-{seed}-terminal-rejection",
                decision_id=observation.decision_id,
                action_name="continue_operation",
                arguments={"reason": "No declared actor-visible event remains."},
            )
        )
        assert rejected.status == "rejected"
        assert rejected.task_receipt == {"code": "no-next-event", "message": "no-next-event: 223200"}
        assert rejected.next_observation == observation
        assert first.run.snapshot() == before

        evaluation = evaluate_pump_station_reference_run(first.run)
        assert evaluation.evidence.initial_state_id == first.run.manifest.initial_state_id
        assert evaluation.evidence.terminal_state_id == first.run.state.state_id
        assert evaluation.evidence.replayed_transition_ids == report.replayed_transition_ids
        assert evaluation.evidence.replayed_transition_ids


def _scenario(_seed: int) -> WorldConformanceScenario:
    model = _model()
    opening = create_opening_physical_state()
    return WorldConformanceScenario(
        initial_state=lambda _seed: create_opening_physical_state(),
        observe=_observe,
        transition=lambda state, action: transition_coupled_pump_station(model, state, action),
        actions=(_interval(opening.calendar_seconds, 60), _interval(opening.calendar_seconds + 60, 120)),
        invalid_action=_interval(opening.calendar_seconds + 1, 60),
        assert_observation_safe=_assert_actor_safe,
        assert_state_valid=_assert_state_valid,
        state_codec=_state_codec,
        state_decoder=_state_decoder,
        observation_codec=_observation_codec,
        observation_decoder=_observation_decoder,
        state_size_bound=100_000,
        observation_size_bound=20_000,
        evaluate=lambda state: (state.calendar_seconds, tuple(pump.exposure for pump in state.pumps)),
        assert_owner_conformance=_assert_owner_conformance,
    )


WORLD_CONFORMANCE_CASE = WorldConformanceCase(
    world_key="stewardship/wastewater-pump-station",
    scenario=_scenario,
    requires_terminal_rejection=True,
)


def world_conformance_case() -> WorldConformanceCase:
    """Return the maintained pump-station conformance case."""

    return WORLD_CONFORMANCE_CASE


__all__ = ("WORLD_CONFORMANCE_CASE", "world_conformance_case")
