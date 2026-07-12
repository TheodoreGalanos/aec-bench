# ABOUTME: Deterministic screening calculations for public hydraulic mini-worlds.
# ABOUTME: Implements runoff, storage, outlet, pipe, and HGL primitives without SWMM claims.

from __future__ import annotations

import math
from dataclasses import dataclass

from aec_bench.task_world_templates.hydraulics.contracts import (
    HydraulicEngineIdentity,
    HydraulicRunResult,
    HydraulicSourceState,
    HydraulicTimeSeries,
    HydraulicTimeStep,
    NetworkSpec,
    PipeSpec,
)

_GRAVITY_M_S2 = 9.81


@dataclass(frozen=True)
class PipeHydraulicResult:
    velocity_m_s: float
    friction_loss_m: float
    minor_loss_m: float
    capacity_m3_s: float


@dataclass(frozen=True)
class OutletHydraulicState:
    orifice_flow_m3_s: float
    weir_flow_m3_s: float
    node_hgl_m: dict[str, float]
    pipe_hydraulics: dict[str, PipeHydraulicResult]
    converged: bool


def _positive(name: str, value: float) -> None:
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError(f"{name} must be finite and > 0")


def rational_peak_flow(*, runoff_coefficient: float, rainfall_intensity_mm_h: float, area_ha: float) -> float:
    """Return Rational Method peak runoff in cubic metres per second."""
    if not 0.0 <= runoff_coefficient <= 1.0:
        raise ValueError("runoff_coefficient must be between 0 and 1")
    _positive("rainfall_intensity_mm_h", rainfall_intensity_mm_h)
    _positive("area_ha", area_ha)
    return runoff_coefficient * rainfall_intensity_mm_h * area_ha / 360.0


def storage_volume(
    *,
    depth_m: float,
    maximum_depth_m: float,
    bottom_area_m2: float,
    top_area_m2: float,
) -> float:
    """Return volume below a depth for a basin whose plan area changes linearly."""
    _positive("maximum_depth_m", maximum_depth_m)
    _positive("bottom_area_m2", bottom_area_m2)
    _positive("top_area_m2", top_area_m2)
    if top_area_m2 < bottom_area_m2:
        raise ValueError("top_area_m2 must be >= bottom_area_m2")
    if not math.isfinite(depth_m) or not 0.0 <= depth_m <= maximum_depth_m:
        raise ValueError("depth_m must be finite and within the basin")
    area_gradient = (top_area_m2 - bottom_area_m2) / maximum_depth_m
    return bottom_area_m2 * depth_m + 0.5 * area_gradient * depth_m**2


def depth_from_storage_volume(
    *,
    volume_m3: float,
    maximum_depth_m: float,
    bottom_area_m2: float,
    top_area_m2: float,
) -> float:
    """Invert the linear-area stage-storage relationship."""
    if not math.isfinite(volume_m3) or volume_m3 < 0.0:
        raise ValueError("volume_m3 must be finite and >= 0")
    maximum_volume = storage_volume(
        depth_m=maximum_depth_m,
        maximum_depth_m=maximum_depth_m,
        bottom_area_m2=bottom_area_m2,
        top_area_m2=top_area_m2,
    )
    if volume_m3 > maximum_volume:
        raise ValueError("volume_m3 exceeds basin storage")
    area_gradient = (top_area_m2 - bottom_area_m2) / maximum_depth_m
    if area_gradient == 0.0:
        return volume_m3 / bottom_area_m2
    discriminant = bottom_area_m2**2 + 2.0 * area_gradient * volume_m3
    return (-bottom_area_m2 + math.sqrt(discriminant)) / area_gradient


def orifice_discharge(
    *,
    upstream_level_m: float,
    downstream_level_m: float,
    diameter_m: float,
    discharge_coefficient: float,
    centre_elevation_m: float,
) -> float:
    """Return circular-orifice discharge using the effective differential head."""
    _positive("diameter_m", diameter_m)
    if not 0.0 < discharge_coefficient <= 1.0:
        raise ValueError("discharge_coefficient must be > 0 and <= 1")
    head_m = upstream_level_m - max(downstream_level_m, centre_elevation_m)
    if head_m <= 0.0:
        return 0.0
    area_m2 = math.pi * diameter_m**2 / 4.0
    return discharge_coefficient * area_m2 * math.sqrt(2.0 * _GRAVITY_M_S2 * head_m)


