You are a civil drainage engineer checking a task-owned synthetic SSC-11 stormwater outlet, flap-gate, and HGL package.

Use only the task-owned synthetic source pack values shown below for numeric grading. Manning hydraulic calculations, stormwater HGL review workflows, flap-gate product coordination, and outfall support routes shape the workflow context only; they are not extra data sources for this instance.

## Scene

- Product family: `SSC-11-LH-04`
- Drainage calculation: `DRAIN-SSC11-004`
- Flap-gate datasheet: `FLAP-SSC11-004`
- Tailwater table: `TAIL-SSC11-004`
- Outlet pipe/support detail: `PIPE-SSC11-004`
- Coordination memo: `MEMO-SSC11-004`

## Source Values

| Item | Value |
|------|-------|
| Pipe diameter | {{ pipe_diameter_m }} m |
| Design flow | {{ design_flow_m3_s }} m3/s |
| Pipe length | {{ pipe_length_m }} m |
| Manning n | {{ manning_n }} |
| Tailwater level | {{ tailwater_level_m }} m |
| Flap-gate loss coefficient | {{ flap_gate_loss_coefficient }} |
| Minor-loss coefficient | {{ minor_loss_coefficient }} |
| Upstream invert | {{ upstream_invert_m }} m |
| Road surface level | {{ road_surface_level_m }} m |
| Pipe support line load | {{ pipe_support_line_load_kn_m }} kN/m |
| Support span | {{ support_span_m }} m |
| Flap-gate weight | {{ flap_gate_weight_kn }} kN |
| Support allowable | {{ support_allowable_kn }} kN |

## Checks

- Pipe velocity equals design flow divided by pipe area.
- Manning friction slope uses full-pipe area and hydraulic radius.
- Flap-gate and minor losses equal their loss coefficients times velocity head.
- Upstream HGL equals tailwater plus friction, flap-gate, and minor losses.
- HGL clearance equals road surface level minus upstream HGL.
- Pipe crown clearance equals road surface level minus upstream invert minus pipe diameter.
- Outfall support reaction equals pipe line load times support span plus flap-gate weight.
- Overall pass score is `1.0` only when HGL, pipe crown, and support checks pass; otherwise it is `0.0`.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the object IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "pipe_velocity_m_s": <numeric_value>,
  "friction_loss_m": <numeric_value>,
  "flap_gate_headloss_m": <numeric_value>,
  "minor_loss_m": <numeric_value>,
  "upstream_hgl_m": <numeric_value>,
  "hgl_clearance_to_surface_m": <numeric_value>,
  "pipe_crown_margin_to_surface_m": <numeric_value>,
  "outfall_support_reaction_kn": <numeric_value>,
  "support_utilization": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
