You are a building services and life-safety engineer checking a task-owned synthetic SSC-08 station population, vertical movement, egress, alarm, and ventilation package for one concourse zone.

Use only the task-owned synthetic source pack values shown below for numeric grading. External NFPA 101, IBC, NFPA 72, Pathfinder, MassMotion, and NIST FDS/Smokeview routes shape the workflow context only; they are not extra data sources for this instance.

## Scene

- Station case ledger: `CASE-SSC08-STATION-001`
- Floor/zone model: `ZONE-08-CONCOURSE-L1`
- Population and peak scenario schedule: `POP-08-PEAK-001`
- Egress route register: `EGRESS-08-ROUTE-A`
- Escalator group schedule: `ESC-08-UP-01`
- Lift group schedule: `LIFT-08-GROUP-01`
- Emergency ventilation schedule: `VENT-08-SMOKE-01`
- Fire alarm NAC schedule: `NAC-08-ALARM-01`
- Life-safety operations memo: `MEMO-08-OPS-01`

All checks use the same `ZONE-08-CONCOURSE-L1` and `POP-08-PEAK-001` scenario. Do not change the population, egress route, vertical-transport assets, alarm circuit, or ventilation case unless you explicitly flag a source conflict.

Unit convention for this source pack:

- Occupancy is in persons.
- Egress width is in millimetres unless converted to metres for flow time.
- Five-minute capacities are persons per 5 minutes; hourly escalator capacity divided by 12 gives persons per 5 minutes.
- NAC appliance quantities are counts and currents are amps.

## Population And Egress Basis

| Item | Value |
|------|-------|
| Concourse net floor area | {{ floor_area_m2 }} m2 |
| Area per occupant | {{ area_per_occupant_m2 }} m2/person |
| Egress width factor | {{ egress_width_per_occupant_mm }} mm/person |
| Provided egress width | {{ provided_egress_width_mm }} mm |
| Maximum egress flow time | {{ max_egress_time_s }} s |
| Egress flow rate | {{ egress_flow_rate_persons_per_m_s }} persons/(m*s) |

Population and egress checks:

- Calculated occupants equal `floor_area_m2 / area_per_occupant_m2`.
- Design occupants equal the ceiling of calculated occupants.
- Occupant density equals `design_occupants / floor_area_m2`.
- Required egress width equals `design_occupants x egress_width_per_occupant_mm`.
- Egress width margin equals `provided_egress_width_mm - required_egress_width_mm`.
- Egress width utilization equals `required_egress_width_mm / provided_egress_width_mm`.
- Egress flow time equals `design_occupants / ((provided_egress_width_mm / 1000) x egress_flow_rate_persons_per_m_s)`.
- Egress time margin equals `max_egress_time_s - egress_flow_time_s`.

## Vertical Movement Basis

| Item | Value |
|------|-------|
| Peak vertical demand | {{ peak_vertical_demand_persons_per_5min }} persons/5min |
| Escalator speed | {{ escalator_speed_m_s }} m/s |
| Escalator step width | {{ escalator_step_width_mm }} mm |
| Escalator step pitch | {{ escalator_step_pitch_mm }} mm |
| Escalator practical loading factor | {{ escalator_loading_factor_percent }} percent |
| Lift round-trip time | {{ lift_round_trip_time_s }} s |
| Lift car capacity | {{ lift_car_capacity_persons }} persons |
| Lift count | {{ lift_count }} |
| Lift loading factor | {{ lift_loading_factor_percent }} percent |
| Required lift handling capacity | {{ required_lift_handling_percent }} percent |

Vertical movement checks:

- Escalator steps per second equal `escalator_speed_m_s / (escalator_step_pitch_mm / 1000)`.
- Escalator persons per step equals `2.0` for this 1000 mm source step width.
- Escalator practical capacity per hour equals `steps_per_second x persons_per_step x 3600 x escalator_loading_factor_percent / 100`.
- Escalator capacity per 5 minutes equals hourly capacity divided by `12`.
- Lift loaded car capacity equals `lift_car_capacity_persons x lift_loading_factor_percent / 100`.
- Lift passengers per 5 minutes equals `300 x lift_count x lift_loaded_car_capacity / lift_round_trip_time_s`.
- Lift handling capacity percent equals `lift_passengers_per_5min / design_occupants x 100`.
- Lift handling margin percent equals `lift_handling_capacity_percent - required_lift_handling_percent`.
- Vertical capacity per 5 minutes equals `escalator_capacity_persons_per_5min + lift_passengers_per_5min`.
- Vertical capacity margin equals `vertical_capacity_persons_per_5min - peak_vertical_demand_persons_per_5min`.

## Alarm And Ventilation Basis

| Item | Value |
|------|-------|
| Emergency ventilation airflow | {{ ventilation_airflow_m3_h }} m3/h |
| Concourse volume | {{ concourse_volume_m3 }} m3 |
| Required air changes | {{ required_air_changes_per_h }} 1/h |
| NAC strobe quantity | {{ nac_strobe_quantity }} |
| NAC strobe current | {{ nac_strobe_current_a }} A |
| NAC horn quantity | {{ nac_horn_quantity }} |
| NAC horn current | {{ nac_horn_current_a }} A |
| NAC speaker quantity | {{ nac_speaker_quantity }} |
| NAC speaker current | {{ nac_speaker_current_a }} A |
| NAC circuit capacity | {{ nac_circuit_capacity_a }} A |

Alarm and ventilation checks:

- Ventilation air changes per hour equal `ventilation_airflow_m3_h / concourse_volume_m3`.
- Ventilation ACH margin equals `ventilation_air_changes_per_h - required_air_changes_per_h`.
- NAC total load equals `strobe_quantity x strobe_current + horn_quantity x horn_current + speaker_quantity x speaker_current`.
- NAC spare capacity equals `nac_circuit_capacity_a - nac_total_load_a`.
- NAC utilization percent equals `nac_total_load_a / nac_circuit_capacity_a x 100`.
- Overall pass score is `1.0` only when egress width margin, egress time margin, vertical capacity margin, lift handling margin, ventilation ACH margin, and NAC spare capacity are all non-negative; otherwise it is `0.0`.

## Output Format

Write a compact life-safety operations memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Explain the calculations briefly, preserve the object IDs above, and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "calculated_occupants": <numeric_value>,
  "design_occupants": <numeric_value>,
  "occupant_density_person_m2": <numeric_value>,
  "required_egress_width_mm": <numeric_value>,
  "egress_width_margin_mm": <numeric_value>,
  "egress_width_utilization": <numeric_value>,
  "egress_flow_time_s": <numeric_value>,
  "egress_time_margin_s": <numeric_value>,
  "escalator_practical_capacity_persons_per_h": <numeric_value>,
  "escalator_capacity_persons_per_5min": <numeric_value>,
  "lift_passengers_per_5min": <numeric_value>,
  "lift_handling_capacity_percent": <numeric_value>,
  "lift_handling_margin_percent": <numeric_value>,
  "vertical_capacity_persons_per_5min": <numeric_value>,
  "vertical_capacity_margin_persons_per_5min": <numeric_value>,
  "ventilation_air_changes_per_h": <numeric_value>,
  "ventilation_ach_margin": <numeric_value>,
  "nac_total_load_a": <numeric_value>,
  "nac_spare_capacity_a": <numeric_value>,
  "nac_utilization_percent": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