def weir_discharge(
    *,
    upstream_level_m: float,
    downstream_level_m: float,
    crest_elevation_m: float,
    length_m: float,
    discharge_coefficient: float,
) -> float:
    """Return tailwater-reduced sharp-crested rectangular-weir discharge."""
    _positive("length_m", length_m)
    if not 0.0 < discharge_coefficient <= 1.0:
        raise ValueError("discharge_coefficient must be > 0 and <= 1")
    control_level_m = max(crest_elevation_m, downstream_level_m)
    head_m = upstream_level_m - control_level_m
    if head_m <= 0.0:
        return 0.0
    return (2.0 / 3.0) * discharge_coefficient * math.sqrt(2.0 * _GRAVITY_M_S2) * length_m * math.pow(head_m, 1.5)


def pipe_hydraulics(*, flow_m3_s: float, pipe: PipeSpec) -> PipeHydraulicResult:
    """Return full-pipe velocity, losses, and Manning capacity for one reach."""
    if not math.isfinite(flow_m3_s) or flow_m3_s < 0.0:
        raise ValueError("flow_m3_s must be finite and >= 0")
    area_m2 = math.pi * pipe.diameter_m**2 / 4.0
    hydraulic_radius_m = pipe.diameter_m / 4.0
    velocity_m_s = flow_m3_s / area_m2
    friction_slope = (velocity_m_s * pipe.mannings_n / hydraulic_radius_m ** (2.0 / 3.0)) ** 2
    friction_loss_m = friction_slope * pipe.length_m
    minor_loss_m = pipe.minor_loss_coefficient * velocity_m_s**2 / (2.0 * _GRAVITY_M_S2)
    capacity_m3_s = area_m2 * hydraulic_radius_m ** (2.0 / 3.0) * math.sqrt(pipe.slope_m_per_m) / pipe.mannings_n
    return PipeHydraulicResult(
        velocity_m_s=velocity_m_s,
        friction_loss_m=friction_loss_m,
        minor_loss_m=minor_loss_m,
        capacity_m3_s=capacity_m3_s,
    )


def _triangular_inflow_fraction(time_s: float, duration_s: int) -> float:
    midpoint_s = duration_s / 2.0
    if time_s <= 0.0 or time_s >= duration_s:
        return 0.0
    if time_s <= midpoint_s:
        return time_s / midpoint_s
    return (duration_s - time_s) / midpoint_s


def _network_hgl(
    *,
    flow_m3_s: float,
    network: NetworkSpec,
) -> tuple[dict[str, float], dict[str, PipeHydraulicResult]]:
    node_hgl = {network.tailwater_node_id: network.tailwater_elevation_m}
    pipe_results: dict[str, PipeHydraulicResult] = {}
    downstream_hgl = network.tailwater_elevation_m
    for pipe in reversed(network.pipes):
        result = pipe_hydraulics(flow_m3_s=flow_m3_s, pipe=pipe)
        pipe_results[pipe.pipe_id] = result
        upstream_hgl = downstream_hgl + result.friction_loss_m + result.minor_loss_m
        node_hgl[pipe.upstream_node_id] = upstream_hgl
        downstream_hgl = upstream_hgl
    return node_hgl, pipe_results


def _solve_outlet(*, water_surface_elevation_m: float, source: HydraulicSourceState) -> OutletHydraulicState:
    payload = source.payload
    downstream_level_m = payload.network.tailwater_elevation_m
    converged = False
    orifice_flow_m3_s = 0.0
    weir_flow_m3_s = 0.0
    node_hgl_m: dict[str, float] = {}
    pipe_results: dict[str, PipeHydraulicResult] = {}
    upstream_node_id = payload.network.pipes[0].upstream_node_id

    for _iteration in range(60):
        orifice_flow_m3_s = orifice_discharge(
            upstream_level_m=water_surface_elevation_m,
            downstream_level_m=downstream_level_m,
            diameter_m=payload.outlet.orifice.diameter_m,
            discharge_coefficient=payload.outlet.orifice.discharge_coefficient,
            centre_elevation_m=payload.outlet.orifice.centre_elevation_m,
        )
        weir_flow_m3_s = weir_discharge(
            upstream_level_m=water_surface_elevation_m,
            downstream_level_m=downstream_level_m,
            crest_elevation_m=payload.outlet.emergency_weir.crest_elevation_m,
            length_m=payload.outlet.emergency_weir.length_m,
            discharge_coefficient=payload.outlet.emergency_weir.discharge_coefficient,
        )
        node_hgl_m, pipe_results = _network_hgl(
            flow_m3_s=orifice_flow_m3_s + weir_flow_m3_s,
            network=payload.network,
        )
        next_downstream_level_m = node_hgl_m[upstream_node_id]
        if abs(next_downstream_level_m - downstream_level_m) <= 1e-10:
            converged = True
            break
        downstream_level_m = (downstream_level_m + next_downstream_level_m) / 2.0

    return OutletHydraulicState(
        orifice_flow_m3_s=orifice_flow_m3_s,
        weir_flow_m3_s=weir_flow_m3_s,
        node_hgl_m=node_hgl_m,
        pipe_hydraulics=pipe_results,
        converged=converged,
    )


