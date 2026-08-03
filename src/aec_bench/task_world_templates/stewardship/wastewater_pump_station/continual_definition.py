# ABOUTME: Registers the pump-station world and its exact ASW-8 RS1 profile.
# ABOUTME: Reuses certified profile loaders without creating another pump execution path.

from __future__ import annotations

import hashlib
import inspect
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache

from aec_bench.contracts.continual_world import ContinualWorldDefinitionSpec, ContinualWorldProfileRef
from aec_bench.contracts.harness_kernel import canonical_content_sha256
from aec_bench.task_world_templates.continual.definition import (
    ContinualWorldDefinition,
    LoadedContinualWorldProfile,
    python_source_sha256,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station import (
    reference_package_reader,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_runtime import (
    PumpStationCoupledWorldState,
    create_asw_8_world_state,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_kernel import (
    coupled_pump_station_model_from_package,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_models import (
    PumpStationCoupledModel,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_package_models import (
    ReferencePackage,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_system import (
    PUMP_STATION_REFERENCE_SYSTEM_ID,
    PumpStationReferenceSystem,
    load_reference_system,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_session import (
    PUMP_STATION_TASK_WORLD_ID,
)

PUMP_STATION_CONTINUAL_DEFINITION_VERSION = "1"
PUMP_STATION_RS1_PROFILE_VERSION = "1"


@dataclass(frozen=True)
class PumpStationContinualProfile:
    """Validated RS1 data and opening state supplied by the registered pump port."""

    reference_system: PumpStationReferenceSystem
    station_package: ReferencePackage
    model: PumpStationCoupledModel
    opening_state: PumpStationCoupledWorldState


def _validated_profile_data() -> tuple[PumpStationReferenceSystem, ReferencePackage]:
    system = load_reference_system()
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


def _load_pump_station_profile(reference: ContinualWorldProfileRef) -> LoadedContinualWorldProfile:
    if reference.profile_id != PUMP_STATION_REFERENCE_SYSTEM_ID:
        raise ValueError("pump continual-world profile identity differs")
    system, package = _validated_profile_data()
    task_world_id = str(system.descriptor.get("task_world_id"))
    if task_world_id != reference.task_world_id or system.descriptor_content_id != reference.profile_content_sha256:
        raise ValueError("pump continual-world profile content differs")
    return LoadedContinualWorldProfile(
        reference=reference,
        value=PumpStationContinualProfile(
            reference_system=system,
            station_package=package,
            model=coupled_pump_station_model_from_package(package),
            opening_state=create_asw_8_world_state(),
        ),
    )


def _implementation_content_sha256() -> str:
    from aec_bench.task_world_templates.stewardship.wastewater_pump_station import (
        continual_rollout_adapter,
    )

    adapter_source_sha256 = hashlib.sha256(
        inspect.getsource(continual_rollout_adapter).encode("utf-8"),
    ).hexdigest()
    reference_reader_source_sha256 = hashlib.sha256(
        inspect.getsource(reference_package_reader).encode("utf-8"),
    ).hexdigest()
    return canonical_content_sha256(
        {
            "loaded_profile": python_source_sha256(PumpStationContinualProfile),
            "profile_loader": python_source_sha256(_load_pump_station_profile),
            "profile_validator": python_source_sha256(_validated_profile_data),
            "reference_system_loader": python_source_sha256(load_reference_system),
            "reference_package_reader_module": reference_reader_source_sha256,
            "model_factory": python_source_sha256(coupled_pump_station_model_from_package),
            "opening_state_factory": python_source_sha256(create_asw_8_world_state),
            "branch_adapter_module": adapter_source_sha256,
        }
    )


@cache
def pump_station_continual_world_definition() -> ContinualWorldDefinition:
    """Return the content-pinned pump definition without starting a world run."""
    from aec_bench.task_world_templates.stewardship.wastewater_pump_station.continual_rollout_adapter import (
        PumpStationContinualWorldBranchPort,
    )

    system, _ = _validated_profile_data()
    task_world_id = str(system.descriptor.get("task_world_id"))
    profile = ContinualWorldProfileRef(
        task_world_id=task_world_id,
        profile_id=PUMP_STATION_REFERENCE_SYSTEM_ID,
        profile_version=PUMP_STATION_RS1_PROFILE_VERSION,
        profile_content_sha256=system.descriptor_content_id,
    )
    return ContinualWorldDefinition(
        spec=ContinualWorldDefinitionSpec(
            task_world_id=task_world_id,
            definition_version=PUMP_STATION_CONTINUAL_DEFINITION_VERSION,
            implementation_content_sha256=_implementation_content_sha256(),
            profiles=(profile,),
        ),
        profile_loader=_load_pump_station_profile,
        branch_port=PumpStationContinualWorldBranchPort(),
    )
