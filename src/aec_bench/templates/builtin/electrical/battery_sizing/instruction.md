You are a senior electrical engineer sizing backup battery capacity.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Critical load | {{ critical_load_w }} | W |
| Required autonomy | {{ required_autonomy_h }} | h |
| DC system voltage | {{ system_voltage_v }} | V |
| Depth of discharge | {{ depth_of_discharge_pct }} | % |
{% if temperature_derating_factor is defined %}
| Temperature derating factor | {{ temperature_derating_factor }} | - |
{% endif %}
| Inverter efficiency | {{ inverter_efficiency_pct }} | % |
| Load power factor | {{ load_power_factor }} | - |
| Battery block voltage | {{ battery_block_voltage_v }} | V |

## Constraints

- Required energy equals critical load times autonomy duration.
- Battery Ah equals load watt-hours divided by system voltage and all usable-capacity factors.
- Usable factors are depth of discharge, temperature derating, and inverter efficiency.
- UPS VA equals critical load divided by load power factor.
- Battery block count equals the ceiling of system voltage divided by block voltage.

## Output Format

Include a JSON block with exactly these keys:

```json
{
  "required_energy_kwh": <numeric_value>,
  "required_battery_capacity_ah": <numeric_value>,
  "ups_rating_va": <numeric_value>,
  "battery_block_count": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
