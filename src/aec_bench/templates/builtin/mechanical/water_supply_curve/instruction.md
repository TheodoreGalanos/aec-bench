You are a senior mechanical engineer specializing in fire protection hydraulics.

## Task

Develop the water supply curve for the hydrant flow test in {{ site_context }}.

## Given

| Parameter | Value | Unit |
| --- | ---: | --- |
| Static pressure | {{ static_pressure_psi }} | psi |
| Residual pressure during test | {{ residual_pressure_psi }} | psi |
| Measured test flow | {{ test_flow_gpm }} | gpm |
| Target residual pressure | {{ target_residual_pressure_psi }} | psi |

## Constraints

- No internet access is available.
- Use `Q = K * (P_static - P_residual)^0.54`.
- Calculate `K` from the measured test point.
- Calculate available flow at 20 psi residual pressure using the same curve.

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

- Pressure drop during the flow test (`pressure_drop_test_psi`)
- Water supply curve coefficient (`curve_coefficient`)
- Flow at the target residual pressure (`flow_at_target_residual_gpm`)
- Available flow at 20 psi residual pressure (`available_flow_20psi_gpm`)

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "pressure_drop_test_psi": <numeric_value>,
  "curve_coefficient": <numeric_value>,
  "flow_at_target_residual_gpm": <numeric_value>,
  "available_flow_20psi_gpm": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
