You are a senior distribution engineer calculating radial feeder voltage drop.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Feeder resistance | {{ feeder_resistance_ohm_per_km }} | ohm/km |
| Feeder reactance | {{ feeder_reactance_ohm_per_km }} | ohm/km |
| Feeder length | {{ feeder_length_km }} | km |
| Real load | {{ load_real_power_kw }} | kW |
{% if load_reactive_power_kvar is defined %}
| Reactive load | {{ load_reactive_power_kvar }} | kVAr |
{% endif %}
| Source voltage | {{ source_voltage_v }} | V |

## Constraints

- Treat the feeder as a single balanced three-phase section.
- Calculate feeder current from apparent power and source voltage.
- Use the approximate drop `sqrt(3) I (R cos phi + X sin phi)`.
- Receiving voltage equals source voltage minus voltage drop.
- Feeder loss equals `3 I^2 R_total`.

## Output Format

Include a JSON block with exactly these keys:

```json
{
  "feeder_current_a": <numeric_value>,
  "voltage_drop_v": <numeric_value>,
  "voltage_drop_pct": <numeric_value>,
  "receiving_end_voltage_v": <numeric_value>,
  "feeder_loss_kw": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
