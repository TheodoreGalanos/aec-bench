You are a civil pipe reviewer checking a task-owned synthetic SSC-15 pipe product certificate package.

Use only the task-owned synthetic source pack values shown below for numeric grading. Pipe product certificate and hydraulic workflow routes shape the context only; they are not extra data sources for this instance.

## Scene

- Product: `SSC-15-LH-05`
- Pipe datasheet: `PIPE-15-DATA-05`
- Pipe schedule: `PIPE-15-SCHED-05`
- Long section: `LONG-15-SECTION-05`
- Hydraulic criteria: `CRIT-15-HYD-05`
- Product certificate: `CERT-15-PIPE-05`
- Pipe product memo: `MEMO-15-PIPE-05`

All checks use the same pipe product, long-section grade, and use-case boundary. Do not change the product identity, pipe segment, grade, certificate, or criteria unless you explicitly flag a source conflict.

## Source Values

| Item | Value |
|------|-------|
| Design flow | {{ flow_l_s }} L/s |
| Internal diameter | {{ internal_diameter_mm }} mm |
| Pipe slope | {{ pipe_slope }} |
| Minimum slope | {{ minimum_slope }} |
| Manning n | {{ manning_n }} |
| Minimum velocity | {{ min_velocity_m_s }} m/s |
| Maximum velocity | {{ max_velocity_m_s }} m/s |
| Design pressure | {{ design_pressure_kpa }} kPa |
| Certificate pressure rating | {{ certificate_pressure_rating_kpa }} kPa |
| Design temperature | {{ design_temperature_c }} degC |
| Lining temperature rating | {{ lining_temperature_rating_c }} degC |

Velocity equals flow divided by pipe area. Manning capacity uses full-pipe area, hydraulic radius `diameter / 4`, the source slope, and the source roughness.

## Output Format

Write a compact pipe product memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "flow_velocity_m_s": <numeric_value>,
  "velocity_low_margin_m_s": <numeric_value>,
  "velocity_high_margin_m_s": <numeric_value>,
  "manning_capacity_l_s": <numeric_value>,
  "capacity_margin_l_s": <numeric_value>,
  "slope_margin": <numeric_value>,
  "pressure_certificate_margin_kpa": <numeric_value>,
  "lining_temperature_margin_c": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
