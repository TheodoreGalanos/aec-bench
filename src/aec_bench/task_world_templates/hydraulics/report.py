# ABOUTME: Renders deterministic, source-bound reports for hydraulic mini-world runs.
# ABOUTME: States screening assumptions and prevents fallback results being called SWMM output.

from __future__ import annotations

from aec_bench.task_world_templates.hydraulics.contracts import (
    HydraulicRunRequest,
    HydraulicRunResult,
    HydraulicSourceState,
)


def render_hydraulic_report(
    source: HydraulicSourceState,
    request: HydraulicRunRequest,
    result: HydraulicRunResult,
) -> str:
    """Return the canonical Markdown report for one deterministic run."""
    catchment_rows = "\n".join(
        f"| {catchment_id} | {flow:.6f} |" for catchment_id, flow in sorted(result.catchment_peak_flows_m3_s.items())
    )
    pipe_rows = "\n".join(
        f"| {pipe_id} | {result.maximum_pipe_velocity_m_s[pipe_id]:.6f} | {result.pipe_capacity_m3_s[pipe_id]:.6f} |"
        for pipe_id in sorted(result.maximum_pipe_velocity_m_s)
    )
    hgl_rows = "\n".join(f"| {node_id} | {hgl:.6f} |" for node_id, hgl in sorted(result.maximum_node_hgl_m.items()))
    criterion_rows = "\n".join(
        f"| {criterion} | {'pass' if passed else 'fail'} |" for criterion, passed in sorted(result.criteria.items())
    )
    warnings = "None." if not result.warnings else ", ".join(result.warnings)
    return (
        "# SSC-03 Deterministic Hydraulic Screening Report\n\n"
        "## Identity\n\n"
        f"- World: `{result.world_id}`\n"
        f"- Scenario: `{result.scenario_id}`\n"
        f"- Run: `{result.run_id}`\n"
        f"- Package SHA-256: `{request.package_sha256}`\n"
        f"- Source-state SHA-256: `{result.source_state_sha256}`\n"
        f"- Calculation-input SHA-256: `{result.calculation_input_sha256}`\n"
        f"- Engine: `{result.engine.engine_id}` `{result.engine.engine_version}`\n"
        f"- Engine implementation SHA-256: `{result.engine.implementation_sha256}`\n"
        f"- Engine runtime-dependency SHA-256: `{result.engine.runtime_dependency_sha256}`\n\n"
        "## Claim boundary\n\n"
        f"{source.claim_boundary}\n\n"
        "The calculation uses a fixed-step triangular inflow hydrograph, level-pool storage, "
        "a head-dependent circular orifice, a tailwater-reduced sharp-crested rectangular emergency weir, and a "
        "full-pipe Manning/minor-loss HGL chain. It is not a generated SWMM report.\n\n"
        "## Catchment peak flows\n\n"
        "| Catchment | Peak flow (m3/s) |\n"
        "| --- | ---: |\n"
        f"{catchment_rows}\n\n"
        "## Basin and outlet summary\n\n"
        f"- Peak total inflow: {result.peak_total_inflow_m3_s:.6f} m3/s\n"
        f"- Peak controlled-orifice flow: {result.peak_orifice_flow_m3_s:.6f} m3/s\n"
        f"- Peak emergency-weir flow: {result.peak_weir_flow_m3_s:.6f} m3/s\n"
        f"- Peak structured outlet flow: {result.peak_structured_outflow_m3_s:.6f} m3/s\n"
        f"- Peak total outflow: {result.peak_total_outflow_m3_s:.6f} m3/s\n"
        f"- Maximum storage: {result.maximum_storage_m3:.6f} m3\n"
        f"- Maximum water-surface elevation: {result.maximum_water_surface_elevation_m:.6f} m\n"
        f"- Minimum freeboard: {result.minimum_freeboard_m:.6f} m\n"
        f"- Continuity error: {result.continuity_error_m3:.6f} m3\n\n"
        "## Pipe results\n\n"
        "| Pipe | Maximum velocity (m/s) | Manning capacity (m3/s) |\n"
        "| --- | ---: | ---: |\n"
        f"{pipe_rows}\n\n"
        "## Node HGL results\n\n"
        "| Node | Maximum HGL (m) |\n"
        "| --- | ---: |\n"
        f"{hgl_rows}\n\n"
        "## Criteria\n\n"
        "| Criterion | Result |\n"
        "| --- | --- |\n"
        f"{criterion_rows}\n\n"
        f"Warnings: {warnings}\n"
    )
