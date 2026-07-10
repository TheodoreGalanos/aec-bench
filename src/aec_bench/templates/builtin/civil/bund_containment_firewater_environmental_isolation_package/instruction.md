You are a civil and environmental interface engineer checking a task-owned synthetic SSC-19 bund containment, firewater, and environmental isolation package.

Use only the task-owned synthetic source pack values shown below for numeric grading. Bund design, firewater runoff capture, isolation drain operation, and environmental review workflows shape the context only; this instance does not run hydraulic software, parse a real drawing, or prove regulatory acceptance.

## Scene

- Product: `SSC-19-LH-07`
- Chemical inventory: `INV-19-CHEM-07`
- Bund layout: `BUND-19-LAYOUT-07`
- Firewater demand basis: `FIREWATER-19-DEMAND-07`
- Drain isolation schedule: `DRAIN-19-ISOLATION-07`
- Environmental criteria: `ENV-19-CRIT-07`
- Containment memo: `MEMO-19-CONTAIN-07`

## Source Values

| Item | Value |
| --- | --- |
| Largest container | {{ largest_container_l }} L |
| Rainfall depth | {{ rainfall_depth_mm }} mm |
| Bund area | {{ bund_area_m2 }} m2 |
| Foam allowance | {{ foam_allowance_l }} L |
| Equipment displacement | {{ equipment_displacement_l }} L |
| Bund capacity | {{ bund_capacity_l }} L |
| Firewater flow | {{ firewater_flow_l_s }} L/s |
| Firewater duration | {{ firewater_duration_min }} min |
| Isolation sump capacity | {{ isolation_sump_capacity_l }} L |
| Environmental freeboard | {{ environmental_freeboard_l }} L |
| Outlet headloss | {{ outlet_headloss_m }} m |
| Maximum outlet headloss | {{ max_outlet_headloss_m }} m |
| Total isolation valves | {{ isolation_valves_total }} |
| Verified isolation valves | {{ isolation_valves_verified }} |

## Checks

- Rainfall allowance equals rainfall depth in metres times bund area times 1000.
- Required bund volume equals largest container plus rainfall allowance plus foam allowance minus equipment displacement.
- Firewater runoff volume equals firewater flow times firewater duration in seconds.
- Isolation required volume equals firewater runoff volume plus environmental freeboard.
- Headloss margin equals maximum outlet headloss minus outlet headloss.
- Valve verification fraction equals verified valves divided by total valves.
- Overall pass score is `1.0` only when bund, isolation, headloss, and valve-verification checks pass; otherwise it is `0.0`.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the object IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, hydraulic software export validity, environmental permit acceptance, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "rainfall_allowance_l": <numeric_value>,
  "required_bund_volume_l": <numeric_value>,
  "bund_capacity_margin_l": <numeric_value>,
  "firewater_runoff_volume_l": <numeric_value>,
  "isolation_required_volume_l": <numeric_value>,
  "isolation_capacity_margin_l": <numeric_value>,
  "headloss_margin_m": <numeric_value>,
  "valve_verification_fraction": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
