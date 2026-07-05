You are an OLE and signalling interface engineer checking `SSC-02-LH-02`, a task-owned synthetic SSC-02 OLE sag, thermal stress, and signal-clearance package.

Use only the task-owned synthetic source pack values below for numeric grading. OLE sag-tension and clearance workflows shape the context only; this instance does not run an OLE model, parse a real span schedule, or validate an operator standard.

## Scene

- Design case: `CASE-SSC02-OLE-02`
- OLE span schedule: `OLE-02-SPAN-02`
- Route clearance table: `ROUTE-02-CLEAR-02`
- Weather/temperature case: `WEATHER-02-TEMP-02`
- Wire data sheet: `WIRE-02-DATA-02`
- Clearance criterion: `CRIT-02-CLEAR-02`
- Clearance memo: `MEMO-02-OLE-02`

## Source Values

| Item | Value |
|------|-------|
| Span length | {{ span_length_m }} m |
| Conductor unit weight | {{ conductor_unit_weight_n_m }} N/m |
| Initial tension | {{ initial_tension_kn }} kN |
| Thermal expansion coefficient | {{ thermal_expansion_per_c }} 1/deg C |
| Young's modulus | {{ youngs_modulus_mpa }} MPa |
| Temperature rise | {{ temp_delta_c }} deg C |
| Cross-section area | {{ cross_section_mm2 }} mm^2 |
| Static clearance | {{ static_clearance_m }} m |
| Signal envelope | {{ signal_envelope_m }} m |
| Maximum allowed sag | {{ max_allowed_sag_m }} m |
| Allowable thermal stress | {{ allowable_thermal_stress_mpa }} MPa |

Checks:

- Thermal stress equals `E x alpha x delta_T`.
- Thermal tension loss equals thermal stress times area divided by 1000.
- Hot tension equals initial tension minus thermal tension loss.
- Sag equals `unit_weight x span_length^2 / (8 x hot_tension_N)`.
- Clearance at sag equals static clearance minus sag.
- Overall pass score is `1.0` only when clearance, sag, and thermal-stress margins are non-negative; otherwise it is `0.0`.

## Output Format

Write a compact memo to `/workspace/output.md`. Preserve the object IDs above, state the task-owned synthetic source-pack boundary, and explain whether the baseline source pack passes the docs-only checks.

Do not claim authority approval, accepted project evidence, OLE model validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "thermal_stress_mpa": <numeric_value>,
  "thermal_tension_loss_kn": <numeric_value>,
  "hot_tension_kn": <numeric_value>,
  "sag_m": <numeric_value>,
  "clearance_at_sag_m": <numeric_value>,
  "clearance_margin_m": <numeric_value>,
  "sag_margin_m": <numeric_value>,
  "thermal_stress_margin_mpa": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
