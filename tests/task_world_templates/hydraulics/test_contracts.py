# ABOUTME: Tests typed source-state and topology contracts for public hydraulic worlds.
# ABOUTME: Ensures revisions, section hashes, scenarios, and pipe chains fail closed.

from __future__ import annotations

import copy

import pytest
from pydantic import ValidationError

from aec_bench.task_world_templates.hydraulics.contracts import HydraulicSourceState, NetworkSpec
from aec_bench.task_world_templates.hydraulics.worlds.ssc03_detention_network import build_source_state


def test_public_ssc03_source_state_has_two_catchments_and_content_bound_sections() -> None:
    state = build_source_state()

    assert state.world_id == "ssc03.public.detention-network.v1"
    assert [catchment.catchment_id for catchment in state.payload.catchments] == ["CATCH-A", "CATCH-B"]
    assert {scenario.scenario_id for scenario in state.payload.scenarios} == {"design-10yr", "major-100yr"}
    assert {section.section_name for section in state.sections} == {
        "catchments",
        "scenarios",
        "basin",
        "outlet",
        "network",
        "criteria",
    }
    assert all(len(section.content_sha256) == 64 for section in state.sections)


def test_source_state_rejects_section_content_that_no_longer_matches_its_hash() -> None:
    payload = build_source_state().model_dump(mode="json")
    payload["payload"]["network"]["tailwater_elevation_m"] += 0.1

    with pytest.raises(ValidationError, match="section hash does not match"):
        HydraulicSourceState.model_validate(payload)


def test_source_state_rejects_a_broken_pipe_chain() -> None:
    payload = copy.deepcopy(build_source_state().model_dump(mode="json"))
    payload["payload"]["network"]["pipes"][1]["upstream_node_id"] = "UNCONNECTED-PIT"

    with pytest.raises(ValidationError, match="pipe chain"):
        HydraulicSourceState.model_validate(payload)


def test_source_state_rejects_unbounded_scenario_step_count() -> None:
    payload = copy.deepcopy(build_source_state().model_dump(mode="json"))
    payload["payload"]["scenarios"][0]["storm_duration_s"] = 600_000
    payload["payload"]["scenarios"][0]["time_step_s"] = 1

    with pytest.raises(ValidationError, match="time steps"):
        HydraulicSourceState.model_validate(payload)


def test_network_rejects_a_cycle_that_reuses_tailwater_as_an_upstream_pit() -> None:
    network = build_source_state().payload.network.model_dump(mode="json")
    network["pits"] = [
        {"node_id": "PIT-A", "rim_elevation_m": 42.0},
        {"node_id": "PIT-B", "rim_elevation_m": 42.0},
    ]
    network["pipes"][0]["upstream_node_id"] = "PIT-A"
    network["pipes"][0]["downstream_node_id"] = "PIT-B"
    network["pipes"][1]["upstream_node_id"] = "PIT-B"
    network["pipes"][1]["downstream_node_id"] = "PIT-A"
    network["tailwater_node_id"] = "PIT-A"

    with pytest.raises(ValidationError, match="tailwater node must be distinct"):
        NetworkSpec.model_validate(network)
