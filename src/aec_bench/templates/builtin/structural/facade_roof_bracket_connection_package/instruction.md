You are a structural engineer checking a task-owned synthetic SSC-14 facade or roof bracket, anchor, and connection package.

Use only the task-owned synthetic source pack values below for numeric grading. Wind loading, bracket design, anchor reports, and material certificates shape the workflow context only; they are not extra data sources for this instance.

## Scene

- Product: `SSC-14-LH-02`
- Facade/roof elevation: `ELEV-SSC14-002`
- Wind criteria: `WIND-SSC14-002`
- Bracket and anchor schedule: `BRKT-SSC14-002`
- Material certificate: `MAT-SSC14-002`
- Connection memo: `MEMO-SSC14-002`

## Source Values

- Wind pressure, tributary width, tributary height: {{ wind_pressure_kpa }} kPa, {{ tributary_width_m }} m, {{ tributary_height_m }} m
- Facade or roof dead load: {{ facade_dead_load_kpa }} kPa
- Wind and dead load factors: {{ wind_load_factor }}, {{ dead_load_factor }}
- Bracket horizontal capacity: {{ bracket_horizontal_capacity_kn }} kN
- Anchor tension and shear capacities: {{ anchor_tension_capacity_kn }} kN, {{ anchor_shear_capacity_kn }} kN
- Active anchor count: {{ active_anchor_count }}
- Material certificate chemistry: C {{ carbon_percent }} %, Mn {{ manganese_percent }} %, Cr {{ chromium_percent }} %, Mo {{ molybdenum_percent }} %, V {{ vanadium_percent }} %, Ni {{ nickel_percent }} %, Cu {{ copper_percent }} %
- Carbon equivalent limit: {{ carbon_equivalent_limit }}

## Required Calculations

- Tributary area is width times height.
- Service wind and dead loads are pressure times tributary area.
- Factored reactions use the listed load factors.
- Bracket utilization is factored out-of-plane reaction divided by bracket capacity.
- Anchor demands are factored reactions divided by active anchor count.
- Anchor combined utilization is `sqrt((tension / tension_capacity)^2 + (shear / shear_capacity)^2)`.
- Carbon equivalent is `C + Mn / 6 + (Cr + Mo + V) / 5 + (Ni + Cu) / 15`.
- Overall pass score is `1.0` only when bracket utilization, anchor combined utilization, and carbon equivalent margin pass.

Write a compact connection memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the source IDs above and state whether the baseline source pack passes the current synthetic checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "tributary_area_m2": <numeric_value>,
  "service_wind_load_kn": <numeric_value>,
  "service_dead_load_kn": <numeric_value>,
  "factored_out_of_plane_reaction_kn": <numeric_value>,
  "factored_vertical_reaction_kn": <numeric_value>,
  "bracket_utilization": <numeric_value>,
  "anchor_tension_per_anchor_kn": <numeric_value>,
  "anchor_shear_per_anchor_kn": <numeric_value>,
  "anchor_combined_utilization": <numeric_value>,
  "carbon_equivalent": <numeric_value>,
  "carbon_equivalent_margin": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
