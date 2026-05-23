You are a senior mechanical engineer specializing in pump power and motor sizing.

## Task

Calculate the pump power and recommended motor size for the duty in {{ site_context }}.

## Given

| Parameter | Value | Unit |
| --- | ---: | --- |
| Flow rate | {{ flow_rate_m3_h }} | m3/h |
| Total dynamic head | {{ total_dynamic_head_m }} | m |
| Fluid density | {{ fluid_density_kg_m3 }} | kg/m3 |
| Pump efficiency | {{ pump_efficiency_pct }} | % |
| Motor efficiency | {{ motor_efficiency_pct }} | % |
| Motor sizing factor | {{ motor_sizing_factor }} | - |

## Constraints

- No internet access is available.
- Convert flow from m3/h to m3/s.
- Use `P_h = rho g Q H / 1000` for hydraulic power in kW.
- Use `shaft power = hydraulic power / pump efficiency`.
- Use `motor input power = shaft power / motor efficiency`.
- Use `recommended motor size = motor input power * motor sizing factor`.

{% if tool_available %}
## Available Tool

A calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate:

- Hydraulic power (`hydraulic_power_kw`)
- Pump shaft power (`shaft_power_kw`)
- Motor input power (`motor_input_power_kw`)
- Recommended motor size (`recommended_motor_size_kw`)

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "hydraulic_power_kw": <numeric_value>,
  "shaft_power_kw": <numeric_value>,
  "motor_input_power_kw": <numeric_value>,
  "recommended_motor_size_kw": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
