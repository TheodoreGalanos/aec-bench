You are a senior mechanical engineer specializing in HVAC design review and quality assurance.

## Problem

Audit the following heat load calculation schedule for a commercial office building in Brisbane, Australia. The schedule was prepared by a junior engineer. Your task is to identify errors in the calculations — wrong AS 1668.2 lookups, arithmetic mistakes, or omitted terms.

## Design Conditions

| Parameter | Value | Unit |
|-----------|-------|------|
| Location | Brisbane, Australia | - |
| Outdoor dry-bulb temperature | 38.3 | °C |
| Outdoor wet-bulb temperature | 23.6 | °C |
| Indoor dry-bulb temperature | 24.0 | °C |
| Outdoor air enthalpy | 71.2 | kJ/kg |
| Indoor air enthalpy | 48.2 | kJ/kg |

## Pre-Filled Heat Load Schedule

| Room No | Name | AS 1668.2 Type | Area (m²) | Height (m) | Lighting (W/m²) | Small Power (W/m²) | Conduction (W/m²) | People | OA (L/s) | People Sens (W) | People Lat (W) | Lighting (W) | Sm Power (W) | Conduction (W) | Vent Sens (W) | Vent Lat (W) | Total Sens (W) | Total Lat (W) | Total Cool (W) |
|---------|------|----------------|-----------|------------|-----------------|--------------------|--------------------|--------|----------|-----------------|----------------|--------------|---------------|----------------|---------------|--------------|----------------|----------------|----------------|
| 1 | Reception | Reception / Lobby | 45 | 2.7 | 12 | 5 | 15 | 9.00 | 90.00 | 675.00 | 495.00 | 540.00 | 225.00 | 675.00 | 1557.27 | 2484.99 | 3672.27 | 2979.99 | 6652.26 |
| 2 | Office | Office Areas | 160 | 2.7 | 10 | 15 | 18 | 16.00 | 160.00 | 1200.00 | 880.00 | 1600.00 | 2400.00 | 2880.00 | 2768.48 | 13675.87 | 10848.48 | 14555.87 | 25404.35 |
| 3 | Classroom | Classrooms | 80 | 2.7 | 12 | 10 | 15 | 8.00 | 480.00 | 3000.00 | 2200.00 | 960.00 | 800.00 | 1200.00 | 8305.44 | 13253.30 | 14265.44 | 15453.30 | 29718.74 |
| 4 | Library | Libraries | 90 | 2.7 | 10 | 8 | 15 | 18.00 | 180.00 | 1350.00 | 990.00 | 900.00 | 720.00 | 1350.00 | 0.00 | 4969.99 | 4320.00 | 5959.99 | 10279.99 |
| 5 | Meeting | Meeting Rooms | 20 | 2.7 | 10 | 8 | 15 | 6.67 | 66.67 | 500.00 | 366.67 | 200.00 | 160.00 | 300.00 | 1153.53 | 1840.74 | 2313.53 | 2207.40 | 4520.94 |
| 6 | Corridor | Corridors | 60 | 2.7 | 6 | 0 | 10 | 0.00 | 30.00 | 0.00 | 0.00 | 360.00 | 0.00 | 600.00 | 519.09 | 828.33 | 1479.09 | 828.33 | 2307.42 |
| 7 | Storage | Storage / Warehouses | 25 | 3.0 | 5 | 2 | 10 | 0.00 | 12.50 | 0.00 | 0.00 | 125.00 | 50.00 | 250.00 | 216.29 | 345.14 | 641.29 | 345.14 | 986.43 |
| 8 | Server Room | Data Centres / Server Rooms | 15 | 3.0 | 5 | 300 | 25 | 0.00 | 15.00 | 0.00 | 0.00 | 75.00 | 4500.00 | 375.00 | 259.54 | 414.17 | 5209.55 | 414.17 | 5623.71 |

## Applicable Standards

- AS 1668.2 — The use of ventilation and airconditioning in buildings, Part 2: Mechanical ventilation in buildings

## Constraints

- No internet access is available. Work from engineering knowledge only.
## AS 1668.2 Reference Data

| Room Type | Area per Person (m²) | Outside Air per Person (L/s) | Min OA Rate (L/s/m²) | Classification |
|-----------|---------------------|-----------------------------|-----------------------|----------------|
| Classrooms | 2.0 | 12.0 | 0.0 | Class A |
| Corridors | 0.0 | 0.0 | 0.5 | Class B |
| Data Centres / Server Rooms | 0.0 | 0.0 | 1.0 | Class B |
| Libraries | 5.0 | 10.0 | 0.0 | Class A |
| Meeting Rooms | 3.0 | 10.0 | 0.0 | Class A |
| Office Areas | 10.0 | 10.0 | 0.0 | Class A |
| Reception / Lobby | 5.0 | 10.0 | 0.0 | Class A |
| Storage / Warehouses | 0.0 | 0.0 | 0.5 | Class B |

- Use standard psychrometric formulas for ventilation sensible and latent heat gains.
- Apply standard occupant heat gain values for office-type activity.

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
