You are a senior mechanical engineer specializing in rolling stock braking systems.

## Problem

Calculate train stopping distance from initial speed, braking effort, adhesion limit, and track gradient.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Train mass | {{ train_mass_t }} | t |
| Initial speed | {{ initial_speed_km_h }} | km/h |
| Brake effort | {{ brake_effort_kn }} | kN |
| Adhesion coefficient | {{ adhesion_coefficient }} | - |
| Track gradient | {{ track_gradient_pct }} | % |

{% if archetype_description is defined %}
### Braking Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A braking distance calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Effective brake effort after adhesion limit (kN)
2. Net braking deceleration (m/s2)
3. Stopping distance (m)
4. Stopping time (s)

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use g = 9.81 m/s2.
- Convert mass from tonnes to kg and speed from km/h to m/s.
- Use adhesion limit = adhesion coefficient x mass x g.
- Use effective brake effort = min(brake effort, adhesion limit).
- Use gradient acceleration = g x gradient percent / 100, positive downhill.
- Use net deceleration = brake deceleration - gradient acceleration.
- Use stopping distance = initial speed^2 / (2 x net deceleration).
- Use stopping time = initial speed / net deceleration.

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "adhesion_limited_brake_effort_kn": <numeric_value>,
  "net_deceleration_m_s2": <numeric_value>,
  "stopping_distance_m": <numeric_value>,
  "stopping_time_s": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
