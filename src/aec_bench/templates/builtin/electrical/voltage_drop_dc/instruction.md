# ABOUTME: Prompt template for DC solar string voltage-drop tasks.
# ABOUTME: Presents current, length, cable size, resistivity, voltage, and hours.

You are a senior solar PV electrical engineer checking DC string cable voltage drop.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| String current at maximum power | {{ string_current_a }} | A |
| One-way DC cable length | {{ dc_cable_length_m }} | m |
| Cable cross-section | {{ cable_cross_section_mm2 }} | mm2 |
| Cable resistivity | {{ cable_resistivity_ohm_mm2_m }} | ohm.mm2/m |
| String voltage | {{ string_voltage_v }} | V |
| Annual operating hours | {{ annual_operating_hours }} | h/year |
| Maximum voltage drop | {{ maximum_voltage_drop_pct }} | % |

## Constraints

- Use a two-way DC loop resistance equal to `2 * length * resistivity / cross-section`.
- Voltage drop equals string current times loop resistance.
- Voltage drop percentage equals voltage drop divided by string voltage times 100.
- Annual energy loss equals current times voltage drop times annual operating hours divided by 1000.
- Voltage drop margin equals maximum voltage drop percentage minus calculated voltage drop percentage.

## Output Format

Include a JSON block with exactly these keys:

```json
{
  "voltage_drop_v": <numeric_value>,
  "voltage_drop_pct": <numeric_value>,
  "annual_energy_loss_kwh": <numeric_value>,
  "voltage_drop_margin_pct": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
