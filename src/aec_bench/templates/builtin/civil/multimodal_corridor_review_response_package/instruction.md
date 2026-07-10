You are a corridor package reviewer checking a task-owned synthetic SSC-01 multimodal corridor review response.

Use only the task-owned synthetic source pack values below for numeric grading. Road, drainage, traffic, ITS, and electrical review workflows shape the context only; they are not extra data sources for this instance.

## Scene

- Product: `SSC-01-LH-08`
- Review comment register: `REV-SSC01-008`
- Marked-up corridor plan: `MARKUP-SSC01-008`
- Revised drainage calculation: `DRAIN-SSC01-008`
- Revised signal and pedestrian timing sheet: `SIG-SSC01-008`
- Revised feeder schedule: `FEED-SSC01-008`
- Response memo: `MEMO-SSC01-008`

## Source Values

- Original and revised chainage: {{ original_chainage_m }} m and {{ revised_chainage_m }} m
- Revised road level and HGL: {{ revised_road_level_m }} m and {{ revised_hgl_m }} m
- Minimum HGL clearance: {{ minimum_hgl_clearance_mm }} mm
- Pedestrian startup, crossing width, walk speed, and available clearance: {{ pedestrian_startup_time_s }} s, {{ revised_crossing_width_m }} m, {{ pedestrian_walk_speed_m_s }} m/s, {{ available_ped_clearance_s }} s
- VMS character height, approach speed, reading rate, and message length: {{ vms_character_height_in }} in, {{ approach_speed_kmh }} km/h, {{ reading_rate_chars_s }} chars/s, {{ revised_message_length_chars }} chars
- Revised device load: {{ revised_device_load_w }} W
- Feeder length, resistance, voltage, power factor, and voltage-drop limit: {{ feeder_length_km }} km, {{ conductor_resistance_ohm_km }} ohm/km, {{ feeder_voltage_v }} V, {{ power_factor }}, {{ allowable_voltage_drop_pct }} %
- Review comments closed/total: {{ review_comments_closed }} / {{ review_comments_total }}
- Impacted calculations: {{ impacted_calculation_count }}

## Required Calculations

- Changed chainage delta is revised chainage minus original chainage.
- HGL clearance is revised road level minus revised HGL, converted to mm.
- Pedestrian clearance required is startup time plus crossing width divided by walk speed.
- VMS reading time is character height times 40 ft/in, converted to metres, divided by approach speed.
- Feeder voltage drop is `2 x length x resistance x current / voltage x 100`.
- Comment closeout percent is closed comments divided by total comments.
- Overall pass score is `1.0` only when drainage, pedestrian, VMS, voltage, and review-closeout checks pass.

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the source IDs above and state that the baseline source pack passes the current synthetic checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable source-pack hardening, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "changed_chainage_delta_m": <numeric_value>,
  "hgl_clearance_mm": <numeric_value>,
  "hgl_clearance_margin_mm": <numeric_value>,
  "ped_clearance_required_s": <numeric_value>,
  "ped_clearance_margin_s": <numeric_value>,
  "vms_reading_time_s": <numeric_value>,
  "vms_message_margin_chars": <numeric_value>,
  "feeder_voltage_drop_percent": <numeric_value>,
  "voltage_drop_margin_percent": <numeric_value>,
  "comment_closeout_percent": <numeric_value>,
  "impacted_calculation_count": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
