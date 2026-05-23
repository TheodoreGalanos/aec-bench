You are a senior mechanical engineer specializing in HVAC design for commercial buildings.

## Problem

Calculate the cooling heat loads for a 4-room office building in Darwin, Australia, using AS 1668.2 ventilation requirements and standard psychrometric formulas. Compute per-room values and floor-level totals.

## Design Conditions

| Parameter | Value | Unit |
|-----------|-------|------|
| Location | Darwin, Australia | - |
| Outdoor dry-bulb temperature | 34.4 | °C |
| Outdoor wet-bulb temperature | 27.0 | °C |
| Indoor dry-bulb temperature | 24.0 | °C |
| Outdoor air enthalpy | 82.6 | kJ/kg |
| Indoor air enthalpy | 48.2 | kJ/kg |

## Room Schedule

| Room No | Name | Room Type (AS 1668.2) | Floor Area (m²) | Ceiling Height (m) | Lighting (W/m²) | Small Power (W/m²) | Conduction (W/m²) |
|---------|------|----------------------|-----------------|---------------------|-----------------|--------------------|--------------------|
| 1 | Hotel Bedroom | Hotel Bedrooms | 35 | 2.7 | 8 | 5 | 12 |
| 2 | Hotel Suite | Hotel Suites | 55 | 2.7 | 10 | 8 | 15 |
| 3 | Lobby | Reception / Lobby | 60 | 3.0 | 12 | 5 | 15 |
| 4 | Corridor | Corridors | 50 | 2.7 | 6 | 0 | 10 |

## Available Tool

A heat load calculation tool is available at `/workspace/heat_load_calc.py`. Run it with:

```bash
python3 /workspace/heat_load_calc.py --help
python3 /workspace/heat_load_calc.py --list-room-types
```

You may use this tool to compute values for each room individually.

## Required

For each room, calculate:
1. Number of occupants (from AS 1668.2 area-per-person for the room type)
2. Total outside air requirement (L/s)
3. People sensible and latent heat gains (W)
4. Lighting, small power, and conduction heat gains (W)
5. Ventilation sensible and latent heat gains (W)
6. Total sensible, total latent, and total cooling load (W)

Then calculate floor-level totals for total sensible, total latent, and total cooling.

Note: Room 4 (Corridor) is classified as "Corridors" — an unoccupied space. For unoccupied spaces, num_people = 0, and outside air = floor_area × min_OA_rate (L/s/m²).

## Applicable Standards

- AS 1668.2 — The use of ventilation and airconditioning in buildings, Part 2: Mechanical ventilation in buildings

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the following psychrometric constants:
  - Sensible heat gain per person: 75 W
  - Latent heat gain per person: 55 W
  - Air sensible factor: 1.21 W per (L/s)·°C — ventilation sensible = ΔT × 1.21 × total_OA
  - Air latent divisor: 0.833 — ventilation latent = Δh × total_OA / 0.833
- For occupied spaces: outside air = num_people × OA_per_person
- For unoccupied spaces (area_per_person = 0): outside air = floor_area × min_OA_rate

## Output Format

Show your working for each room. At the end of your solution, include a JSON block with all results in exactly this format:

```json
{
  "rooms": [
    {
      "room_no": 1,
      "num_people": <value>,
      "total_outside_air": <value>,
      "people_sensible_w": <value>,
      "people_latent_w": <value>,
      "lighting_w": <value>,
      "small_power_w": <value>,
      "conduction_w": <value>,
      "ventilation_sensible_w": <value>,
      "ventilation_latent_w": <value>,
      "total_sensible_w": <value>,
      "total_latent_w": <value>,
      "total_cooling_w": <value>
    }
  ],
  "floor_totals": {
    "total_sensible_w": <value>,
    "total_latent_w": <value>,
    "total_cooling_w": <value>
  }
}
```

Write your complete solution to `/workspace/output.md`.
