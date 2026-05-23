You are a senior mechanical engineer specializing in HVAC design review and quality assurance.

## Problem

Audit the following heat load calculation schedule for a commercial office building in Hobart, Australia. The schedule was prepared by a junior engineer. Your task is to identify errors in the calculations — wrong AS 1668.2 lookups, arithmetic mistakes, or omitted terms.

## Design Conditions

| Parameter | Value | Unit |
|-----------|-------|------|
| Location | Hobart, Australia | - |
| Outdoor dry-bulb temperature | 31.0 | °C |
| Outdoor wet-bulb temperature | 18.5 | °C |
| Indoor dry-bulb temperature | 24.0 | °C |
| Outdoor air enthalpy | 50.8 | kJ/kg |
| Indoor air enthalpy | 48.2 | kJ/kg |

## Pre-Filled Heat Load Schedule

| Room No | Name | AS 1668.2 Type | Area (m²) | Height (m) | Lighting (W/m²) | Small Power (W/m²) | Conduction (W/m²) | People | OA (L/s) | People Sens (W) | People Lat (W) | Lighting (W) | Sm Power (W) | Conduction (W) | Vent Sens (W) | Vent Lat (W) | Total Sens (W) | Total Lat (W) | Total Cool (W) |
|---------|------|----------------|-----------|------------|-----------------|--------------------|--------------------|--------|----------|-----------------|----------------|--------------|---------------|----------------|---------------|--------------|----------------|----------------|----------------|
| 1 | Retail A | Retail Shops | 90 | 3.5 | 18 | 10 | 20 | 18.00 | 180.00 | 1350.00 | 990.00 | 1620.00 | 900.00 | 6300.00 | 1524.60 | 561.82 | 11694.60 | 1551.82 | 13246.42 |
| 2 | Retail B | Retail Shops | 70 | 3.5 | 18 | 10 | 20 | 14.00 | 140.00 | 1050.00 | 770.00 | 1260.00 | 700.00 | 1400.00 | 1185.80 | 436.97 | 5595.80 | 1206.97 | 6802.77 |
| 3 | Office | Office Areas | 60 | 2.7 | 10 | 15 | 18 | 6.00 | 60.00 | 390.00 | 330.00 | 600.00 | 900.00 | 1080.00 | 508.20 | 187.27 | 3478.20 | 517.27 | 3995.47 |
| 4 | Meeting | Meeting Rooms | 15 | 2.7 | 10 | 8 | 15 | 5.00 | 50.00 | 375.00 | 275.00 | 150.00 | 120.00 | 225.00 | 423.50 | 156.06 | 1293.50 | 431.06 | 1724.56 |
| 5 | Break Room | Cafeteria / Break Rooms | 20 | 2.7 | 8 | 8 | 12 | 8.00 | 80.00 | 600.00 | 440.00 | 160.00 | 160.00 | 240.00 | 0.00 | 249.70 | 1160.00 | 689.70 | 1849.70 |
| 6 | Corridor | Corridors | 40 | 2.7 | 6 | 0 | 10 | 0.00 | 20.00 | 0.00 | 0.00 | 240.00 | 0.00 | 400.00 | 169.40 | 62.42 | 809.40 | 62.42 | 871.82 |
| 7 | Storage | Storage / Warehouses | 20 | 3.0 | 5 | 2 | 10 | 0.00 | 10.00 | 0.00 | 0.00 | 100.00 | 40.00 | 200.00 | 84.70 | 31.21 | 424.70 | 31.21 | 455.91 |
| 8 | Server Room | Data Centres / Server Rooms | 10 | 3.0 | 5 | 250 | 25 | 0.00 | 10.00 | 0.00 | 0.00 | 50.00 | 2500.00 | 250.00 | 84.70 | 31.21 | 2884.70 | 31.21 | 2915.91 |

## Applicable Standards

- AS 1668.2 — The use of ventilation and airconditioning in buildings, Part 2: Mechanical ventilation in buildings

## Constraints

- No internet access is available. Work from engineering knowledge only.
- Use the following psychrometric constants:
  - Sensible heat gain per person: 75 W
  - Latent heat gain per person: 55 W
  - Air sensible factor: 1.21 W per (L/s)·°C — ventilation sensible = (T_outdoor − T_indoor) × 1.21 × total_OA
  - Air latent divisor: 0.833 — ventilation latent = (h_outdoor − h_indoor) × total_OA / 0.833
- For occupied spaces: outside air = num_people × OA_per_person
- For unoccupied spaces (area_per_person = 0): outside air = floor_area × min_OA_rate

## Required

Check every room in the schedule. For each error found, report:
- Which room (by room number)
- Which field is wrong
- The value given in the schedule
- The correct value you calculated
- A brief explanation of the error

If a room has no errors, you do not need to report it.

## Output Format

Show your step-by-step audit working. At the end, include a JSON block with your findings in exactly this format:

```json
{
  "errors_found": [
    {
      "room_no": <integer>,
      "field": "<field_name>",
      "given_value": <numeric_value_from_schedule>,
      "correct_value": <your_calculated_correct_value>,
      "explanation": "<brief description of the error>"
    }
  ]
}
```

Valid field names: `num_people`, `total_outside_air`, `people_sensible_w`, `people_latent_w`, `lighting_w`, `small_power_w`, `conduction_w`, `ventilation_sensible_w`, `ventilation_latent_w`, `total_sensible_w`, `total_latent_w`, `total_cooling_w`.

If no errors are found, use: `{"errors_found": []}`

Write your complete audit to `/workspace/output.md`.
