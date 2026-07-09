You are a mechanical process engineer checking a task-owned synthetic SSC-06 blower process, energy, and acoustic impact package.

Use only the task-owned synthetic source pack values shown below for numeric grading. Process modelling, blower selection, motor scheduling, and acoustic receiver workflows shape the context only; this instance does not run external software or parse a real source pack.

## Scene

- Product: `SSC-06-LH-02`
- Process load basis: `PROCESS-06-BLOWER-02`
- Blower data sheet: `BLOWER-06-DATA-02`
- Motor schedule: `MOTOR-06-SCHED-02`
- Receiver plan: `RECEIVER-06-PLAN-02`
- Acoustic criterion: `ACOUSTIC-06-CRIT-02`
- Process/acoustic memo: `MEMO-06-PROCESS-02`

## Source Values

| Item | Value |
| --- | --- |
| Influent flow | {{ influent_flow_mld }} ML/d |
| BOD | {{ bod_mg_l }} mg/L |
| Ammonia | {{ ammonia_mg_l }} mg/L |
| BOD oxygen factor | {{ bod_oxygen_factor }} |
| Nitrification oxygen factor | {{ nitrification_oxygen_factor }} |
| Blower air volume | {{ blower_air_m3_per_kg_o2 }} m3/kg O2 |
| Blower discharge pressure | {{ blower_discharge_pressure_kpa }} kPa |
| Blower efficiency | {{ blower_efficiency }} |
| Motor efficiency | {{ motor_efficiency }} |
| Selected motor size | {{ selected_motor_kw }} kW |
| Source sound level | {{ source_sound_power_dba }} dBA |
| Receiver distance | {{ receiver_distance_m }} m |
| Enclosure insertion loss | {{ enclosure_insertion_loss_db }} dB |
| Receiver criterion | {{ receiver_criterion_dba }} dBA |

## Calculation Rules

- Oxygen demand equals `flow_m3_d x (bod_mg_l x bod_oxygen_factor + ammonia_mg_l x nitrification_oxygen_factor) / 1000`, where `flow_m3_d = influent_flow_mld x 1000`.
- Required airflow equals `oxygen_demand_kg_d x blower_air_m3_per_kg_o2 / (24 x 60)`.
- Blower shaft power equals `(required_airflow_m3_min / 60) x blower_discharge_pressure_kpa x 1000 / blower_efficiency / 1000`.
- Motor input power equals blower shaft power divided by motor efficiency.
- Motor size margin equals selected motor size minus motor input power.
- Distance attenuation equals `20 x log10(receiver_distance_m)`.
- Receiver SPL equals source sound level minus distance attenuation minus enclosure insertion loss.
- Criterion margin equals receiver criterion minus receiver SPL.
- Overall pass score is `1.0` only when motor size and acoustic criterion margins are non-negative.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the source IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated modelling evidence, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "oxygen_demand_kg_d": <numeric_value>,
  "required_airflow_m3_min": <numeric_value>,
  "blower_shaft_power_kw": <numeric_value>,
  "motor_input_power_kw": <numeric_value>,
  "motor_size_margin_kw": <numeric_value>,
  "distance_attenuation_db": <numeric_value>,
  "receiver_spl_dba": <numeric_value>,
  "criterion_margin_db": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
