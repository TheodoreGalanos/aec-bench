You are a senior mechanical engineer specializing in vibration isolation.

## Problem

Calculate vibration transmissibility for a damped single-degree isolation system.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Forcing frequency | {{ forcing_frequency_hz }} | Hz |
| Natural frequency | {{ natural_frequency_hz }} | Hz |
| Damping ratio | {{ damping_ratio }} | - |

{% if archetype_description is defined %}
### Isolation Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A vibration transmissibility calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Frequency ratio
2. Transmissibility
3. Isolation efficiency in percent

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use frequency ratio = forcing frequency / natural frequency.
- Use the damped force transmissibility equation provided by the tool.
- Use isolation efficiency = (1 - transmissibility) x 100.

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "frequency_ratio": <numeric_value>,
  "transmissibility": <numeric_value>,
  "isolation_efficiency_pct": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.

