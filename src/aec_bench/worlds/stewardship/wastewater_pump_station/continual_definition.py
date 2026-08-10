# ABOUTME: Registers the pump-station world and its content-pinned scenario profiles.
# ABOUTME: Keeps execution, evaluation, Harbor, and rollout composition with their concrete owners.

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from aec_bench.contracts.interactive_world import InteractiveWorldProfileRef, WorldBuildRef
from aec_bench.worlds.runtime.definition import (
    InteractiveWorldDefinition,
    LoadedInteractiveWorldProfile,
    source_tree_world_build,
)
from aec_bench.worlds.stewardship.wastewater_pump_station import reference_package_reader
from aec_bench.worlds.stewardship.wastewater_pump_station.coupled_runtime import (
    initial_state,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.episode_runtime import (
    PUMP_STATION_TASK_WORLD_ID,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.physical_kernel import (
    coupled_pump_station_model_from_package,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.physical_models import (
    PumpStationCoupledModel,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.reference_package_models import (
    ReferencePackage,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.reference_system import (
    PumpStationReferenceSystem,
    list_reference_system_ids,
    load_reference_system,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.stewardship_models import (
    PumpStationStewardshipState,
)


@dataclass(frozen=True)
class PumpStationContinualProfile:
    """Validated scenario data and opening state for the registered pump world."""

    reference_system: PumpStationReferenceSystem
    station_package: ReferencePackage
    model: PumpStationCoupledModel
    opening_state: PumpStationStewardshipState


def pump_station_profile_ref(profile: LoadedInteractiveWorldProfile) -> InteractiveWorldProfileRef:
    """Validate and return the exact current pump profile reference."""

    profile_value = profile.value
    if not isinstance(profile_value, PumpStationContinualProfile):
        raise TypeError("registered pump runtime received another profile value")
    reference = profile.reference
    if (
        reference.task_world_id != PUMP_STATION_TASK_WORLD_ID
        or reference.profile_id != profile_value.reference_system.descriptor_id
        or profile_value.reference_system.profile_content_id != reference.profile_content_sha256
        or profile_value.station_package.profile_id != profile_value.reference_system.station_data_profile_id
    ):
        raise ValueError("registered pump profile content differs")
    return reference


def _validated_profile_data(reference_system_id: str) -> tuple[PumpStationReferenceSystem, ReferencePackage]:
    system = load_reference_system(reference_system_id=reference_system_id)
    task_world_id = str(system.descriptor.get("task_world_id"))
    if task_world_id != PUMP_STATION_TASK_WORLD_ID:
        raise ValueError("pump reference system task-world identity differs")
    station_binding = system.descriptor.get("station_data")
    if not isinstance(station_binding, Mapping):
        raise ValueError("pump reference system station-data binding is missing")
    package = reference_package_reader.load_reference_package(profile_id=system.station_data_profile_id)
    if package.package_content_id != station_binding.get("package_content_id"):
        raise ValueError("pump reference system station-data binding differs")
    return system, package


def _load_pump_station_profile(reference: InteractiveWorldProfileRef) -> LoadedInteractiveWorldProfile:
    system, package = _validated_profile_data(reference.profile_id)
    task_world_id = str(system.descriptor.get("task_world_id"))
    if task_world_id != reference.task_world_id or system.profile_content_id != reference.profile_content_sha256:
        raise ValueError("pump continual-world profile content differs")
    return LoadedInteractiveWorldProfile(
        reference=reference,
        value=PumpStationContinualProfile(
            reference_system=system,
            station_package=package,
            model=coupled_pump_station_model_from_package(package),
            opening_state=initial_state(system),
        ),
    )


@cache
def _pump_station_world_build() -> WorldBuildRef:
    source_root = Path(__file__).resolve().parents[3]
    return source_tree_world_build(
        task_world_id=PUMP_STATION_TASK_WORLD_ID,
        entry_point=(
            "aec_bench.worlds.stewardship.wastewater_pump_station.continual_definition:"
            "pump_station_continual_world_definition"
        ),
        roots=(
            Path(__file__).resolve().parent,
            source_root / "contracts" / "interactive_world.py",
            source_root / "contracts" / "continual_world.py",
            source_root / "contracts" / "harness_kernel.py",
            source_root / "contracts" / "world_interface.py",
            source_root / "worlds" / "runtime",
        ),
    )


def _profile_ref(reference_system_id: str) -> InteractiveWorldProfileRef:
    system, _ = _validated_profile_data(reference_system_id)
    return InteractiveWorldProfileRef(
        task_world_id=PUMP_STATION_TASK_WORLD_ID,
        profile_id=system.descriptor_id,
        profile_content_sha256=system.profile_content_id,
    )


@cache
def pump_station_continual_world_definition() -> InteractiveWorldDefinition:
    """Return the current pump definition and its bundled scenario profiles."""

    profiles = tuple(_profile_ref(reference_system_id) for reference_system_id in list_reference_system_ids())
    return InteractiveWorldDefinition(
        build=_pump_station_world_build(),
        profiles=profiles,
        profile_loader=_load_pump_station_profile,
    )
