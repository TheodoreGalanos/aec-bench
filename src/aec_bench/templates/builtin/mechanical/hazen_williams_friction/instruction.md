You are a senior mechanical engineer specializing in hydraulic pipe calculations.

## Task

Calculate the Hazen-Williams friction loss for the pressurised water pipe in {{ site_context }}.

## Given

| Parameter | Value | Unit |
| --- | ---: | --- |
| Pipe length | {{ pipe_length_m }} | m |
| Internal pipe diameter | {{ pipe_internal_diameter_mm }} | mm |
| Flow rate | {{ flow_rate_l_s }} | L/s |
| Hazen-Williams C value | {{ hazen_williams_c }} | - |
| Fluid density | {{ fluid_density_kg_m3 }} | kg/m3 |

## Constraints

- No internet access is available.
- Use the Hazen-Williams equation in SI form: `h_f = 10.67 L Q^1.852 / (C^1.852 d^4.871)`.
- Convert flow from L/s to m3/s and diameter from mm to m before calculating head loss.
- Use `g = 9.81 m/s2` for pressure conversion.

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

- Flow rate in cubic metres per second (`flow_rate_m3_s`)
- Friction head loss (`head_loss_m`)
- Equivalent pressure loss (`pressure_loss_kpa`)
- Hydraulic gradient (`hydraulic_gradient_m_per_m`)

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "flow_rate_m3_s": <numeric_value>,
  "head_loss_m": <numeric_value>,
  "pressure_loss_kpa": <numeric_value>,
  "hydraulic_gradient_m_per_m": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
