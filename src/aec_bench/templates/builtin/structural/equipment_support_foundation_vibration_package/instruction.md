You are a structural equipment engineer checking a task-owned synthetic SSC-06 equipment support, foundation, and vibration package.

Use only the task-owned synthetic source pack values shown below for numeric grading. Equipment layout, support, isolator, fatigue, and load-combination workflows shape the context only; this instance does not run external software or parse a real source pack.

## Scene

- Product: `SSC-06-LH-04`
- Equipment layout: `LAYOUT-06-SKID-04`
- Mass and support schedule: `MASS-06-SCHED-04`
- Foundation sketch: `FOUNDATION-06-BASE-04`
- Vibration isolator data: `ISO-06-VIB-04`
- Load-case table: `LOAD-06-COMB-04`
- Installation memo: `MEMO-06-INSTALL-04`

## Source Values

| Item | Value |
| --- | --- |
| Equipment mass | {{ equipment_mass_kg }} kg |
| Dynamic allowance factor | {{ dynamic_allowance_factor }} |
| Support count | {{ support_count }} |
| Reaction load factor | {{ reaction_load_factor }} |
| Foundation self-weight | {{ foundation_self_weight_kn }} kN |
| Foundation length | {{ foundation_length_m }} m |
| Foundation width | {{ foundation_width_m }} m |
| Allowable bearing pressure | {{ allowable_bearing_kpa }} kPa |
| Operating frequency | {{ operating_frequency_hz }} Hz |
| Support natural frequency | {{ support_natural_frequency_hz }} Hz |
| Damping ratio | {{ damping_ratio }} |
| Cycles per day | {{ cycles_per_day }} |
| Design life | {{ design_life_days }} days |
| Stress range | {{ stress_range_mpa }} MPa |
| Fatigue constant | {{ fatigue_constant }} |
| Fatigue exponent | {{ fatigue_exponent }} |
| Support factored capacity | {{ support_factored_capacity_kn }} kN |

## Calculation Rules

- Equipment weight equals `equipment_mass_kg x 9.81 / 1000`.
- Support service reaction equals equipment weight times dynamic allowance divided by support count.
- Factored support reaction equals support service reaction times reaction load factor.
- Bearing pressure equals `(equipment weight + foundation self-weight) / (foundation length x foundation width)`.
- Bearing utilization equals bearing pressure divided by allowable bearing pressure.
- Frequency ratio equals operating frequency divided by support natural frequency.
- Vibration transmissibility uses the damped single-degree expression with frequency ratio and damping ratio.
- Transmitted dynamic force equals support service reaction times vibration transmissibility.
- Fatigue damage ratio equals `cycles_per_day x design_life_days x stress_range_mpa^fatigue_exponent / fatigue_constant`.
- Load-combination margin equals support factored capacity minus factored support reaction.
- Overall pass score is `1.0` only when bearing, fatigue, and support-capacity checks pass.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the source IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated modelling evidence, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "support_service_reaction_kn": <numeric_value>,
  "factored_support_reaction_kn": <numeric_value>,
  "bearing_pressure_kpa": <numeric_value>,
  "bearing_utilization": <numeric_value>,
  "frequency_ratio": <numeric_value>,
  "vibration_transmissibility": <numeric_value>,
  "transmitted_dynamic_force_kn": <numeric_value>,
  "fatigue_damage_ratio": <numeric_value>,
  "load_combination_margin_kn": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
