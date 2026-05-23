You are a senior mechanical engineer specializing in HVAC design for commercial buildings.

## Problem

Calculate the cooling heat load for a single conference rooms room in Melbourne, Australia, using AS 1668.2 ventilation requirements and standard psychrometric formulas.
## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Room type | Conference Rooms | - |
| Floor area | 50 | m² |
| Ceiling height | 2.7 | m |
| Outdoor dry-bulb temperature | 36.4 | °C |
| Outdoor wet-bulb temperature | 20.8 | °C |
| Indoor dry-bulb temperature | 24.0 | °C |
| Outdoor air enthalpy | 58.6 | kJ/kg |
| Indoor air enthalpy | 48.2 | kJ/kg |
| Lighting power density | 10 | W/m² |
| Small power (equipment) density | 10 | W/m² |
| Conduction/transmission factor | 15 | W/m² |
| Ventilation type | Mechanical | - |

## Required

Calculate the following for this room:

1. Number of occupants (from AS 1668.2 area-per-person for room type)
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

## Applicable Standards

- AS 1668.2 — The use of ventilation and airconditioning in buildings, Part 2: Mechanical ventilation in buildings (for occupancy densities and outside air rates)

## Constraints

- No internet access is available. Work from engineering knowledge only.
- Use the following psychrometric constants:
  - Sensible heat gain per person: 75 W
  - Latent heat gain per person: 55 W
  - Air sensible factor: 1.21 W per (L/s)·°C — i.e., ventilation sensible = ΔT × 1.21 × total_OA
  - Air latent divisor: 0.833 — i.e., ventilation latent = Δh × total_OA / 0.833
- For occupied spaces, outside air = num_people × OA_per_person
- For unoccupied spaces (area_per_person = 0), outside air = floor_area × min_OA_rate

## Output Format

Show your step-by-step working in Markdown, including formulas and intermediate calculations. At the end of your solution, include a JSON block with your final answers in exactly this format:

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
