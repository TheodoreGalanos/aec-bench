You are a senior mechanical engineer specializing in rail vehicle dynamics.

## Task

Calculate Davis running resistance and tractive power for the train in {{ site_context }}.

## Given

| Parameter | Value | Unit |
| --- | ---: | --- |
| Train mass | {{ train_mass_t }} | t |
| Train speed | {{ speed_km_h }} | km/h |
| Davis A coefficient | {{ coefficient_a_n_t }} | N/t |
| Davis B coefficient | {{ coefficient_b_n_t_km_h }} | N/t per km/h |
| Davis C coefficient | {{ coefficient_c_n_t_km_h2 }} | N/t per (km/h)^2 |

## Constraints

- No internet access is available.
- Use `R = A + Bv + Cv^2` to calculate resistance in N/t, with speed in km/h.
- Convert speed to m/s using `v_m_s = v_km_h / 3.6`.
- Calculate total resistance in kN as `R * train mass / 1000`.
- Calculate tractive power in kW as `total resistance kN * speed m/s`.

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

- Train speed in metres per second (`speed_m_s`)
- Running resistance per tonne (`resistance_n_per_t`)
- Total running resistance (`total_resistance_kn`)
- Tractive power to overcome running resistance (`tractive_power_kw`)

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "speed_m_s": <numeric_value>,
  "resistance_n_per_t": <numeric_value>,
  "total_resistance_kn": <numeric_value>,
  "tractive_power_kw": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
