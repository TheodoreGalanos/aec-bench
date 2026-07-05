You are a structural engineer checking a task-owned synthetic SSC-14 marine fender, mooring, and berthing structure package.

Use only the task-owned synthetic source pack values below for numeric grading. Berthing energy, fender, mooring, water-level, and structural support workflows shape the context only; they are not extra data sources for this instance.

## Scene

- Product: `SSC-14-LH-05`
- Berth layout: `BERTH-SSC14-005`
- Vessel data: `VESSEL-SSC14-005`
- Fender and mooring schedule: `FENDER-SSC14-005`
- Water-level table: `WATER-SSC14-005`
- Marine structural memo: `MEMO-SSC14-005`

## Source Values

- Vessel displacement, berthing velocity, and berthing coefficient: {{ vessel_displacement_t }} t, {{ berthing_velocity_m_s }} m/s, {{ berthing_coefficient }}
- Fender demand factor, capacity, and stroke: {{ fender_demand_factor }}, {{ fender_energy_capacity_kj }} kJ, {{ fender_stroke_m }} m
- Wind pressure, projected area, and drag coefficient: {{ wind_pressure_kpa }} kPa, {{ vessel_projected_area_m2 }} m2, {{ wind_drag_coefficient }}
- Active mooring lines, line angle, and line capacity: {{ active_mooring_line_count }}, {{ mooring_line_angle_deg }} deg, {{ mooring_line_capacity_kn }} kN
- Design water level, deck level, and required freeboard: {{ design_water_level_m }} m, {{ deck_level_m }} m, {{ required_freeboard_m }} m
- Vertical support load, vertical load factor, and fender reaction factor: {{ vertical_support_load_kn }} kN, {{ vertical_load_factor }}, {{ fender_reaction_combination_factor }}

## Required Calculations

- Berthing energy is `0.5 x displacement_t x 1000 x velocity^2 / 1000 x berthing_coefficient`.
- Fender energy demand is berthing energy times fender demand factor.
- Fender reaction is fender energy demand divided by fender stroke.
- Mooring wind force is wind pressure times projected area times drag coefficient.
- Mooring line demand is wind force divided by active line count and `cos(line_angle)`.
- Water-level margin is deck level minus design water level and required freeboard.
- Combined support load is factored vertical support load plus the combined fender reaction component.
- Overall pass score is `1.0` only when fender utilization, mooring utilization, and water-level margin pass.

Write a compact marine structural memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the source IDs above and state whether the baseline source pack passes the current synthetic checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "berthing_energy_kj": <numeric_value>,
  "fender_energy_demand_kj": <numeric_value>,
  "fender_energy_utilization": <numeric_value>,
  "fender_reaction_kn": <numeric_value>,
  "mooring_wind_force_kn": <numeric_value>,
  "mooring_line_demand_kn": <numeric_value>,
  "mooring_utilization": <numeric_value>,
  "water_level_margin_m": <numeric_value>,
  "combined_support_load_kn": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
