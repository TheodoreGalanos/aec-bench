You are a senior wireless systems engineer checking an RF link budget.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Transmit power | {{ transmit_power_dbm }} | dBm |
| Transmit antenna gain | {{ transmit_antenna_gain_dbi }} | dBi |
| Link distance | {{ distance_m }} | m |
| Frequency | {{ frequency_ghz }} | GHz |
| Receive antenna gain | {{ receive_antenna_gain_dbi }} | dBi |
{% if obstacle_losses_db is defined %}
| Obstacle losses | {{ obstacle_losses_db }} | dB |
{% endif %}
| Required receive sensitivity | {{ required_receive_sensitivity_dbm }} | dBm |

## Constraints

- Use `FSPL = 32.44 + 20 log10(distance_km) + 20 log10(frequency_MHz)`.
- Total path loss equals free-space path loss plus obstacle losses.
- Received signal equals transmit power plus antenna gains minus total path loss.
- Link margin equals received signal minus required receive sensitivity.

## Output Format

Include a JSON block with exactly these keys:

```json
{
  "free_space_path_loss_db": <numeric_value>,
  "total_path_loss_db": <numeric_value>,
  "received_signal_level_dbm": <numeric_value>,
  "link_margin_db": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
