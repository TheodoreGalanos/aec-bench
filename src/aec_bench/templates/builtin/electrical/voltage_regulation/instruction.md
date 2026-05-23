You are a senior power systems engineer calculating line voltage regulation.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Line resistance | {{ line_resistance_ohm_per_km }} | ohm/km |
| Line reactance | {{ line_reactance_ohm_per_km }} | ohm/km |
| Line length | {{ line_length_km }} | km |
| Real load | {{ load_real_power_mw }} | MW |
{% if load_reactive_power_mvar is defined %}
| Reactive load | {{ load_reactive_power_mvar }} | MVAr |
{% endif %}
| Sending-end voltage | {{ sending_voltage_kv }} | kV |

## Constraints

- Use total R and X over the full line length.
- Use the approximate drop formula `deltaV_kV = (R_total P_MW + X_total Q_MVAr) / V_kV`.
- Voltage regulation equals `deltaV / sending_voltage x 100`.
- Receiving voltage equals sending voltage minus voltage drop.
- Estimate three-phase real power loss using line current from apparent power.

## Output Format

Include a JSON block with exactly these keys:

```json
{
  "voltage_drop_kv": <numeric_value>,
  "voltage_regulation_pct": <numeric_value>,
  "receiving_end_voltage_kv": <numeric_value>,
  "power_loss_mw": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
