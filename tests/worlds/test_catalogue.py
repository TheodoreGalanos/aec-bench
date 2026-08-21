# ABOUTME: Tests the task-neutral catalogue for registered Interactive Worlds.
# ABOUTME: Proves exact pump-world build and profile dispatch without lifecycle registrations.

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from aec_bench.contracts.interactive_world import InteractiveWorldProfileRef, WorldBuildRef
from aec_bench.worlds.catalogue import WorldCatalogue, _catalogue
from aec_bench.worlds.monitoring.dam_seepage.definition import (
    DamSeepageProfile,
    dam_seepage_world_definition,
)
from aec_bench.worlds.monitoring.dam_seepage.world import DAM_SEEPAGE_TASK_WORLD_ID
from aec_bench.worlds.runtime.definition import source_tree_world_build
from aec_bench.worlds.stewardship.wastewater_pump_station.continual_definition import (
    PumpStationContinualProfile,
    pump_station_continual_world_definition,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.episode_runtime import (
    PUMP_STATION_TASK_WORLD_ID,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.physical_models import (
    PumpStationCoupledModel,
    PumpStationCoupledPhysicalState,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.reference_system import (
    PUMP_STATION_REFERENCE_SYSTEM_ID,
    PUMP_STATION_REFERENCE_SYSTEM_RS2_ID,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.stewardship_models import (
    PumpStationStewardshipState,
)


def test_catalogue_rejects_duplicate_world_id() -> None:
    definition = pump_station_continual_world_definition()

    with pytest.raises(ValueError, match="task world ids must be unique"):
        WorldCatalogue(definitions=(definition, definition))


def test_catalogue_resolves_exact_content_pinned_definition() -> None:
    catalogue = _catalogue()
    definition = catalogue.get(PUMP_STATION_TASK_WORLD_ID)

    assert catalogue.resolve(definition.ref) is definition


def test_catalogue_rejects_stale_definition_reference() -> None:
    catalogue = _catalogue()
    definition = catalogue.get(PUMP_STATION_TASK_WORLD_ID)
    stale = WorldBuildRef(
        task_world_id=definition.ref.task_world_id,
        entry_point=definition.ref.entry_point,
        artifact_sha256="f" * 64,
    )

    with pytest.raises(ValueError, match="world build does not match"):
        catalogue.resolve(stale)


def test_world_build_identity_changes_with_executable_source_content(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime_root = Path(__file__).parents[2] / "src" / "aec_bench" / "worlds" / "runtime"
    definition_path = runtime_root / "definition.py"
    baseline = source_tree_world_build(
        task_world_id="identity-test-world",
        entry_point="identity:test",
        roots=(definition_path,),
    )

    original_read_bytes = Path.read_bytes

    def read_changed_source(path: Path) -> bytes:
        content = original_read_bytes(path)
        return content + b"\n# changed executable rule\n" if path == definition_path else content

    monkeypatch.setattr(Path, "read_bytes", read_changed_source)
    changed = source_tree_world_build(
        task_world_id="identity-test-world",
        entry_point="identity:test",
        roots=(definition_path,),
    )

    assert baseline.artifact_sha256 != changed.artifact_sha256


def test_definition_rejects_stale_profile_reference() -> None:
    definition = pump_station_continual_world_definition()
    current = definition.profile_ref(PUMP_STATION_REFERENCE_SYSTEM_ID)
    stale = InteractiveWorldProfileRef(
        task_world_id=current.task_world_id,
        profile_id=current.profile_id,
        profile_content_sha256="f" * 64,
    )

    with pytest.raises(ValueError, match="content-pinned profile does not match"):
        definition.load_profile(stale)


def test_definition_rejects_profile_from_another_world() -> None:
    definition = pump_station_continual_world_definition()
    current = definition.profile_ref(PUMP_STATION_REFERENCE_SYSTEM_ID)
    foreign = InteractiveWorldProfileRef(
        task_world_id="another-world",
        profile_id=current.profile_id,
        profile_content_sha256=current.profile_content_sha256,
    )

    with pytest.raises(ValueError, match="belongs to another task world"):
        definition.load_profile(foreign)


def test_catalogue_rejects_unknown_world_and_profile() -> None:
    catalogue = _catalogue()
    definition = catalogue.get(PUMP_STATION_TASK_WORLD_ID)

    with pytest.raises(KeyError, match="unknown Interactive World"):
        catalogue.get("unknown-world")
    with pytest.raises(KeyError, match="unknown Interactive World profile"):
        definition.profile_ref("unknown-profile")


def test_interactive_world_core_does_not_import_concrete_world_packages() -> None:
    package_root = Path(__file__).parents[2] / "src" / "aec_bench" / "worlds" / "runtime"
    forbidden_fragments = ("stewardship", "lifecycles", "hydraulics", "cli", "harbor")

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


def test_default_catalogue_registers_current_worlds() -> None:
    catalogue = _catalogue()

    assert tuple(reference.task_world_id for reference in catalogue.list_definition_refs()) == (
        DAM_SEEPAGE_TASK_WORLD_ID,
        PUMP_STATION_TASK_WORLD_ID,
    )


def test_dam_seepage_definition_loads_content_pinned_profile() -> None:
    definition = dam_seepage_world_definition()
    reference = definition.profiles[0]

    loaded = definition.load_profile(reference)

    assert loaded.reference == reference
    assert isinstance(loaded.value, DamSeepageProfile)
    assert loaded.value.scenario.task_world_id == DAM_SEEPAGE_TASK_WORLD_ID
    assert loaded.value.opening_state.scenario is loaded.value.scenario


@pytest.mark.parametrize(
    "profile_id",
    (PUMP_STATION_REFERENCE_SYSTEM_ID, PUMP_STATION_REFERENCE_SYSTEM_RS2_ID),
)
def test_pump_definition_loads_each_content_pinned_profile(profile_id: str) -> None:
    definition = pump_station_continual_world_definition()
    reference = definition.profile_ref(profile_id)

    loaded = definition.load_profile(reference)

    assert loaded.reference == reference
    assert isinstance(loaded.value, PumpStationContinualProfile)
    assert reference.profile_content_sha256 == loaded.value.reference_system.profile_content_id
    station_binding = loaded.value.reference_system.descriptor["station_data"]
    assert loaded.value.station_package.package_content_id == station_binding["package_content_id"]
    assert isinstance(loaded.value.model, PumpStationCoupledModel)
    assert isinstance(loaded.value.opening_state, PumpStationStewardshipState)
    assert isinstance(loaded.value.opening_state.physical, PumpStationCoupledPhysicalState)
    assert not hasattr(loaded.value.opening_state, "state_version")
    assert (
        loaded.value.opening_state.calendar_seconds == loaded.value.reference_system.opening_state["calendar_seconds"]
    )
