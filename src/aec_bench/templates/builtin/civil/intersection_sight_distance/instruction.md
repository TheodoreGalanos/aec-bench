You are a senior civil engineer specializing in road geometry and intersection design.

## Problem

Calculate the required intersection sight distance (ISD) for a minor-road approach at an unsignalised intersection.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Major road design speed (V) | {{ design_speed_kmh }} | km/h |
| Control type | {{ control_type }} | - |
| Approach grade | {{ approach_grade_pct }} | % |
| Lanes to cross | {{ num_lanes_to_cross }} | lanes |
{% if vehicle_type is defined %}
| Design vehicle | {{ vehicle_type }} | - |
{% endif %}
{% if setback_distance_m is defined %}
| Setback distance | {{ setback_distance_m }} | m |
{% endif %}
{% if archetype_description is defined %}

### Site Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

An intersection sight distance calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Total gap acceptance time t_gap (s)
2. Required intersection sight distance ISD (m)
3. Sight triangle leg along the major road (m)
4. Sight triangle leg along the minor road (m)

## Applicable Standards

- Austroads Guide to Road Design Part 4A (AGRD Part 4A §3)

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- The intersection sight distance is calculated as:
  - ISD = V × t_gap / 3.6
  - where V is the major road design speed in km/h and t_gap is the total gap acceptance time in seconds
- Base gap acceptance times (for a 2-lane major road, grade ≤ 3%):
  - **Give way** — passenger: 6.5 s, single-unit truck: 8.5 s, semi-trailer: 10.5 s
  - **Stop** — passenger: 7.5 s, single-unit truck: 9.5 s, semi-trailer: 11.5 s
- **Grade correction**: for minor-road upgrade grades exceeding 3%, add 0.2 s per percent grade above 3%
  - e.g. a 5% upgrade adds 0.2 × (5 − 3) = 0.4 s
  - Downgrades receive no additional time
- **Lane correction**: for major roads with more than 2 lanes, add time per extra lane:
  - Passenger vehicles: +0.5 s per extra lane
  - Trucks: +0.7 s per extra lane
- Total gap time: t_gap = t_base + t_grade + t_lane
- The sight triangle has two legs:
  - Major-road leg = ISD
  - Minor-road leg = setback distance (distance from major-road edge to driver eye position)
{% if vehicle_type is not defined %}
- Design vehicle type is not provided; select an appropriate vehicle based on the intersection context. Use "passenger" for typical urban/suburban roads, "single_unit_truck" where goods vehicles are common, and "semi_trailer" for industrial or freight routes.
{% endif %}
{% if setback_distance_m is not defined %}
- Setback distance is not provided; use a value appropriate for the intersection geometry. Typical values: 5–8 m for urban streets, 8–15 m for industrial accesses with larger turning radii.
{% endif %}

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "gap_time_s": <numeric_value>,
  "required_isd_m": <numeric_value>,
  "sight_triangle_major_m": <numeric_value>,
  "sight_triangle_minor_m": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
