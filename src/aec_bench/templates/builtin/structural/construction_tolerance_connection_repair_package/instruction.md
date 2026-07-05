You are a structural engineer checking a task-owned synthetic SSC-14 construction tolerance and connection repair package.

Use only the task-owned synthetic source pack values below for numeric grading. As-built survey, connection detail, tolerance specification, field NCR, and weldability workflows shape the context only; they are not extra data sources for this instance.

## Scene

- Product: `SSC-14-LH-07`
- As-built survey: `SURVEY-SSC14-007`
- Connection detail: `CONN-SSC14-007`
- Tolerance specification: `TOL-SSC14-007`
- Field NCR/comment register: `NCR-SSC14-007`
- Field response memo: `MEMO-SSC14-007`

## Source Values

- Measured offset and permitted tolerance: {{ measured_offset_mm }} mm and {{ permitted_tolerance_mm }} mm
- Available slot adjustment and maximum repair shim: {{ available_slot_adjustment_mm }} mm and {{ maximum_repair_shim_mm }} mm
- Bracket service load, arm, and moment capacity: {{ bracket_service_load_kn }} kN, {{ bracket_arm_m }} m, {{ bracket_moment_capacity_knm }} kNm
- Repair material chemistry: C {{ carbon_percent }} %, Mn {{ manganese_percent }} %, Cr {{ chromium_percent }} %, Mo {{ molybdenum_percent }} %, V {{ vanadium_percent }} %, Ni {{ nickel_percent }} %, Cu {{ copper_percent }} %
- Weld carbon equivalent limit and minimum remaining slot margin: {{ weld_carbon_equivalent_limit }} and {{ minimum_remaining_slot_margin_mm }} mm

## Required Calculations

- Tolerance exceedance is measured offset minus permitted tolerance, not less than zero.
- Required slot adjustment is the measured offset.
- Remaining slot margin is available slot adjustment minus required slot adjustment.
- Repair shim margin is maximum shim thickness minus tolerance exceedance.
- Baseline moment is service load times bracket arm.
- Added moment is service load times tolerance exceedance in metres.
- Bracket moment utilization is total moment divided by bracket moment capacity.
- Weld carbon equivalent is `C + Mn / 6 + (Cr + Mo + V) / 5 + (Ni + Cu) / 15`.
- Repair acceptance is `1.0` only when slot margin, shim margin, bracket moment, and weldability checks pass.

Write a compact field response memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the source IDs above and state whether the baseline source pack passes the current synthetic checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "tolerance_exceedance_mm": <numeric_value>,
  "required_slot_adjustment_mm": <numeric_value>,
  "remaining_slot_margin_mm": <numeric_value>,
  "repair_shim_margin_mm": <numeric_value>,
  "baseline_moment_knm": <numeric_value>,
  "added_moment_knm": <numeric_value>,
  "bracket_moment_utilization": <numeric_value>,
  "weld_carbon_equivalent": <numeric_value>,
  "carbon_equivalent_margin": <numeric_value>,
  "repair_acceptance_score": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
