You are a senior mechanical engineer specializing in building water hydraulics.

## Task

Calculate the pressure loss through the water pipework in {{ site_context }}.

## Given

| Parameter | Value | Unit |
| --- | ---: | --- |
| Flow rate | {{ flow_rate_l_s }} | L/s |
| Internal pipe diameter | {{ pipe_internal_diameter_mm }} | mm |
| Pipe length | {{ pipe_length_m }} | m |
| Hazen-Williams C value | {{ hazen_williams_c }} | - |
| Total fitting K value | {{ total_fitting_k }} | - |
| Fluid density | {{ fluid_density_kg_m3 }} | kg/m3 |

## Constraints

- No internet access is available.
- Use `h_f = 10.67 L Q^1.852 / (C^1.852 d^4.871)` with Q in m3/s and d in m.
- Use `h_k = K v^2 / (2g)` for fittings and valves.
- Use `g = 9.81 m/s2`.
- Convert pressure losses from head using `delta_p = rho g h`.

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

- Pipe velocity (`velocity_m_s`)
- Straight-pipe friction pressure loss (`friction_loss_kpa`)
- Fitting and valve pressure loss (`fitting_loss_kpa`)
- Total pipe pressure loss (`total_pressure_loss_kpa`)

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "velocity_m_s": <numeric_value>,
  "friction_loss_kpa": <numeric_value>,
  "fitting_loss_kpa": <numeric_value>,
  "total_pressure_loss_kpa": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
