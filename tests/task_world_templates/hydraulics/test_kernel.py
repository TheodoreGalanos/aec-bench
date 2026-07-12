# ABOUTME: Unit-tests the deterministic screening hydraulics used by the SSC-03 mini-world.
# ABOUTME: Anchors equations to hand-calculated values and physical monotonicity checks.

from __future__ import annotations

import pytest

from aec_bench.task_world_templates.hydraulics.contracts import PipeSpec
from aec_bench.task_world_templates.hydraulics.kernel import (
    depth_from_storage_volume,
    orifice_discharge,
    pipe_hydraulics,
    rational_peak_flow,
    storage_volume,
    weir_discharge,
)


def test_rational_peak_flow_matches_hand_calculation() -> None:
    assert rational_peak_flow(runoff_coefficient=0.8, rainfall_intensity_mm_h=90.0, area_ha=2.0) == pytest.approx(0.4)


def test_stage_storage_curve_and_inverse_match_hand_calculation() -> None:
    volume = storage_volume(
        depth_m=1.0,
        maximum_depth_m=2.0,
        bottom_area_m2=100.0,
        top_area_m2=200.0,
    )

    assert volume == pytest.approx(125.0)
    assert depth_from_storage_volume(
        volume_m3=volume,
        maximum_depth_m=2.0,
        bottom_area_m2=100.0,
        top_area_m2=200.0,
    ) == pytest.approx(1.0)


def test_orifice_and_weir_discharge_match_hand_calculations() -> None:
    assert orifice_discharge(
        upstream_level_m=42.0,
        downstream_level_m=41.0,
        diameter_m=0.4,
        discharge_coefficient=0.6,
        centre_elevation_m=40.5,
    ) == pytest.approx(0.334, abs=0.001)
    assert weir_discharge(
        upstream_level_m=41.8,
        downstream_level_m=41.0,
        crest_elevation_m=41.5,
        length_m=2.0,
        discharge_coefficient=0.62,
    ) == pytest.approx(0.601, abs=0.001)


def test_weir_discharge_reduces_under_tailwater_and_stops_at_drowned_headwater() -> None:
    free = weir_discharge(
        upstream_level_m=41.8,
        downstream_level_m=41.0,
        crest_elevation_m=41.5,
        length_m=2.0,
        discharge_coefficient=0.62,
    )
    submerged = weir_discharge(
        upstream_level_m=41.8,
        downstream_level_m=41.7,
        crest_elevation_m=41.5,
        length_m=2.0,
        discharge_coefficient=0.62,
    )
    drowned = weir_discharge(
        upstream_level_m=41.8,
        downstream_level_m=41.8,
        crest_elevation_m=41.5,
        length_m=2.0,
        discharge_coefficient=0.62,
    )

    assert 0.0 < submerged < free
    assert drowned == 0.0


def test_pipe_hydraulics_matches_independent_full_pipe_check() -> None:
    result = pipe_hydraulics(
        flow_m3_s=0.5,
        pipe=PipeSpec(
            pipe_id="PIPE-TEST",
            upstream_node_id="PIT-A",
            downstream_node_id="OUTFALL",
            diameter_m=0.75,
            length_m=20.0,
            slope_m_per_m=0.005,
            mannings_n=0.013,
            minor_loss_coefficient=0.5,
        ),
    )

    assert result.velocity_m_s == pytest.approx(1.132, abs=0.001)
    assert result.friction_loss_m == pytest.approx(0.041, abs=0.001)
    assert result.minor_loss_m == pytest.approx(0.033, abs=0.001)
    assert result.capacity_m3_s == pytest.approx(0.786, abs=0.002)


def test_discharge_increases_with_available_head() -> None:
    low = orifice_discharge(
        upstream_level_m=41.2,
        downstream_level_m=41.0,
        diameter_m=0.4,
        discharge_coefficient=0.6,
        centre_elevation_m=40.5,
    )
    high = orifice_discharge(
        upstream_level_m=42.0,
        downstream_level_m=41.0,
        diameter_m=0.4,
        discharge_coefficient=0.6,
        centre_elevation_m=40.5,
    )

    assert 0.0 < low < high
