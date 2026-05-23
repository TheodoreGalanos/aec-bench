You are a senior vertical transportation engineer calculating escalator capacity.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Escalator speed | {{ escalator_speed_m_s }} | m/s |
| Step width | {{ step_width_mm }} | mm |
| Step pitch | {{ step_pitch_mm }} | mm |
{% if practical_loading_factor_pct is defined %}
| Practical loading factor | {{ practical_loading_factor_pct }} | % |
{% endif %}

## Constraints

- Steps per second equals escalator speed divided by step pitch in metres.
- Use 1 person per step when step width is less than 800 mm, otherwise use 2 persons per step.
- Theoretical hourly capacity equals steps per second times persons per step times 3600.
- Practical capacity equals theoretical capacity times the practical loading factor.

## Output Format

Include a JSON block with exactly these keys:

```json
{
  "steps_per_second": <numeric_value>,
  "persons_per_step": <numeric_value>,
  "theoretical_capacity_persons_per_h": <numeric_value>,
  "practical_capacity_persons_per_h": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
