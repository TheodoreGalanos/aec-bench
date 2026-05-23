You are a senior mechanical engineer specializing in CFD verification.

## Task

Calculate the grid convergence index for the monotonic three-grid study in {{ site_context }}.

## Given

| Parameter | Value | Unit |
| --- | ---: | --- |
| Coarse-grid QoI value | {{ coarse_grid_value }} | - |
| Medium-grid QoI value | {{ medium_grid_value }} | - |
| Fine-grid QoI value | {{ fine_grid_value }} | - |
| Refinement ratio | {{ refinement_ratio }} | - |

## Constraints

- No internet access is available.
- Use equal refinement ratio between coarse, medium, and fine grids.
- Use `p = ln(abs((phi_3 - phi_2) / (phi_2 - phi_1))) / ln(r)`, where `phi_1` is the fine-grid value, `phi_2` is the medium-grid value, and `phi_3` is the coarse-grid value.
- Use `phi_ext = phi_1 + (phi_1 - phi_2) / (r^p - 1)`.
- Use safety factor `Fs = 1.25`.
- Use `GCI_fine = Fs * abs((phi_1 - phi_2) / phi_1) * 100 / (r^p - 1)`.

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

- Observed order of accuracy (`observed_order`)
- Richardson extrapolated value (`extrapolated_value`)
- Approximate relative error (`approximate_relative_error_pct`)
- Fine-grid convergence index (`gci_fine_pct`)
- Asymptotic range ratio (`asymptotic_range_ratio`)

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "observed_order": <numeric_value>,
  "extrapolated_value": <numeric_value>,
  "approximate_relative_error_pct": <numeric_value>,
  "gci_fine_pct": <numeric_value>,
  "asymptotic_range_ratio": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
