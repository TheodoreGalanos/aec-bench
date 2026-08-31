# ABOUTME: Tests explicit world-owner descriptors and the generated catalogue composition.
# ABOUTME: Protects stable order, freshness, provider-free import, and runtime resolution.

from __future__ import annotations

import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from aec_bench.worlds.catalogue import WorldCatalogue, _catalogue
from aec_bench.worlds.generated_catalogue import WORLD_DESCRIPTORS, load_world_definitions
from aec_bench.worlds.monitoring.dam_seepage import WORLD_DESCRIPTOR as DAM_SEEPAGE_DESCRIPTOR
from aec_bench.worlds.stewardship.wastewater_pump_station import WORLD_DESCRIPTOR as PUMP_STATION_DESCRIPTOR
from scripts.generate_world_catalogue import OWNER_IMPORTS, render_catalogue


def test_each_concrete_world_owner_exposes_one_descriptor() -> None:
    descriptors = (DAM_SEEPAGE_DESCRIPTOR, PUMP_STATION_DESCRIPTOR)

    assert descriptors == WORLD_DESCRIPTORS
    assert tuple(descriptor.task_world_id for descriptor in descriptors) == tuple(
        definition.build.task_world_id for definition in load_world_definitions()
    )


def test_generated_catalogue_matches_generator_output() -> None:
    generated_path = Path(__file__).parents[2] / "src" / "aec_bench" / "worlds" / "generated_catalogue.py"

    assert generated_path.read_text(encoding="utf-8") == render_catalogue()


def test_generated_catalogue_has_stable_owner_order() -> None:
    assert tuple(descriptor.task_world_id for descriptor in WORLD_DESCRIPTORS) == tuple(
        sorted(descriptor.task_world_id for descriptor in WORLD_DESCRIPTORS)
    )
    assert tuple(definition.build.task_world_id for definition in _catalogue().definitions) == tuple(
        sorted(definition.build.task_world_id for definition in _catalogue().definitions)
    )


def test_generator_supports_more_than_two_world_owners_and_sorts_them() -> None:
    third_owner = (
        "asset/third-world",
        "aec_bench.worlds.asset.third_world",
        "WORLD_DESCRIPTOR",
        "THIRD_WORLD_DESCRIPTOR",
    )

    rendered = render_catalogue((*OWNER_IMPORTS, third_owner))

    assert "from aec_bench.worlds.asset.third_world import WORLD_DESCRIPTOR as THIRD_WORLD_DESCRIPTOR" in rendered
    assert rendered.index("THIRD_WORLD_DESCRIPTOR,") < rendered.index("DAM_SEEPAGE_DESCRIPTOR,")


def test_catalogue_rejects_duplicate_entity_identity() -> None:
    definition = _catalogue().definitions[0]
    alternate_task_world_id = "duplicate-task-world"
    duplicate_identity = replace(
        definition,
        build=replace(definition.build, task_world_id=alternate_task_world_id),
        profiles=tuple(replace(profile, task_world_id=alternate_task_world_id) for profile in definition.profiles),
    )

    with pytest.raises(ValueError, match="entity UUIDs must be unique"):
        WorldCatalogue(definitions=(definition, duplicate_identity))


def test_world_catalogue_import_does_not_load_optional_providers() -> None:
    source_root = Path(__file__).parents[2] / "src"
    probe = (
        "import sys; import aec_bench.worlds.catalogue; "
        "print(sorted(name for name in sys.modules if name.split('.')[0] in "
        "{'boto3', 'botocore', 'harbor', 'prime', 'verifiers', 'pydantic_ai', 'httpx'}))"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=source_root.parents[1],
        env={"PYTHONPATH": str(source_root)},
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.strip() == "[]"
