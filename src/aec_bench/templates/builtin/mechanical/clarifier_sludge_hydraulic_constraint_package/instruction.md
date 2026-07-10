You are a wastewater process engineer checking a task-owned synthetic SSC-10 clarifier loading, sludge, and hydraulic constraint package.

Use only the task-owned synthetic source pack values shown below for numeric grading. Clarifier loading, sludge wasting, hydraulic profile, and permit criteria workflows shape the context only; this instance does not parse a real process model or accepted project report.

## Scene

- Product: `SSC-10-LH-05`
- Clarifier schedule: `CLAR-10-SCHED-05`
- Sampling/load table: `SAMPLE-10-LOAD-05`
- Sludge wasting table: `SLUDGE-10-WASTE-05`
- Hydraulic profile: `HGL-10-PROFILE-05`
- Permit criteria table: `PERMIT-10-CRIT-05`
- Clarifier note: `MEMO-10-CLAR-05`

## Source Values

| Item | Value |
| --- | --- |
| Flow | {{ flow_rate_m3_d }} m3/d |
| Clarifier diameter | {{ clarifier_diameter_m }} m |
| MLSS | {{ mlss_mg_l }} mg/L |
| Maximum SOR | {{ max_sor_m3_m2_d }} m3/m2/d |
| Maximum SLR | {{ max_slr_kg_m2_d }} kg/m2/d |
| Influent BOD | {{ influent_bod_mg_l }} mg/L |
| Effluent BOD | {{ effluent_bod_mg_l }} mg/L |
| Sludge yield | {{ sludge_yield_kg_kg_bod }} kg/kg BOD |
| Wasting capacity | {{ wasting_capacity_kg_d }} kg/d |
| Sludge blanket limit | {{ sludge_blanket_limit_m }} m |
| Measured sludge blanket | {{ measured_sludge_blanket_m }} m |
| Clarifier volume | {{ clarifier_volume_m3 }} m3 |
| Minimum HRT | {{ min_hrt_hr }} h |
| Recycle percent | {{ recycle_percent }} % |

## Calculation Rules

- Clarifier area equals `pi x clarifier_diameter_m^2 / 4`.
- Surface overflow rate equals flow divided by clarifier area.
- Solids loading equals `flow x MLSS / 1000 / clarifier area`.
- BOD removed equals `flow x (influent BOD - effluent BOD) / 1000`.
- Sludge production equals BOD removed times sludge yield.
- Clarifier HRT equals clarifier volume divided by flow, converted to hours.
- Recycle flow equals flow times recycle percent.
- Overall pass score is `1.0` only when SOR, SLR, wasting, sludge blanket, and HRT margins are non-negative.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the source IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated modelling evidence, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "surface_overflow_rate_m3_m2_d": <numeric_value>,
  "sor_margin_m3_m2_d": <numeric_value>,
  "solids_loading_kg_m2_d": <numeric_value>,
  "slr_margin_kg_m2_d": <numeric_value>,
  "bod_removed_kg_d": <numeric_value>,
  "sludge_production_kg_d": <numeric_value>,
  "wasting_capacity_margin_kg_d": <numeric_value>,
  "sludge_blanket_margin_m": <numeric_value>,
  "clarifier_hrt_hr": <numeric_value>,
  "hrt_margin_hr": <numeric_value>,
  "recycle_flow_m3_d": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
