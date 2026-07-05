You are a mechanical fire-protection engineer checking a task-owned synthetic SSC-11 fire-main hydraulic and seismic support package.

Use only the task-owned synthetic source pack values shown below for numeric grading. NFPA-style fire-main checks, Hazen-Williams calculations, ASME-style piping support workflows, and seismic bracing coordination routes shape the workflow context only; they are not extra data sources for this instance.

## Scene

- Product family: `SSC-11-LH-02`
- Fire-main route: `FIRE-SSC11-002`
- Flow basis: `FLOW-SSC11-002`
- Support detail: `SUP-SSC11-002`
- Pump basis: `PUMP-SSC11-002`
- Coordination memo: `MEMO-SSC11-002`

## Source Values

| Item | Value |
|------|-------|
| Design fire flow | {{ fire_flow_l_s }} L/s |
| Main length | {{ main_length_m }} m |
| Hydraulic internal diameter | {{ pipe_internal_diameter_mm }} mm |
| Hazen-Williams C | {{ hazen_williams_c }} |
| Riser elevation | {{ riser_elevation_m }} m |
| Remote head flow | {{ remote_head_flow_l_min }} L/min |
| Remote head count | {{ remote_head_count }} |
| Source residual pressure | {{ source_residual_pressure_kpa }} kPa |
| Pump boost pressure | {{ pump_boost_pressure_kpa }} kPa |
| Required remote residual pressure | {{ required_remote_pressure_kpa }} kPa |
| Support span | {{ support_span_m }} m |
| Support pipe outer diameter | {{ pipe_outer_diameter_mm }} mm |
| Support pipe wall thickness | {{ pipe_wall_thickness_mm }} mm |
| Water density | {{ water_density_kg_m3 }} kg/m3 |
| Steel density | {{ steel_density_kg_m3 }} kg/m3 |
| Seismic horizontal coefficient | {{ seismic_horizontal_coefficient }} |
| Vertical support allowable | {{ support_vertical_allowable_kn }} kN |
| Horizontal support allowable | {{ support_horizontal_allowable_kn }} kN |

## Checks

- Hazen-Williams loss equals `10.67 x length x flow^1.852 / (C^1.852 x diameter^4.871)`, using m3/s and m.
- Friction loss in kPa equals head loss times `9.81`.
- Remote demand equals `remote_head_flow_l_min x remote_head_count / 60`.
- Remote pressure equals source residual plus pump boost minus friction loss minus elevation pressure.
- Support line load includes pipe annulus steel weight plus contents weight.
- Vertical reaction equals line load times support span.
- Seismic horizontal reaction equals vertical reaction times the horizontal coefficient.
- Overall pass score is `1.0` only when flow margin, remote pressure margin, and both support utilizations pass; otherwise it is `0.0`.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the object IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "hazen_williams_loss_m": <numeric_value>,
  "friction_loss_kpa": <numeric_value>,
  "remote_flow_demand_l_s": <numeric_value>,
  "fire_flow_margin_l_s": <numeric_value>,
  "remote_pressure_kpa": <numeric_value>,
  "remote_pressure_margin_kpa": <numeric_value>,
  "support_line_load_kn_m": <numeric_value>,
  "support_vertical_reaction_kn": <numeric_value>,
  "seismic_horizontal_reaction_kn": <numeric_value>,
  "support_vertical_utilization": <numeric_value>,
  "support_horizontal_utilization": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
