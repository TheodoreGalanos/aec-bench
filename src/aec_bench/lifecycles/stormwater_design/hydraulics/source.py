# ABOUTME: Defines the public two-catchment detention and outlet calculation source.
# ABOUTME: Separates its metric synthetic inputs from the EPA Example 3 reference packet.

from __future__ import annotations

from aec_bench.lifecycles.stormwater_design.hydraulics.models import (
    BasinSpec,
    CatchmentSpec,
    HydraulicCriteriaSpec,
    HydraulicReferenceSpec,
    HydraulicSourcePayload,
    HydraulicSourceState,
    NetworkSpec,
    OrificeSpec,
    OutletSpec,
    PipeSpec,
    PitSpec,
    RainfallScenarioSpec,
    WeirSpec,
    build_source_state_contract,
)

SOURCE_ID = "stormwater-detention-network"


def build_source_state() -> HydraulicSourceState:
    """Return the canonical source for the stormwater hydraulic review."""
    payload = HydraulicSourcePayload(
        catchments=(
            CatchmentSpec(catchment_id="CATCH-A", area_ha=3.6, runoff_coefficient=0.72),
            CatchmentSpec(catchment_id="CATCH-B", area_ha=2.8, runoff_coefficient=0.68),
        ),
        scenarios=(
            RainfallScenarioSpec(
                scenario_id="design-10yr",
                title="Synthetic 10-year storage event",
                role="design",
                rainfall_intensity_mm_h=78.0,
                climate_factor=1.1,
                storm_duration_s=1800,
                time_step_s=60,
            ),
            RainfallScenarioSpec(
                scenario_id="major-100yr",
                title="Synthetic 100-year emergency event",
                role="major",
                rainfall_intensity_mm_h=105.0,
                climate_factor=1.1,
                storm_duration_s=7200,
                time_step_s=60,
            ),
        ),
        basin=BasinSpec(
            basin_id="DET-03-BASIN-01",
            bottom_elevation_m=40.0,
            crest_elevation_m=42.2,
            bottom_area_m2=450.0,
            top_area_m2=700.0,
            initial_depth_m=0.0,
        ),
        outlet=OutletSpec(
            orifice=OrificeSpec(
                outlet_id="OUT-03-ORIFICE-01",
                diameter_m=0.42,
                discharge_coefficient=0.61,
                centre_elevation_m=40.35,
            ),
            emergency_weir=WeirSpec(
                outlet_id="OUT-03-WEIR-01",
                crest_elevation_m=41.6,
                length_m=4.2,
                discharge_coefficient=0.62,
            ),
        ),
        network=NetworkSpec(
            pits=(
                PitSpec(node_id="PIT-OUTLET", rim_elevation_m=42.3),
                PitSpec(node_id="PIT-DOWNSTREAM", rim_elevation_m=42.0),
            ),
            pipes=(
                PipeSpec(
                    pipe_id="PIPE-OUT-01",
                    upstream_node_id="PIT-OUTLET",
                    downstream_node_id="PIT-DOWNSTREAM",
                    diameter_m=0.9,
                    length_m=32.0,
                    slope_m_per_m=0.008,
                    mannings_n=0.013,
                    minor_loss_coefficient=0.5,
                ),
                PipeSpec(
                    pipe_id="PIPE-OUT-02",
                    upstream_node_id="PIT-DOWNSTREAM",
                    downstream_node_id="OUTFALL",
                    diameter_m=1.05,
                    length_m=48.0,
                    slope_m_per_m=0.006,
                    mannings_n=0.013,
                    minor_loss_coefficient=0.7,
                ),
            ),
            tailwater_node_id="OUTFALL",
            tailwater_elevation_m=40.6,
        ),
        criteria=HydraulicCriteriaSpec(
            maximum_design_release_m3_s=0.42,
            minimum_major_weir_flow_m3_s=0.05,
            maximum_pipe_velocity_m_s=3.0,
            minimum_hgl_clearance_m=0.15,
            minimum_freeboard_m=0.3,
            maximum_continuity_error_m3=0.001,
            flow_tolerance_m3_s=0.000001,
            level_tolerance_m=0.000001,
            velocity_tolerance_m_s=0.000001,
        ),
    )
    return build_source_state_contract(
        source_id=SOURCE_ID,
        title="Stormwater Detention and Outlet Screening",
        description=(
            "A deterministic metric calculation source with two catchments, level-pool detention, "
            "an orifice, emergency weir, two-pipe outlet chain, and fixed tailwater."
        ),
        claim_boundary=(
            "This is a benchmark-owned screening calculation, not SWMM-equivalent simulation, "
            "authority approval, standards compliance, or project design evidence."
        ),
        reference=HydraulicReferenceSpec(
            source_pack_id="swmm_example3_detention_source_pack",
            source_commit="1a46f13fe44185263853ef78343e540a9895f23a",
            role=(
                "Public provenance and manual-target reference only; its seven-subcatchment "
                "imperial SWMM example is not represented as this two-catchment metric calculation."
            ),
        ),
        payload=payload,
        section_revisions={
            "catchments": ("SYN-STORMWATER-CATCHMENTS", "Rev A"),
            "scenarios": ("SYN-STORMWATER-RAINFALL", "Rev A"),
            "basin": ("SYN-STORMWATER-DETENTION", "Rev A"),
            "outlet": ("SYN-STORMWATER-OUTLETS", "Rev A"),
            "network": ("SYN-STORMWATER-NETWORK", "Rev A"),
            "criteria": ("SYN-STORMWATER-CRITERIA", "Rev A"),
        },
    )
