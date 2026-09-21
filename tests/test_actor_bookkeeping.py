# ABOUTME: Checks task outputs and registered world action schemas for host bookkeeping requirements.
# ABOUTME: Keeps engineering references available and transport identities out of answers.

from __future__ import annotations

from collections.abc import Iterator

from pydantic import JsonValue

from aec_bench.contracts.task_definition import Visibility
from aec_bench.templates.registry import discover_templates
from aec_bench.worlds.generated_catalogue import WORLD_DESCRIPTORS
from aec_bench.worlds.monitoring.dam_seepage.definition import DamSeepageProfile, dam_seepage_world_definition
from aec_bench.worlds.monitoring.dam_seepage.episode_runtime import DamSeepageEpisodeHost
from aec_bench.worlds.stewardship.wastewater_pump_station.actor_interface import pump_station_actor_capabilities
from aec_bench.worlds.stewardship.wastewater_pump_station.episode_runtime import PUMP_STATION_TASK_WORLD_ID

_HOST_FIELDS = {
    "request_id",
    "transport_request_id",
    "session_id",
    "trial_id",
    "attempt_id",
    "decision_id",
    "checkpoint_id",
    "action_id",
    "action_count",
    "world_action_count",
    "visible_source_state_sha256",
    "source_hash",
    "artifact_hash",
    "content_sha256",
}


def _schema_fields(value: JsonValue) -> Iterator[str]:
    if isinstance(value, dict):
        properties = value.get("properties")
        if isinstance(properties, dict):
            yield from properties
        for child in value.values():
            yield from _schema_fields(child)
    elif isinstance(value, list):
        for child in value:
            yield from _schema_fields(child)


def _assert_engineering_fields(fields: set[str]) -> None:
    assert not fields & _HOST_FIELDS
    assert not {field for field in fields if field.endswith("_sha256")}


def test_builtin_task_outputs_do_not_require_host_bookkeeping() -> None:
    templates, diagnostics = discover_templates()
    assert templates
    assert not diagnostics
    for template in templates:
        _assert_engineering_fields(set(template.config.outputs))


def test_registered_world_action_schemas_do_not_require_host_bookkeeping() -> None:
    definition = dam_seepage_world_definition()
    reference = next(
        profile
        for profile in definition.profiles
        if definition.metadata_for(profile.profile_id).visibility == Visibility.PUBLIC
    )
    profile = definition.load_profile(reference).value
    assert isinstance(profile, DamSeepageProfile)
    catalogues = (
        DamSeepageEpisodeHost(profile=profile).capabilities(),
        pump_station_actor_capabilities(task_world_id=PUMP_STATION_TASK_WORLD_ID, temporal_repository_verified=True),
    )
    # A new registered owner must contribute its real actor catalogue to this check.
    assert {catalogue.task_world_id for catalogue in catalogues} == {
        descriptor.task_world_id for descriptor in WORLD_DESCRIPTORS
    }
    for catalogue in catalogues:
        assert catalogue.actions
        for action in catalogue.actions:
            _assert_engineering_fields(set(_schema_fields(action.input_schema)))