def _rounded(value: float, digits: int = 6) -> float:
    rounded = round(value, digits)
    return 0.0 if rounded == -0.0 else rounded


def simulate_hydraulic_world(
    *,
    source: HydraulicSourceState,
    scenario_id: str,
    run_id: str,
    engine: HydraulicEngineIdentity,
    source_state_sha256: str,
    calculation_input_sha256: str,
) -> tuple[HydraulicRunResult, HydraulicTimeSeries]:
    """Run one fixed-step level-pool scenario and return canonical evidence models."""
    try:
        scenario = next(item for item in source.payload.scenarios if item.scenario_id == scenario_id)
    except StopIteration as exc:
        known = ", ".join(item.scenario_id for item in source.payload.scenarios)
        raise ValueError(f"unknown hydraulic scenario {scenario_id!r}; expected one of: {known}") from exc

    payload = source.payload
    basin = payload.basin
    criteria = payload.criteria
    adjusted_intensity = scenario.rainfall_intensity_mm_h * scenario.climate_factor
    catchment_peaks = {
        catchment.catchment_id: rational_peak_flow(
            runoff_coefficient=catchment.runoff_coefficient,
            rainfall_intensity_mm_h=adjusted_intensity,
            area_ha=catchment.area_ha,
        )
        for catchment in payload.catchments
    }
    peak_total_inflow = sum(catchment_peaks.values())
    maximum_storage = storage_volume(
        depth_m=basin.maximum_depth_m,
        maximum_depth_m=basin.maximum_depth_m,
        bottom_area_m2=basin.bottom_area_m2,
        top_area_m2=basin.top_area_m2,
    )
    current_storage = storage_volume(
        depth_m=basin.initial_depth_m,
        maximum_depth_m=basin.maximum_depth_m,
        bottom_area_m2=basin.bottom_area_m2,
        top_area_m2=basin.top_area_m2,
    )
    initial_storage = current_storage
    cumulative_inflow_m3 = 0.0
    cumulative_outflow_m3 = 0.0
    peak_orifice = 0.0
    peak_weir = 0.0
    peak_structured_outflow = 0.0
    peak_total_outflow = 0.0
    peak_spill = 0.0
    maximum_observed_storage = current_storage
    maximum_water_surface = basin.bottom_elevation_m + basin.initial_depth_m
    maximum_pipe_velocity = {pipe.pipe_id: 0.0 for pipe in payload.network.pipes}
    pipe_capacity = {
        pipe.pipe_id: pipe_hydraulics(flow_m3_s=0.0, pipe=pipe).capacity_m3_s for pipe in payload.network.pipes
    }
    maximum_node_hgl = {pit.node_id: payload.network.tailwater_elevation_m for pit in payload.network.pits} | {
        payload.network.tailwater_node_id: payload.network.tailwater_elevation_m
    }
    steps: list[HydraulicTimeStep] = []
    all_converged = True

    step_count = scenario.storm_duration_s // scenario.time_step_s
    for step_index in range(step_count):
        midpoint_s = step_index * scenario.time_step_s + scenario.time_step_s / 2.0
        total_inflow = peak_total_inflow * _triangular_inflow_fraction(midpoint_s, scenario.storm_duration_s)
        depth_before = depth_from_storage_volume(
            volume_m3=current_storage,
            maximum_depth_m=basin.maximum_depth_m,
            bottom_area_m2=basin.bottom_area_m2,
            top_area_m2=basin.top_area_m2,
        )
        water_surface_before = basin.bottom_elevation_m + depth_before
        outlet = _solve_outlet(water_surface_elevation_m=water_surface_before, source=source)
        structured_outflow = outlet.orifice_flow_m3_s + outlet.weir_flow_m3_s
        available_outflow = total_inflow + current_storage / scenario.time_step_s
        if structured_outflow > available_outflow:
            scale = available_outflow / structured_outflow if structured_outflow > 0.0 else 0.0
            orifice_flow = outlet.orifice_flow_m3_s * scale
            weir_flow = outlet.weir_flow_m3_s * scale
            structured_outflow = available_outflow
            node_hgl, pipe_results = _network_hgl(flow_m3_s=structured_outflow, network=payload.network)
        else:
            orifice_flow = outlet.orifice_flow_m3_s
            weir_flow = outlet.weir_flow_m3_s
            node_hgl = outlet.node_hgl_m
            pipe_results = outlet.pipe_hydraulics

        prospective_storage = current_storage + (total_inflow - structured_outflow) * scenario.time_step_s
        spill_flow = 0.0
        if prospective_storage > maximum_storage:
            spill_flow = (prospective_storage - maximum_storage) / scenario.time_step_s
            next_storage = maximum_storage
        else:
            next_storage = max(0.0, prospective_storage)
        total_outflow = structured_outflow + spill_flow
        cumulative_inflow_m3 += total_inflow * scenario.time_step_s
        cumulative_outflow_m3 += total_outflow * scenario.time_step_s
        current_storage = next_storage
        depth_after = depth_from_storage_volume(
            volume_m3=current_storage,
            maximum_depth_m=basin.maximum_depth_m,
            bottom_area_m2=basin.bottom_area_m2,
            top_area_m2=basin.top_area_m2,
        )
        water_surface_after = basin.bottom_elevation_m + depth_after

        peak_orifice = max(peak_orifice, orifice_flow)
        peak_weir = max(peak_weir, weir_flow)
        peak_structured_outflow = max(peak_structured_outflow, structured_outflow)
        peak_total_outflow = max(peak_total_outflow, total_outflow)
        peak_spill = max(peak_spill, spill_flow)
        maximum_observed_storage = max(maximum_observed_storage, current_storage)
        maximum_water_surface = max(maximum_water_surface, water_surface_after)
        all_converged = all_converged and outlet.converged
        for pipe_id, pipe_result in pipe_results.items():
            maximum_pipe_velocity[pipe_id] = max(maximum_pipe_velocity[pipe_id], pipe_result.velocity_m_s)
        for node_id, hgl_m in node_hgl.items():
            maximum_node_hgl[node_id] = max(maximum_node_hgl[node_id], hgl_m)

        steps.append(
            HydraulicTimeStep(
                time_s=(step_index + 1) * scenario.time_step_s,
                total_inflow_m3_s=_rounded(total_inflow),
                orifice_flow_m3_s=_rounded(orifice_flow),
                weir_flow_m3_s=_rounded(weir_flow),
                uncontrolled_spill_m3_s=_rounded(spill_flow),
                total_outflow_m3_s=_rounded(total_outflow),
                storage_m3=_rounded(current_storage),
                water_depth_m=_rounded(depth_after),
                water_surface_elevation_m=_rounded(water_surface_after),
                node_hgl_m={key: _rounded(value) for key, value in sorted(node_hgl.items())},
                pipe_velocity_m_s={key: _rounded(value.velocity_m_s) for key, value in sorted(pipe_results.items())},
                pipe_capacity_m3_s={key: _rounded(value.capacity_m3_s) for key, value in sorted(pipe_results.items())},
                outlet_converged=outlet.converged,
            )
        )

    continuity_error = initial_storage + cumulative_inflow_m3 - cumulative_outflow_m3 - current_storage
    freeboard = basin.crest_elevation_m - maximum_water_surface
    pit_rims = {pit.node_id: pit.rim_elevation_m for pit in payload.network.pits}
    hgl_clearances = {node_id: pit_rims[node_id] - maximum_node_hgl[node_id] for node_id in pit_rims}
    minimum_hgl_clearance = min(hgl_clearances.values())
    canonical_peak_total_inflow = _rounded(peak_total_inflow)
    canonical_peak_orifice = _rounded(peak_orifice)
    canonical_peak_weir = _rounded(peak_weir)
    canonical_peak_structured_outflow = _rounded(peak_structured_outflow)
    canonical_peak_total_outflow = _rounded(peak_total_outflow)
    canonical_peak_spill = _rounded(peak_spill)
    canonical_maximum_storage = _rounded(maximum_observed_storage)
    canonical_maximum_water_surface = _rounded(maximum_water_surface)
    canonical_freeboard = _rounded(freeboard)
    canonical_maximum_pipe_velocity = {key: _rounded(value) for key, value in sorted(maximum_pipe_velocity.items())}
    canonical_pipe_capacity = {key: _rounded(value) for key, value in sorted(pipe_capacity.items())}
    canonical_maximum_node_hgl = {key: _rounded(value) for key, value in sorted(maximum_node_hgl.items())}
    canonical_minimum_hgl_clearance = _rounded(minimum_hgl_clearance)
    canonical_continuity_error = _rounded(continuity_error)
    criteria_results = {
        "continuity": abs(canonical_continuity_error) <= criteria.maximum_continuity_error_m3,
        "freeboard": canonical_freeboard + criteria.level_tolerance_m >= criteria.minimum_freeboard_m,
        "hgl_clearance": canonical_minimum_hgl_clearance + criteria.level_tolerance_m
        >= criteria.minimum_hgl_clearance_m,
        "outlet_convergence": all_converged,
        "pipe_capacity": all(
            capacity + criteria.flow_tolerance_m3_s >= canonical_peak_structured_outflow
            for capacity in canonical_pipe_capacity.values()
        ),
        "pipe_velocity": all(
            velocity <= criteria.maximum_pipe_velocity_m_s + criteria.velocity_tolerance_m_s
            for velocity in canonical_maximum_pipe_velocity.values()
        ),
        "storage_capacity": canonical_peak_spill <= criteria.flow_tolerance_m3_s,
    }
    if scenario.role == "design":
        criteria_results.update(
            {
                "design_total_release": canonical_peak_structured_outflow
                <= criteria.maximum_design_release_m3_s + criteria.flow_tolerance_m3_s,
                "emergency_weir_inactive": canonical_peak_weir <= criteria.flow_tolerance_m3_s,
            }
        )
    else:
        criteria_results["emergency_weir_activated"] = (
            canonical_peak_weir + criteria.flow_tolerance_m3_s >= criteria.minimum_major_weir_flow_m3_s
        )
    warnings = []
    if not all_converged:
        warnings.append("outlet_iteration_not_converged")
    if canonical_peak_spill > criteria.flow_tolerance_m3_s:
        warnings.append("uncontrolled_spill_occurred")

    run_result = HydraulicRunResult(
        run_id=run_id,
        world_id=source.world_id,
        scenario_id=scenario.scenario_id,
        engine=engine,
        source_state_sha256=source_state_sha256,
        calculation_input_sha256=calculation_input_sha256,
        catchment_peak_flows_m3_s={key: _rounded(value) for key, value in sorted(catchment_peaks.items())},
        peak_total_inflow_m3_s=canonical_peak_total_inflow,
        peak_orifice_flow_m3_s=canonical_peak_orifice,
        peak_weir_flow_m3_s=canonical_peak_weir,
        peak_structured_outflow_m3_s=canonical_peak_structured_outflow,
        peak_total_outflow_m3_s=canonical_peak_total_outflow,
        peak_uncontrolled_spill_m3_s=canonical_peak_spill,
        maximum_storage_m3=canonical_maximum_storage,
        maximum_water_surface_elevation_m=canonical_maximum_water_surface,
        minimum_freeboard_m=canonical_freeboard,
        maximum_pipe_velocity_m_s=canonical_maximum_pipe_velocity,
        pipe_capacity_m3_s=canonical_pipe_capacity,
        maximum_node_hgl_m=canonical_maximum_node_hgl,
        minimum_hgl_clearance_m=canonical_minimum_hgl_clearance,
        continuity_error_m3=canonical_continuity_error,
        criteria=dict(sorted(criteria_results.items())),
        warnings=tuple(warnings),
    )
    return run_result, HydraulicTimeSeries(run_id=run_id, steps=tuple(steps))
