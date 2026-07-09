You are a structural engineer checking a task-owned synthetic SSC-14 equipment skid, support, and vibration package.

Use only the task-owned synthetic source pack values below for numeric grading. Equipment support, vibration, fatigue, and foundation workflows shape the context only; they are not extra data sources for this instance.

## Scene

- Product: `SSC-14-LH-03`
- Equipment layout: `EQP-SSC14-003`
- Mass and duty schedule: `MASS-SSC14-003`
- Support/foundation detail: `FDN-SSC14-003`
- Vibration and isolation data: `VIB-SSC14-003`
- Equipment support memo: `MEMO-SSC14-003`

## Source Values

- Equipment mass and dynamic allowance: {{ equipment_mass_kg }} kg and {{ dynamic_allowance_factor }}
- Support count and reaction load factor: {{ support_count }} and {{ reaction_load_factor }}
- Foundation self-weight, length, width, and allowable bearing: {{ foundation_self_weight_kn }} kN, {{ foundation_length_m }} m, {{ foundation_width_m }} m, {{ allowable_bearing_kpa }} kPa
- Operating and natural frequencies: {{ operating_frequency_hz }} Hz and {{ support_natural_frequency_hz }} Hz
- Damping ratio: {{ damping_ratio }}
- Fatigue basis: {{ cycles_per_day }} cycles/day, {{ design_life_days }} days, stress range {{ stress_range_mpa }} MPa, constant {{ fatigue_constant }}, exponent {{ fatigue_exponent }}
- Support factored capacity: {{ support_factored_capacity_kn }} kN

## Required Calculations

- Equipment weight is `mass x 9.81 / 1000`.
- Service support reaction is `equipment_weight x dynamic_allowance / support_count`.
- Factored support reaction is service reaction times the reaction load factor.
- Bearing pressure is `(equipment_weight + foundation_self_weight) / foundation_area`.
- Frequency ratio is operating frequency divided by natural frequency.
- Transmissibility is `sqrt(1 + (2 zeta r)^2) / sqrt((1 - r^2)^2 + (2 zeta r)^2)`.
- Fatigue damage ratio is `cycles x stress_range^exponent / fatigue_constant`.
- Overall pass score is `1.0` only when bearing utilization, fatigue damage, and support capacity margin pass.

Write a compact equipment support memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the source IDs above and state whether the baseline source pack passes the current synthetic checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

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
