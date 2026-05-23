You are a senior mechanical engineer specializing in HVAC design review and quality assurance.

## Problem

Audit the following heat load calculation schedule for a commercial office building in Melbourne, Australia. The schedule was prepared by a junior engineer. Your task is to identify errors in the calculations — wrong AS 1668.2 lookups, arithmetic mistakes, or omitted terms.

## Design Conditions

| Parameter | Value | Unit |
|-----------|-------|------|
| Location | Melbourne, Australia | - |
| Outdoor dry-bulb temperature | 36.4 | °C |
| Outdoor wet-bulb temperature | 20.8 | °C |
| Indoor dry-bulb temperature | 24.0 | °C |
| Outdoor air enthalpy | 58.6 | kJ/kg |
| Indoor air enthalpy | 48.2 | kJ/kg |

## Pre-Filled Heat Load Schedule

| Room No | Name | AS 1668.2 Type | Area (m²) | Height (m) | Lighting (W/m²) | Small Power (W/m²) | Conduction (W/m²) | People | OA (L/s) | People Sens (W) | People Lat (W) | Lighting (W) | Sm Power (W) | Conduction (W) | Vent Sens (W) | Vent Lat (W) | Total Sens (W) | Total Lat (W) | Total Cool (W) |
|---------|------|----------------|-----------|------------|-----------------|--------------------|--------------------|--------|----------|-----------------|----------------|--------------|---------------|----------------|---------------|--------------|----------------|----------------|----------------|
| 1 | Reception | Reception / Lobby | 40 | 2.7 | 12 | 5 | 15 | 8.00 | 80.00 | 600.00 | 440.00 | 480.00 | 200.00 | 600.00 | 1200.32 | 998.80 | 3080.32 | 1438.80 | 4519.12 |
| 2 | Open Office | Office Areas | 200 | 2.7 | 10 | 15 | 18 | 66.67 | 200.00 | 1500.00 | 1100.00 | 2000.00 | 3000.00 | 3600.00 | 3000.80 | 2497.00 | 13100.80 | 3597.00 | 16697.80 |
| 3 | Meeting Room | Meeting Rooms | 25 | 2.7 | 10 | 8 | 15 | 8.33 | 83.33 | 625.00 | 458.33 | 250.00 | 200.00 | 375.00 | 1250.33 | 1040.42 | 2700.33 | 1498.75 | 4199.08 |
| 4 | Breakroom | Cafeteria / Break Rooms | 30 | 2.7 | 8 | 10 | 12 | 12.00 | 120.00 | 900.00 | 660.00 | 240.00 | 300.00 | 360.00 | 1800.48 | 0.00 | 3600.48 | 660.00 | 4260.48 |
| 5 | Conference | Conference Rooms | 50 | 2.7 | 10 | 10 | 15 | 25.00 | 250.00 | 1875.00 | 1375.00 | 500.00 | 500.00 | 750.00 | 0.00 | 3121.25 | 3625.00 | 4496.25 | 8121.25 |
| 6 | Corridor | Corridors | 80 | 2.7 | 6 | 0 | 10 | 0.00 | 40.00 | 0.00 | 0.00 | 480.00 | 0.00 | 800.00 | 600.16 | 499.40 | 1880.16 | 499.40 | 2379.56 |
| 7 | Server Room | Data Centres / Server Rooms | 20 | 3.0 | 5 | 250 | 20 | 0.00 | 20.00 | 0.00 | 0.00 | 100.00 | 5000.00 | 400.00 | 300.08 | 249.70 | 5800.08 | 249.70 | 6049.78 |
| 8 | Library | Libraries | 100 | 2.7 | 10 | 8 | 15 | 20.00 | 200.00 | 1500.00 | 1100.00 | 1000.00 | 800.00 | 1500.00 | 3000.80 | 2497.00 | 7800.80 | 3597.00 | 11397.80 |

## Applicable Standards

- AS 1668.2 — The use of ventilation and airconditioning in buildings, Part 2: Mechanical ventilation in buildings

## Constraints

- No internet access is available. Work from engineering knowledge only.
## AS 1668.2 Reference Data

| Room Type | Area per Person (m²) | Outside Air per Person (L/s) | Min OA Rate (L/s/m²) | Classification |
|-----------|---------------------|-----------------------------|-----------------------|----------------|
| Cafeteria / Break Rooms | 2.5 | 10.0 | 0.0 | Class A |
| Conference Rooms | 2.0 | 10.0 | 0.0 | Class A |
| Corridors | 0.0 | 0.0 | 0.5 | Class B |
| Data Centres / Server Rooms | 0.0 | 0.0 | 1.0 | Class B |
| Libraries | 5.0 | 10.0 | 0.0 | Class A |
| Meeting Rooms | 3.0 | 10.0 | 0.0 | Class A |
| Office Areas | 10.0 | 10.0 | 0.0 | Class A |
| Reception / Lobby | 5.0 | 10.0 | 0.0 | Class A |

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
