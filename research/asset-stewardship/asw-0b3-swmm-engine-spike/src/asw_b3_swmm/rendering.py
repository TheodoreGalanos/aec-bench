# ABOUTME: Renders deterministic SWMM inputs for isolated Pump A and Pump B diagnostic probes.
# ABOUTME: Encodes no transfer, degradation, maintenance, scenario, or production-world semantics.

from __future__ import annotations

from datetime import timedelta

from asw_b3_swmm.specification import Specification


def _time(value: int) -> str:
    hours, remainder = divmod(value, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _curve_lines(specification: Specification) -> str:
    lines: list[str] = []
    for index, (head_m, flow_lps) in enumerate(specification.pump_curve):
        curve_type = "PUMP3" if index == 0 else ""
        lines.append(f"PUMP_CURVE      {curve_type:<5}  {head_m:<8} {flow_lps}")
    return "\n".join(lines)


def render_probe(specification: Specification, probe_id: str) -> str:
    """Render one disposable, single-active-pump SWMM probe."""
    probe = specification.probe(probe_id)
    simulation = specification.simulation
    geometry = specification.diagnostic_geometry
    end = simulation.start + timedelta(seconds=simulation.horizon_seconds)
    statuses = {
        probe.active_pump: "ON",
        probe.inactive_pump: "OFF",
    }
    storage_line = (
        f"WET_WELL        {geometry.wet_well_invert_m}        "
        f"{geometry.wet_well_max_depth_m}       {geometry.wet_well_initial_depth_m}        "
        f"{geometry.wet_well_shape}  {geometry.wet_well_major_axis_m}   "
        f"{geometry.wet_well_minor_axis_m}   {geometry.wet_well_side_slope}  0.0       0.0"
    )
    conduit_line = (
        f"FORCE_MAIN      DISCHARGE   OUTFALL   {geometry.force_main_length_m}   "
        f"{geometry.force_main_conduit_roughness}       0.0       0.0        0.0       0.0"
    )
    xsection_line = (
        f"FORCE_MAIN      FORCE_MAIN  {geometry.force_main_diameter_m}   "
        f"{geometry.force_main_absolute_roughness_mm}    0      0      1"
    )
    return f"""[TITLE]
;; ASW-0B3 disposable engine diagnostic
;; Probe: {probe.probe_id}

[OPTIONS]
FLOW_UNITS              {simulation.flow_units}
INFILTRATION            HORTON
FLOW_ROUTING            {simulation.routing_model}
LINK_OFFSETS            DEPTH
FORCE_MAIN_EQUATION     {simulation.force_main_equation}
IGNORE_RAINFALL         YES
SKIP_STEADY_STATE       NO
START_DATE              {simulation.start:%m/%d/%Y}
START_TIME              {simulation.start:%H:%M:%S}
REPORT_START_DATE       {simulation.start:%m/%d/%Y}
REPORT_START_TIME       {simulation.start:%H:%M:%S}
END_DATE                {end:%m/%d/%Y}
END_TIME                {end:%H:%M:%S}
REPORT_STEP             {_time(simulation.report_step_seconds)}
WET_STEP                {_time(simulation.report_step_seconds)}
DRY_STEP                {_time(simulation.report_step_seconds)}
ROUTING_STEP            {_time(simulation.routing_step_seconds)}
RULE_STEP               {_time(simulation.routing_step_seconds)}
ALLOW_PONDING           NO
VARIABLE_STEP           0.00
MINIMUM_STEP            0.50
THREADS                 {simulation.threads}

[JUNCTIONS]
;;Name          Elevation  MaxDepth  InitDepth  SurDepth  Aponded
DISCHARGE       {geometry.discharge_invert_m}        {geometry.discharge_max_depth_m}       0.0        0.0       0.0

[OUTFALLS]
;;Name          Elevation  Type  Stage Data  Gated  Route To
OUTFALL         {geometry.outfall_invert_m}        FREE              NO

[STORAGE]
;;Name          Elevation  MaxDepth  InitDepth  Shape        L     W     Z  SurDepth  Fevap
{storage_line}

[DWF]
;;Node          Constituent  Baseline
WET_WELL        FLOW         {geometry.dry_weather_inflow_lps}

[CONDUITS]
;;Name          From Node   To Node   Length  Roughness  InOffset  OutOffset  InitFlow  MaxFlow
{conduit_line}

[PUMPS]
;;Name          From Node   To Node    Pump Curve  Status  Startup  Shutoff
PUMP_A          WET_WELL    DISCHARGE  PUMP_CURVE  {statuses["PUMP_A"]}     0.0      0.0
PUMP_B          WET_WELL    DISCHARGE  PUMP_CURVE  {statuses["PUMP_B"]}     0.0      0.0

[XSECTIONS]
;;Link          Shape       Geom1  Geom2  Geom3  Geom4  Barrels
{xsection_line}

[CURVES]
;;Name          Type   Head-m   Flow-LPS
{_curve_lines(specification)}

[REPORT]
INPUT           NO
CONTROLS        NO
AVERAGES        NO
SUBCATCHMENTS   NONE
NODES           ALL
LINKS           ALL
"""
