You are a senior mechanical engineer specializing in wastewater treatment process design.

## Task

Calculate the required solids retention time for nitrification in {{ site_context }}.

## Given

| Parameter | Value | Unit |
| --- | ---: | --- |
| Maximum specific nitrifier growth rate at 20 C | {{ max_specific_growth_d }} | 1/d |
| Temperature correction coefficient | {{ theta }} | - |
| Wastewater temperature | {{ wastewater_temperature_c }} | deg C |
| Ammonia nitrogen concentration | {{ ammonia_n_mg_l }} | mg/L |
| Ammonia half-saturation coefficient | {{ half_saturation_n_mg_l }} | mg/L |
| Dissolved oxygen concentration | {{ dissolved_oxygen_mg_l }} | mg/L |
| Oxygen half-saturation coefficient | {{ oxygen_half_saturation_mg_l }} | mg/L |
| Nitrifier decay rate | {{ decay_rate_d }} | 1/d |
| SRT safety factor | {{ safety_factor }} | - |

## Constraints

- No internet access is available.
- Use `mu_T = mu_20 * theta^(T - 20)`.
- Use `N / (K_N + N)` for the ammonia substrate factor.
- Use `DO / (K_DO + DO)` for the dissolved oxygen factor.
- Use `net growth = mu_T * substrate factor * oxygen factor - decay rate`.
- Use `required SRT = safety factor / net growth`.

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

- Temperature-corrected maximum growth rate (`temperature_corrected_growth_d`)
- Ammonia substrate limitation factor (`substrate_factor`)
- Dissolved oxygen limitation factor (`oxygen_factor`)
- Net nitrifier growth rate (`net_growth_d`)
- Required solids retention time (`required_srt_days`)

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "temperature_corrected_growth_d": <numeric_value>,
  "substrate_factor": <numeric_value>,
  "oxygen_factor": <numeric_value>,
  "net_growth_d": <numeric_value>,
  "required_srt_days": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
