You are a senior mechanical engineer specializing in fatigue damage checks.

## Problem

Calculate cumulative fatigue damage using Miner's rule for three stress or duty cycle bins.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Applied cycles bin 1 | {{ applied_cycles_1 }} | cycles |
| Allowable cycles bin 1 | {{ allowable_cycles_1 }} | cycles |
| Applied cycles bin 2 | {{ applied_cycles_2 }} | cycles |
| Allowable cycles bin 2 | {{ allowable_cycles_2 }} | cycles |
| Applied cycles bin 3 | {{ applied_cycles_3 }} | cycles |
| Allowable cycles bin 3 | {{ allowable_cycles_3 }} | cycles |

{% if archetype_description is defined %}
### Fatigue Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A Miner fatigue calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Damage fraction for each cycle bin
2. Cumulative damage
3. Remaining damage margin
4. Numeric pass flag, where 1 means cumulative damage is not greater than 1

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use damage fraction = applied cycles / allowable cycles.
- Use cumulative damage = sum of damage fractions.
- Use remaining margin = 1 - cumulative damage.

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "damage_bin_1": <numeric_value>,
  "damage_bin_2": <numeric_value>,
  "damage_bin_3": <numeric_value>,
  "cumulative_damage": <numeric_value>,
  "remaining_damage_margin": <numeric_value>,
  "fatigue_satisfies": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.

