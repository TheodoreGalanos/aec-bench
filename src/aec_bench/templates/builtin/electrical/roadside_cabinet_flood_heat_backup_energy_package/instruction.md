You are a roadside electrical resilience engineer checking a task-owned synthetic SSC-01 cabinet flood, heat, and backup energy package.

Use only the task-owned synthetic source pack values below for numeric grading. Cabinet siting, drainage HGL, thermal derating, feeder, and battery/BESS workflows shape the context only; they are not extra data sources for this instance.

## Scene

- Product: `SSC-01-LH-07`
- Cabinet setout: `CAB-SSC01-007`
- HGL or inundation table: `HGL-SSC01-007`
- Heat derating note: `HEAT-SSC01-007`
- Critical load schedule: `LOAD-SSC01-007`
- Battery schedule: `BATT-SSC01-007`
- Resilience memo: `MEMO-SSC01-007`

## Source Values

- Cabinet pad, HGL, and inundation levels: {{ cabinet_pad_level_m }} m, {{ hgl_level_m }} m, {{ inundation_level_m }} m
- Minimum freeboard: {{ minimum_freeboard_m }} m
- Enclosure capacity at reference temperature: {{ enclosure_capacity_w_at_reference_temp }} W at {{ reference_temperature_c }} C
- Event temperature and derating rate: {{ event_temperature_c }} C and {{ derate_pct_per_c }} % per C
- Critical load: {{ critical_load_w }} W
- Battery capacity, efficiency, and required backup duration: {{ battery_capacity_kwh }} kWh, {{ battery_efficiency }}, {{ required_backup_h }} h
- BESS inverter capacity: {{ bess_inverter_capacity_kw }} kW
- Feeder length, resistance, voltage, power factor, and voltage-drop limit: {{ feeder_length_km }} km, {{ conductor_resistance_ohm_km }} ohm/km, {{ feeder_voltage_v }} V, {{ power_factor }}, {{ allowable_voltage_drop_pct }} %
- Road lighting power, annual hours, and lit area: {{ road_lighting_power_w }} W, {{ annual_operating_hours }} h/y, {{ lit_area_m2 }} m2

## Required Calculations

- Cabinet freeboard is pad level minus the greater of HGL and inundation level.
- Flood freeboard margin is cabinet freeboard minus minimum freeboard.
- Thermal derated capacity is reference capacity times the temperature derating factor.
- Battery runtime is `capacity x efficiency / (critical load / 1000)`.
- BESS energy margin is usable battery energy minus required backup energy.
- Feeder voltage drop is `2 x length x resistance x current / voltage x 100`.
- Road-lighting AECI is annual lighting energy divided by lit area.
- Overall pass score is `1.0` only when flood, thermal, battery/BESS, and voltage-drop margins pass.

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the source IDs above and state that the baseline source pack passes the current synthetic checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable source-pack hardening, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "cabinet_freeboard_m": <numeric_value>,
  "flood_freeboard_margin_m": <numeric_value>,
  "thermal_derated_capacity_w": <numeric_value>,
  "thermal_margin_w": <numeric_value>,
  "thermal_utilization": <numeric_value>,
  "battery_runtime_h": <numeric_value>,
  "battery_margin_h": <numeric_value>,
  "bess_power_margin_kw": <numeric_value>,
  "bess_energy_margin_kwh": <numeric_value>,
  "feeder_voltage_drop_percent": <numeric_value>,
  "voltage_drop_margin_percent": <numeric_value>,
  "road_lighting_aeci_kwh_m2_y": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
