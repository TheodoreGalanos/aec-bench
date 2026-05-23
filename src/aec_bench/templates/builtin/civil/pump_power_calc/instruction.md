You are a senior civil engineer specializing in water infrastructure and pump station design.

## Problem

Calculate the required pump power for a water/wastewater pump station at a given duty point. Determine the hydraulic power, brake (shaft) power, and motor input (electrical) power.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Flow rate (Q) | {{ flow_rate_l_s }} | L/s |
| Total dynamic head (H) | {{ total_dynamic_head_m }} | m |
{%- if pump_efficiency_pct is defined %}
| Pump efficiency (η_pump) | {{ pump_efficiency_pct }} | % |
{%- endif %}
{%- if motor_efficiency_pct is defined %}
| Motor efficiency (η_motor) | {{ motor_efficiency_pct }} | % |
{%- endif %}
{% if archetype_description is defined %}

### Station Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A pump power calculation tool is available at `/workspace/pump-power-calc_calc.py`. Run it with:

```bash
python3 /workspace/pump-power-calc_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Hydraulic (water) power P_h (kW)
2. Brake (shaft) power P_b (kW)
3. Motor input (electrical) power P_m (kW)

## Applicable Standards

- AWWA -- American Water Works Association pump station references
- Hydraulics Institute -- pump performance and efficiency standards

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the following formulas:
  - Convert flow rate from L/s to m^3/s: Q_m3s = Q / 1000
  - Hydraulic power: P_h = rho x g x Q x H / 1000 (kW)
  - Brake (shaft) power: P_b = P_h / eta_pump
  - Motor input power: P_m = P_b / eta_motor
- Physical constants: rho = 998 kg/m^3 (water density), g = 9.81 m/s^2
- Efficiencies are given as percentages and must be converted to decimals before use (e.g., 75% = 0.75)
- If pump or motor efficiency is not provided, estimate from the station description and pump type

## Output Format

Show your step-by-step working in Markdown, including the unit conversion, hydraulic power calculation, brake power calculation, and motor input power calculation. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "hydraulic_power_kw": <numeric_value>,
  "brake_power_kw": <numeric_value>,
  "motor_input_power_kw": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
