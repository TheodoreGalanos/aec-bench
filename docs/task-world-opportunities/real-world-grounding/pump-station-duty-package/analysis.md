# ABOUTME: Analysis for grounding the pump station duty package in real workflows.
# ABOUTME: Summarizes workflow chain, inputs, outputs, benchmark implications, and multimodal scope.

# Pump Station Duty Package Analysis

## Real Workflow Chain

The chain is realistic:

inflow/duty requirement -> wet-well and level basis -> static lift -> pipe/fitting losses -> system curve -> pump curve intersection -> motor power and efficiency -> NPSH margin -> duty/standby operating note.

The weak point is no longer the existence of a public design source: the Ten States standards give a strong wastewater-pumping-station anchor. The remaining weak point is product-specific hydraulic equipment detail. Grundfos gives manufacturer-backed curve semantics and a product-selection surface. Xylem/Flygt now strengthens cavitation/NPSH, LCC/energy, and sustained-efficiency semantics, but we still need captured manufacturer/Hydraulic Institute style evidence for numeric power, NPSHr, and duty-point curve exports.

Xylem/Flygt, the simulator paper, and the inter-catchment transfer paper strengthen the long-horizon product-world side. They show real pump-station problems extending beyond initial TDH: variable static head in deep tunnel dewatering, clogging and maintenance, sump design, pump-start and transient analysis, VFD/soft-start controls, SCADA monitoring, energy consumption, fault diagnosis, water-level prediction, and overflow/WWTP-capacity coordination.

## Real Inputs

- Design inflow, peak inflow, emergency storage, operating philosophy, and redundancy requirement.
- Wet-well geometry and levels: invert, pump-off, pump-on, high level, overflow, and maintenance levels.
- Suction/discharge elevations, receiving hydraulic grade, force-main alignment, pipe lengths, diameters, roughness, valves, and fitting losses.
- Pump curves: head-flow, efficiency, power, and NPSHr for the selected impeller/speed.
- NPSH and cavitation inputs: NPSHa/NPSHr margin, submergence, suction configuration, operating point relative to BEP, and duty points for single-pump, parallel-pump, and VSD cases.
- Electrical data: motor rating, starting method/VFD, feeder constraints, standby power, controls, and telemetry.
- Operational/monitoring data for long-horizon variants: pump states, start/stop thresholds, level time series, flow/head estimates, electrical current/voltage/power, runtime, starts, overflow/treatment capacity state, and alarm/fault labels.

## Real Outputs

- Static head and TDH table for duty cases.
- System curve and selected pump duty point.
- Pump/motor power estimate and efficiency evidence.
- NPSHa versus NPSHr margin.
- Wet-well cycle/storage check.
- Duty/standby pump selection note.
- Energy, LCC, or sustained-efficiency comparison for variants where operating cost or wastewater clogging behavior matters.
- Operating/control note: lead/lag sequence, VFD or on/off logic, soft-start/stop assumptions, expected runtimes/starts, and monitoring handoff.
- Maintenance or diagnosis note for product-world variants: clogging, pump degradation, pipe fouling, or energy drift interpretation.

## Harness Implications

- The verifier should preserve both regulatory/design-criteria evidence and pump-curve evidence. A final TDH number is not enough because pump selection is an intersection between system and manufacturer curves.
- A realistic source pack can include a product-selection screenshot/export as an intermediate artifact, but the verifier needs structured curve points or extracted duty fields rather than only a rendered chart.
- A fixture-grade `manufacturer_curve_bundle` should include flow-head curve points, efficiency curve points, absorbed or shaft power curve points, NPSHr/NPSH3 curve points, selected duty point, impeller diameter or speed, BEP/operating-region context, system-curve intersection, unit basis, and extraction provenance.
- Strong failure modes include using only static head, omitting minor losses, using wrong wet-well level for worst-case suction, ignoring force-main roughness, or checking NPSH at the wrong flow.
- Difficulty can be scaled by adding parallel pumps, VFD control, rising main surge constraints, and wet-well cycle limits.
- Long-horizon variants can extend the initial selection into operating evidence: measured level cycles, pump starts, energy consumption, detected drift, and diagnosis of pump-side versus system-side faults.
- A stronger verifier split is emerging: design-criteria/wet-well basis, hydraulic system curve, manufacturer curve/duty fields, NPSH/cavitation margin, energy/sustained-efficiency, and operations/control evidence. The source pack should make these separable so a model can be wrong about NPSH without being automatically wrong about TDH.

## Multimodal Extension

- Inputs: wet-well drawing, long-section/profile, pump curve image/PDF, valve/fitting schedule, P&ID/control schematic, SCADA trend image/table, NPSH/cavitation note, or manufacturer case-study excerpt.
- Outputs: extracted pump-curve points, annotated system profile, duty table, pump selection memo, NPSH/cavitation margin note, control sequence, and monitoring/diagnosis note.
- Interesting checks: curve digitization, profile chainage-to-elevation extraction, level control interpretation, reconciliation of drawing levels with hydraulic calculations, NPSH margin across multiple duty points, and SCADA trend consistency with expected pump/system curves.

## Meta-Harness Opportunities

- Reconfigure application: wastewater lift station, stormwater pump station, booster station, irrigation, or process pump.
- Mutate wet-well levels, receiving HGL, force-main length, pipe roughness, and pump curve.
- Mutate operation mode: single pump, parallel pumps, VSD, clogged pump, pipe throttling, or high-overflow operating regime.
- Combine with treatment packages by passing influent pump station flows into process design.
- Combine with electrical packages by passing motor loads and controls into feeder/protection checks.
- Combine initial design, product selection, commissioning, and monitoring into a composite task-world template without creating a separate long-horizon task class. Meta-harness mutations should reconfigure source-pack fields, stage gates, and evidence availability inside the same task-world substrate.
