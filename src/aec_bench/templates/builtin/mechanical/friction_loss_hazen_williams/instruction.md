You are a senior mechanical engineer specializing in fire sprinkler hydraulics.

## Task

Calculate the Hazen-Williams friction loss for the sprinkler pipe in {{ site_context }}.

## Given

| Parameter | Value | Unit |
| --- | ---: | --- |
| Flow rate | {{ flow_rate_gpm }} | gpm |
| Straight pipe length | {{ pipe_length_ft }} | ft |
| Internal pipe diameter | {{ pipe_internal_diameter_in }} | in |
| Hazen-Williams C factor | {{ hazen_williams_c }} | - |
| Fitting equivalent length | {{ fitting_equivalent_length_ft }} | ft |

## Constraints

- No internet access is available.
- Use the imperial Hazen-Williams form `p_f = 4.52 Q^1.85 / (C^1.85 d^4.87)` for pressure loss in psi per foot.
- Total equivalent length equals straight pipe length plus fitting equivalent length.
- Report straight-pipe pressure loss and total pressure loss including fittings.

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

- Friction loss per foot (`friction_loss_per_ft_psi`)
- Total equivalent pipe length (`equivalent_length_ft`)
- Straight-pipe friction loss (`pipe_friction_loss_psi`)
- Total pressure loss including fittings (`total_pressure_loss_psi`)

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "friction_loss_per_ft_psi": <numeric_value>,
  "equivalent_length_ft": <numeric_value>,
  "pipe_friction_loss_psi": <numeric_value>,
  "total_pressure_loss_psi": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
