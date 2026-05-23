You are a senior fire services engineer specializing in fire alarm notification circuits.

## Problem

Calculate the notification appliance circuit load, utilisation, spare capacity, and pass status.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Strobe quantity | {{ strobe_quantity }} | count |
| Strobe current | {{ strobe_current_a }} | A |
| Horn quantity | {{ horn_quantity }} | count |
| Horn current | {{ horn_current_a }} | A |
| Speaker quantity | {{ speaker_quantity }} | count |
| Speaker current | {{ speaker_current_a }} | A |
| Circuit capacity | {{ circuit_capacity_a }} | A |

{% if archetype_description is defined %}
### Circuit Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A NAC load calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Total circuit load (A)
2. Circuit utilisation (%)
3. Spare capacity (A)
4. Whether the circuit passes the capacity check

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use total load = strobe quantity x strobe current + horn quantity x horn current + speaker quantity x speaker current.
- Use utilisation = total load / circuit capacity x 100.
- Use spare capacity = circuit capacity - total load.
- The circuit passes when total load is less than or equal to circuit capacity.

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "total_load_a": <numeric_value>,
  "utilisation_pct": <numeric_value>,
  "spare_capacity_a": <numeric_value>,
  "passes_capacity_check": <true_or_false>
}
```

Write your complete solution to `/workspace/output.md`.
