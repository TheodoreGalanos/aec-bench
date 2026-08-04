# ABOUTME: Tests the task-neutral continual-world catalogue with two real task consumers.
# ABOUTME: Proves exact pump and SSC-03 profile dispatch without adding another runtime.

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from aec_bench.contracts.continual_world import (
    ContinualWorldProfileRef,
    WorldBuildRef,
)
from aec_bench.meta_harness.evidence_lifecycle import run_evidence_lifecycle
from aec_bench.task_world_templates.continual.catalogue import ContinualWorldCatalogue
from aec_bench.task_world_templates.continual_catalogue import default_continual_world_catalogue
from aec_bench.task_world_templates.lifecycles.ssc03_hydraulic_continual_definition import (
    SSC03_HYDRAULIC_CONTINUAL_WORLD_ID,
    Ssc03HydraulicContinualProfile,
    ssc03_hydraulic_continual_world_definition,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.continual_definition import (
    PumpStationContinualProfile,
    pump_station_continual_world_definition,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.episode_runtime import (
    PUMP_STATION_TASK_WORLD_ID,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_models import (
    PumpStationCoupledModel,
    PumpStationCoupledPhysicalState,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_system import (
    PUMP_STATION_REFERENCE_SYSTEM_ID,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    PumpStationStewardshipState,
)


def test_catalogue_rejects_duplicate_world_id() -> None:
    definition = ssc03_hydraulic_continual_world_definition()

    with pytest.raises(ValueError, match="task world ids must be unique"):
        ContinualWorldCatalogue(definitions=(definition, definition))


def test_catalogue_resolves_exact_content_pinned_definition() -> None:
    catalogue = default_continual_world_catalogue()
    definition = catalogue.get(SSC03_HYDRAULIC_CONTINUAL_WORLD_ID)

    assert catalogue.resolve(definition.ref) is definition


def test_catalogue_rejects_stale_definition_reference() -> None:
    catalogue = default_continual_world_catalogue()
    definition = catalogue.get(SSC03_HYDRAULIC_CONTINUAL_WORLD_ID)
    stale = WorldBuildRef(
        task_world_id=definition.ref.task_world_id,
        entry_point=definition.ref.entry_point,
        artifact_sha256="f" * 64,
    )

    with pytest.raises(ValueError, match="world build does not match"):
        catalogue.resolve(stale)


def test_definition_rejects_stale_profile_reference() -> None:
    definition = ssc03_hydraulic_continual_world_definition()
    current = definition.profile_ref("major_idf_revision")
    stale = ContinualWorldProfileRef(
        task_world_id=current.task_world_id,
        profile_id=current.profile_id,
        profile_content_sha256="f" * 64,
    )

    with pytest.raises(ValueError, match="content-pinned profile does not match"):
        definition.load_profile(stale)


def test_definition_rejects_profile_from_another_real_world() -> None:
    definition = ssc03_hydraulic_continual_world_definition()
    current = definition.profile_ref("major_idf_revision")
    foreign = ContinualWorldProfileRef(
        task_world_id=PUMP_STATION_TASK_WORLD_ID,
        profile_id=current.profile_id,
        profile_content_sha256=current.profile_content_sha256,
    )

    with pytest.raises(ValueError, match="belongs to another task world"):
        definition.load_profile(foreign)


def test_catalogue_rejects_unknown_world_and_profile() -> None:
    catalogue = default_continual_world_catalogue()
    definition = catalogue.get(SSC03_HYDRAULIC_CONTINUAL_WORLD_ID)

    with pytest.raises(KeyError, match="unknown continual task world"):
        catalogue.get("unknown-world")
    with pytest.raises(KeyError, match="unknown continual-world profile"):
        definition.profile_ref("unknown-profile")


def test_continual_core_does_not_import_concrete_task_packages() -> None:
    package_root = Path(__file__).parents[3] / "src" / "aec_bench" / "task_world_templates" / "continual"
    forbidden_fragments = (
        "stewardship",
        "lifecycles",
        "hydraulics",
        "meta_harness",
        "cli",
        "harbor",
    )

    imported_modules: list[str] = []
    for path in sorted(package_root.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imported_modules.append(node.module)

    assert not {
        module for module in imported_modules if any(fragment in module.split(".") for fragment in forbidden_fragments)
    }


def test_default_catalogue_registers_pump_and_ssc03_worlds() -> None:
    catalogue = default_continual_world_catalogue()

    assert tuple(reference.task_world_id for reference in catalogue.list_definition_refs()) == (
        SSC03_HYDRAULIC_CONTINUAL_WORLD_ID,
        PUMP_STATION_TASK_WORLD_ID,
    )


@pytest.mark.parametrize(
    ("task_world_id", "profile_id", "expected_type"),
    (
        (SSC03_HYDRAULIC_CONTINUAL_WORLD_ID, "major_idf_revision", Ssc03HydraulicContinualProfile),
        (PUMP_STATION_TASK_WORLD_ID, PUMP_STATION_REFERENCE_SYSTEM_ID, PumpStationContinualProfile),
    ),
)
def test_real_consumers_satisfy_the_same_definition_profile_contract(
    task_world_id: str,
    profile_id: str,
    expected_type: type[object],
) -> None:
    definition = default_continual_world_catalogue().get(task_world_id)
    reference = definition.profile_ref(profile_id)

    loaded = definition.load_profile(reference)

    assert definition.build.task_world_id == task_world_id
    assert loaded.reference == reference
    assert isinstance(loaded.value, expected_type)


def test_pump_definition_loads_the_exact_rs1_profile() -> None:
    definition = pump_station_continual_world_definition()
    reference = definition.profile_ref(PUMP_STATION_REFERENCE_SYSTEM_ID)

    loaded = definition.load_profile(reference)

    assert loaded.reference == reference
    assert isinstance(loaded.value, PumpStationContinualProfile)
    station_binding = loaded.value.reference_system.descriptor["station_data"]
    assert loaded.value.station_package.package_content_id == station_binding["package_content_id"]
    assert isinstance(loaded.value.model, PumpStationCoupledModel)
    assert isinstance(loaded.value.opening_state, PumpStationStewardshipState)
    assert isinstance(loaded.value.opening_state.physical, PumpStationCoupledPhysicalState)
    assert not hasattr(loaded.value.opening_state, "state_version")
    assert (
        loaded.value.opening_state.calendar_seconds == loaded.value.reference_system.opening_state["calendar_seconds"]
    )


def test_ssc03_definition_loads_every_registered_hydraulic_profile() -> None:
    definition = ssc03_hydraulic_continual_world_definition()
    expected_ids = (
        "administrative_no_op",
        "major_idf_revision",
        "outlet_geometry_revision",
        "tailwater_revision",
    )

    assert tuple(profile.profile_id for profile in definition.profiles) == expected_ids
    for profile_id in expected_ids:
        reference = definition.profile_ref(profile_id)
        loaded = definition.load_profile(reference)
        assert loaded.reference == reference
        assert len(reference.profile_content_sha256) == 64
        assert isinstance(loaded.value, Ssc03HydraulicContinualProfile)
        assert loaded.value.reference == reference
        assert loaded.value.profile_id == profile_id


def test_ssc03_loaded_profile_does_not_expose_mutable_execution_inputs() -> None:
    definition = ssc03_hydraulic_continual_world_definition()
    loaded = definition.load_profile(definition.profile_ref("major_idf_revision"))
    assert isinstance(loaded.value, Ssc03HydraulicContinualProfile)

    assert not hasattr(loaded.value, "template")
    assert not hasattr(loaded.value, "variant")
    assert not hasattr(loaded.value, "adapter")
    with pytest.raises(FrozenInstanceError):
        loaded.value.reference = definition.profile_ref("tailwater_revision")  # type: ignore[misc]


def test_ssc03_profile_rejects_package_from_another_registered_profile(tmp_path: Path) -> None:
    definition = ssc03_hydraulic_continual_world_definition()
    major = definition.load_profile(definition.profile_ref("major_idf_revision"))
    tailwater = definition.load_profile(definition.profile_ref("tailwater_revision"))
    assert isinstance(major.value, Ssc03HydraulicContinualProfile)
    assert isinstance(tailwater.value, Ssc03HydraulicContinualProfile)
    tailwater_package = tailwater.value.compile(tmp_path / "tailwater-package")

    with pytest.raises(ValueError, match="package belongs to another continual-world profile"):
        major.value.build_smoke_environment(tailwater_package.package_dir)


def test_ssc03_profile_rejects_stale_definition_implementation(tmp_path: Path) -> None:
    definition = ssc03_hydraulic_continual_world_definition()
    profile_reference = definition.profile_ref("major_idf_revision")
    stale_world_build = WorldBuildRef(
        task_world_id=definition.ref.task_world_id,
        entry_point=definition.ref.entry_point,
        artifact_sha256="f" * 64,
    )
    stale = Ssc03HydraulicContinualProfile(
        reference=profile_reference,
        world_build=stale_world_build,
    )

    with pytest.raises(ValueError, match="definition implementation differs"):
        stale.compile(tmp_path / "package")


def test_ssc03_catalogue_profile_executes_and_verifies_real_lifecycle(tmp_path: Path) -> None:
    catalogue = default_continual_world_catalogue()
    definition = catalogue.get(SSC03_HYDRAULIC_CONTINUAL_WORLD_ID)
    loaded = definition.load_profile(definition.profile_ref("major_idf_revision"))
    assert isinstance(loaded.value, Ssc03HydraulicContinualProfile)
    compiled = loaded.value.compile(tmp_path / "package")
    assert compiled.envelope.world_id == loaded.reference.task_world_id
    assert compiled.envelope.variant_id == loaded.value.profile_id
    assert loaded.value.build_operation_resolver(compiled.package_dir, tmp_path / "run") is not None
    environment = loaded.value.build_smoke_environment(compiled.package_dir)
    assert environment is not None

    run_evidence_lifecycle(
        compiled.package_dir,
        tmp_path / "run",
        episode_environment=environment,
    )
    verification = loaded.value.verify(compiled.package_dir, tmp_path / "run")

    assert verification["passed"] is True
    assert verification["reward"] == 1.0
