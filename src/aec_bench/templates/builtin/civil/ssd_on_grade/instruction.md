You are a senior civil engineer specializing in road geometry and stopping sight distance analysis.

## Problem

Calculate the required stopping sight distance (SSD) for a road segment on a longitudinal grade.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Design speed (V) | {{ design_speed_km_h }} | km/h |
| Longitudinal grade | {{ grade_pct }} | % |
{% if reaction_time_s is defined %}
| Reaction time (t_r) | {{ reaction_time_s }} | s |
{% endif %}
{% if archetype_description is defined %}

### Site Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A stopping sight distance calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Reaction distance component d_r (m)
2. Braking distance component d_b (m)
3. Total stopping sight distance SSD (m)

## Applicable Standards

- Austroads Guide to Road Design Part 3 (AGRD Part 3 §5)

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- The friction coefficient f depends on design speed per AGRD Table 5.5. Use the following lookup:
  - 40 km/h → f = 0.52, 50 → 0.48, 60 → 0.45, 70 → 0.43, 80 → 0.40, 90 → 0.38, 100 → 0.36, 110 → 0.34, 120 → 0.32, 130 → 0.29
  - Interpolate linearly for intermediate speeds
- Reaction distance: d_r = V × t_r / 3.6 (where V in km/h, t_r in seconds)
- Braking distance: d_b = V² / (254 × (f + g)) (where g = grade / 100, positive = uphill)
  - Sign convention: positive grade means uphill travel (grade assists braking); negative grade means downhill travel (grade hinders braking)
- Total SSD = d_r + d_b
{% if reaction_time_s is not defined %}
- Reaction time is not provided; select an appropriate value based on the road environment and expected driver alertness. AGRD recommends 1.5 s (alert) to 2.5 s (relaxed).
{% endif %}

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "reaction_distance_m": <numeric_value>,
  "braking_distance_m": <numeric_value>,
  "stopping_sight_distance_m": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
