You are a civil drainage engineer checking a task-owned synthetic SSC-03 outfall tailwater, flap-gate, and coastal boundary package.

Use only the task-owned synthetic source pack values shown below for numeric grading. Manning pipe hydraulics, flap-gate headloss checks, outfall tailwater workflows, and coastal boundary coordination shape the workflow context only; they are not extra data sources for this instance.

## Scene

- Product family: `SSC-03-LH-05`
- Outfall long section: `OUTFALL-SSC03-005`
- Tide/tailwater table: `TIDE-SSC03-005`
- Flap-gate datasheet: `FLAP-SSC03-005`
- Upstream HGL table: `HGL-SSC03-005`
- Outfall design memo: `MEMO-SSC03-005`

## Source Values

| Item | Value |
|------|-------|
| Pipe diameter | {{ pipe_diameter_m }} m |
| Design flow | {{ design_flow_m3_s }} m3/s |
| Pipe length | {{ pipe_length_m }} m |
| Manning n | {{ manning_n }} |
| Tailwater level | {{ tailwater_level_m }} m |
| Outfall invert | {{ outfall_invert_m }} m |
| Flap-gate loss coefficient | {{ flap_gate_loss_coefficient }} |
| Minor-loss coefficient | {{ minor_loss_coefficient }} |
| Upstream rim level | {{ upstream_rim_level_m }} m |
| Minimum HGL clearance | {{ minimum_hgl_clearance_m }} m |
| Coastal crest level | {{ coastal_crest_level_m }} m |
| Required coastal freeboard | {{ required_coastal_freeboard_m }} m |

## Checks

- Pipe velocity equals design flow divided by full-pipe area.
- Manning friction uses full-pipe hydraulic radius.
- Upstream HGL equals tailwater plus friction, flap-gate, and minor losses.
- Overall pass score is `1.0` only when HGL clearance and coastal freeboard checks pass; otherwise it is `0.0`.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the object IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated SWMM report-output evidence, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "pipe_velocity_m_s": <numeric_value>,
  "friction_loss_m": <numeric_value>,
  "flap_gate_headloss_m": <numeric_value>,
  "minor_loss_m": <numeric_value>,
  "upstream_hgl_m": <numeric_value>,
  "outfall_submergence_m": <numeric_value>,
  "hgl_clearance_m": <numeric_value>,
  "hgl_clearance_margin_m": <numeric_value>,
  "coastal_freeboard_margin_m": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
