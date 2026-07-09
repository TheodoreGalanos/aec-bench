You are an electrical/building-services engineer checking a task-owned synthetic SSC-08 room occupancy, lighting energy, and access-control package.

Use only the task-owned synthetic source pack values shown below for numeric grading. External room occupancy, lumen-method lighting, lighting energy, access-control, and operations-memo workflows shape the practice context only; they are not extra data sources for this instance.

## Scene

- Product family: `SSC-08-LH-02`
- Room plan: `ROOM-08-PLAN-02`
- Occupancy schedule: `OCC-08-SCHED-02`
- Lighting layout: `LGT-08-LAYOUT-02`
- Access device list: `ACC-08-DEV-02`
- Energy profile: `ENERGY-08-PROFILE-02`
- Room operations memo: `MEMO-08-ROOM-02`

## Source Values

| Item | Value |
|------|-------|
| Room area | {{ room_area_m2 }} m2 |
| Area per occupant | {{ area_per_occupant_m2 }} m2/person |
| Luminaire lumens | {{ luminaire_lumens }} lm |
| Luminaire count | {{ luminaire_count }} |
| Light loss factor | {{ light_loss_factor }} |
| Utilization factor | {{ utilization_factor }} |
| Minimum illuminance | {{ minimum_illuminance_lux }} lux |
| Target illuminance | {{ target_illuminance_lux }} lux |
| Minimum uniformity ratio | {{ minimum_uniformity_ratio }} |
| Luminaire power | {{ luminaire_power_w }} W |
| Operating hours | {{ operating_hours_per_year }} h/y |
| Maximum LENI | {{ max_leni_kwh_m2_y }} kWh/m2-y |
| Access door count | {{ access_door_count }} |
| Readers per door | {{ readers_per_door }} |
| Controller reader capacity | {{ controller_reader_capacity }} |
| Reader load | {{ reader_load_w }} W |
| Controller panel load | {{ controller_panel_load_w }} W |
| Backup runtime | {{ backup_runtime_h }} h |
| Battery derate factor | {{ battery_derate_factor }} |

## Checks

- Design occupants equal the ceiling of room area divided by area per occupant.
- Average illuminance equals luminaire lumens times luminaire count times light loss factor times utilization factor divided by room area.
- Illuminance margin equals average illuminance minus target illuminance.
- Uniformity ratio equals minimum illuminance divided by average illuminance.
- Lighting power density equals luminaire power times luminaire count divided by room area.
- LENI equals annual lighting energy divided by room area.
- Access reader count equals access doors times readers per door.
- Access spare points equal controller reader capacity minus reader count.
- Access battery required equals access-control load times backup runtime divided by battery derate factor.
- Overall pass score is `1.0` only when illuminance, uniformity, LENI, and access-controller checks pass; otherwise it is `0.0`.

## Output Format

Write a compact room operations memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the object IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "design_occupants": <numeric_value>,
  "average_illuminance_lux": <numeric_value>,
  "illuminance_margin_lux": <numeric_value>,
  "uniformity_ratio": <numeric_value>,
  "lighting_power_density_w_m2": <numeric_value>,
  "leni_kwh_m2_y": <numeric_value>,
  "access_reader_count": <numeric_value>,
  "access_controller_spare_points": <numeric_value>,
  "access_battery_required_wh": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
