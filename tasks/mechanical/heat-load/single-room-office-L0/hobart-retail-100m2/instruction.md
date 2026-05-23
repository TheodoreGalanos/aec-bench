You are a senior mechanical engineer specializing in HVAC design for commercial buildings.

## Problem

Calculate the cooling heat load for a single retail shops room in Hobart, Australia.
## Room Details

| Parameter | Value | Unit |
|-----------|-------|------|
| Room type | Retail Shops | - |
| Floor area | 100 | m² |
| Ceiling height | 3.5 | m |
| Location | Hobart, Australia | - |

## Required

Using your engineering knowledge, determine appropriate design conditions for Hobart and calculate the following for this room:

1. Number of occupants (from AS 1668.2 area-per-person for the type)
2. Total outside air requirement (L/s)
3. People sensible heat gain (W)
4. People latent heat gain (W)
5. Lighting heat gain (W)
6. Small power heat gain (W)
7. Conduction/transmission heat gain (W)
8. Ventilation sensible heat gain (W)
9. Ventilation latent heat gain (W)
10. Total sensible heat gain (W)
11. Total latent heat gain (W)
12. Total cooling load (W)

You will need to determine appropriate values for outdoor design conditions, indoor design conditions, lighting power density, small power density, conduction factor, and all ventilation parameters from your engineering knowledge.

## Applicable Standards

- AS 1668.2 — The use of ventilation and airconditioning in buildings, Part 2: Mechanical ventilation in buildings (for occupancy densities and outside air rates)

## Constraints

- No internet access is available. Work from engineering knowledge only.

## Output Format

Show your step-by-step working in Markdown, including all assumptions, formulas and intermediate calculations. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "num_people": <numeric_value>,
  "total_outside_air": <numeric_value>,
  "people_sensible_w": <numeric_value>,
  "people_latent_w": <numeric_value>,
  "lighting_w": <numeric_value>,
  "small_power_w": <numeric_value>,
  "conduction_w": <numeric_value>,
  "ventilation_sensible_w": <numeric_value>,
  "ventilation_latent_w": <numeric_value>,
  "total_sensible_w": <numeric_value>,
  "total_latent_w": <numeric_value>,
  "total_cooling_w": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
