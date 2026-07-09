You are a wastewater process engineer checking a task-owned synthetic SSC-10 aeration blower process, power, and acoustic package.

Use only the task-owned synthetic source pack values shown below for numeric grading. BioWin, GPS-X, SUMO, blower selection, and acoustic screening workflows shape the context only; this instance does not run those tools or parse a real process model, source pack, or vendor export.

## Scene

- Product: `SSC-10-LH-02`
- Sampling table: `SAMPLE-10-AER-02`
- Process criteria: `CRITERIA-10-AER-02`
- Blower data sheet: `BLOWER-10-DATA-02`
- Motor schedule: `MOTOR-10-SCHED-02`
- Receiver plan: `RECEIVER-10-PLAN-02`
- Aeration/acoustic memo: `MEMO-10-AER-02`

## Source Values

| Item | Value |
| --- | --- |
| Design flow | {{ flow_rate_m3_d }} m3/d |
| Influent BOD | {{ influent_bod_mg_l }} mg/L |
| Effluent BOD | {{ effluent_bod_mg_l }} mg/L |
| Influent TKN | {{ influent_tkn_mg_l }} mg/L |
| Effluent TKN | {{ effluent_tkn_mg_l }} mg/L |
| Sludge production | {{ sludge_production_kg_d }} kg/d |
| Denitrified nitrogen | {{ denitrified_nitrogen_mg_l }} mg/L |
| Field oxygen transfer efficiency | {{ field_transfer_efficiency }} |
| Air oxygen mass fraction | {{ air_oxygen_mass_fraction }} |
| Air density | {{ air_density_kg_m3 }} kg/m3 |
| Blower capacity | {{ blower_capacity_m3_min }} m3/min |
| Blower discharge pressure | {{ blower_discharge_pressure_kpa }} kPa |
| Blower efficiency | {{ blower_efficiency }} |
| Motor efficiency | {{ motor_efficiency }} |
| Selected motor | {{ selected_motor_kw }} kW |
| Blower sound level | {{ blower_sound_level_dba }} dBA |
| Header sound level | {{ header_sound_level_dba }} dBA |
| Enclosure sound level | {{ enclosure_sound_level_dba }} dBA |
| Receiver distance | {{ receiver_distance_m }} m |
| Receiver criterion | {{ receiver_criterion_dba }} dBA |

## Calculation Rules

- BOD removed equals `flow_rate_m3_d x (influent_bod_mg_l - effluent_bod_mg_l) / 1000`.
- Nitrogen removed equals `flow_rate_m3_d x (influent_tkn_mg_l - effluent_tkn_mg_l) / 1000`.
- Oxygen demand equals `max(bod_removed - 1.42 x sludge_production + 4.57 x nitrogen_removed - 2.86 x denitrified_nitrogen, 0)`.
- Required airflow uses `air_oxygen_mass_fraction x air_density_kg_m3 x field_transfer_efficiency`.
- Blower input power equals `(required_airflow_m3_min / 60) x blower_discharge_pressure_kpa / blower_efficiency / motor_efficiency`.
- Combine source sound levels with logarithmic summation, then subtract `20 x log10(receiver_distance_m)` at the receiver.
- Overall pass score is `1.0` only when blower oxygen capacity, motor margin, and acoustic margin are non-negative.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the source IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated BioWin/GPS-X/SUMO evidence, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "bod_removed_kg_d": <numeric_value>,
  "nitrogen_removed_kg_d": <numeric_value>,
  "oxygen_demand_kg_d": <numeric_value>,
  "required_airflow_m3_min": <numeric_value>,
  "blower_oxygen_capacity_margin_kg_d": <numeric_value>,
  "blower_input_power_kw": <numeric_value>,
  "motor_margin_kw": <numeric_value>,
  "combined_source_spl_dba": <numeric_value>,
  "receiver_spl_dba": <numeric_value>,
  "acoustic_margin_db": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
