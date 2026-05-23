# ABOUTME: Prompt template for interior illuminance uniformity tasks.
# ABOUTME: Presents task, surround, and background illuminance values.

You are a senior interior lighting engineer verifying workplace illuminance uniformity.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Task minimum illuminance | {{ task_min_illuminance_lux }} | lux |
| Task average illuminance | {{ task_average_illuminance_lux }} | lux |
| Immediate surround average illuminance | {{ surround_average_illuminance_lux }} | lux |
| Background average illuminance | {{ background_average_illuminance_lux }} | lux |

## Constraints

- Task uniformity Uo equals task minimum illuminance divided by task average illuminance.
- Surround-to-task ratio equals immediate surround average illuminance divided by task average illuminance.
- Background-to-task ratio equals background average illuminance divided by task average illuminance.

## Output Format

Include a JSON block with exactly these keys:

```json
{
  "task_uniformity_uo": <numeric_value>,
  "surround_to_task_ratio": <numeric_value>,
  "background_to_task_ratio": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
