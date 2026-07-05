You are a mechanical piping product reviewer checking a task-owned synthetic SSC-11 pipe material, velocity, certificate, and support package.

Use only the task-owned synthetic source pack values shown below for numeric grading. Pipe material certificate review, velocity and pressure-loss checks, Darcy-Weisbach calculations, and pipe support coordination routes shape the workflow context only; they are not extra data sources for this instance.

## Scene

- Product family: `SSC-11-LH-07`
- Line list: `LINE-SSC11-007`
- Material certificate: `MAT-SSC11-007`
- Design criteria excerpt: `CRIT-SSC11-007`
- Support detail: `SUP-SSC11-007`
- Coordination memo: `MEMO-SSC11-007`

## Source Values

| Item | Value |
|------|-------|
| Flow | {{ flow_l_s }} L/s |
| Hydraulic internal diameter | {{ pipe_internal_diameter_mm }} mm |
| Maximum velocity | {{ maximum_velocity_m_s }} m/s |
| Pipe length | {{ pipe_length_m }} m |
| Darcy friction factor | {{ darcy_friction_factor }} |
| Maximum pressure loss | {{ maximum_pressure_loss_kpa }} kPa |
| Design pressure | {{ design_pressure_kpa }} kPa |
| Pipe pressure class | {{ pipe_pressure_class_kpa }} kPa |
| Lining maximum velocity | {{ lining_max_velocity_m_s }} m/s |
| Carbon | {{ carbon_percent }} percent |
| Manganese | {{ manganese_percent }} percent |
| Chromium | {{ chromium_percent }} percent |
| Molybdenum | {{ molybdenum_percent }} percent |
| Vanadium | {{ vanadium_percent }} percent |
| Nickel | {{ nickel_percent }} percent |
| Copper | {{ copper_percent }} percent |
| Carbon equivalent limit | {{ carbon_equivalent_limit }} |
| Required certificate fields | {{ required_certificate_items }} |
| Matching certificate fields | {{ matching_certificate_items }} |
| Support span | {{ support_span_m }} m |
| Support pipe outer diameter | {{ pipe_outer_diameter_mm }} mm |
| Support pipe wall thickness | {{ pipe_wall_thickness_mm }} mm |
| Steel density | {{ steel_density_kg_m3 }} kg/m3 |
| Contents density | {{ contents_density_kg_m3 }} kg/m3 |
| Support vertical allowable | {{ support_vertical_allowable_kn }} kN |

## Checks

- Pipe velocity equals flow divided by pipe area.
- Darcy pressure loss uses friction factor, length over diameter, and velocity head.
- Pressure-class margin equals pipe pressure class minus design pressure.
- Carbon equivalent equals `C + Mn/6 + (Cr + Mo + V)/5 + (Ni + Cu)/15`.
- Certificate match percent equals matching fields divided by required fields times 100.
- Support reaction includes steel annulus weight and contents weight over the support span.
- Overall pass score is `1.0` only when velocity, pressure loss, pressure class, lining velocity, carbon equivalent, certificate, and support checks pass; otherwise it is `0.0`.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the object IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "pipe_velocity_m_s": <numeric_value>,
  "velocity_margin_m_s": <numeric_value>,
  "pressure_loss_kpa": <numeric_value>,
  "pressure_loss_margin_kpa": <numeric_value>,
  "pressure_class_margin_kpa": <numeric_value>,
  "lining_velocity_margin_m_s": <numeric_value>,
  "carbon_equivalent": <numeric_value>,
  "carbon_equivalent_margin": <numeric_value>,
  "certificate_match_percent": <numeric_value>,
  "support_vertical_reaction_kn": <numeric_value>,
  "support_margin_kn": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
