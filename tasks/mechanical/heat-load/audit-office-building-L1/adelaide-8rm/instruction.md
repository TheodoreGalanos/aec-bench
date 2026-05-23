You are a senior mechanical engineer specializing in HVAC design review and quality assurance.

## Problem

Audit the following heat load calculation schedule for a commercial office building in Adelaide, Australia. The schedule was prepared by a junior engineer. Your task is to identify errors in the calculations — wrong AS 1668.2 lookups, arithmetic mistakes, or omitted terms.

## Design Conditions

| Parameter | Value | Unit |
|-----------|-------|------|
| Location | Adelaide, Australia | - |
| Outdoor dry-bulb temperature | 39.6 | °C |
| Outdoor wet-bulb temperature | 21.5 | °C |
| Indoor dry-bulb temperature | 24.0 | °C |
| Outdoor air enthalpy | 62.8 | kJ/kg |
| Indoor air enthalpy | 48.2 | kJ/kg |

## Pre-Filled Heat Load Schedule

| Room No | Name | AS 1668.2 Type | Area (m²) | Height (m) | Lighting (W/m²) | Small Power (W/m²) | Conduction (W/m²) | People | OA (L/s) | People Sens (W) | People Lat (W) | Lighting (W) | Sm Power (W) | Conduction (W) | Vent Sens (W) | Vent Lat (W) | Total Sens (W) | Total Lat (W) | Total Cool (W) |
|---------|------|----------------|-----------|------------|-----------------|--------------------|--------------------|--------|----------|-----------------|----------------|--------------|---------------|----------------|---------------|--------------|----------------|----------------|----------------|
| 1 | Hotel Room A | Hotel Bedrooms | 30 | 2.7 | 8 | 5 | 12 | 3.00 | 37.50 | 225.00 | 165.00 | 240.00 | 150.00 | 972.00 | 707.85 | 657.26 | 2294.85 | 822.26 | 3117.11 |
| 2 | Hotel Room B | Hotel Bedrooms | 35 | 2.7 | 8 | 5 | 12 | 3.50 | 43.75 | 262.50 | 192.50 | 280.00 | 175.00 | 420.00 | 825.83 | 766.81 | 1963.33 | 959.31 | 2922.63 |
| 3 | Hotel Suite | Hotel Suites | 50 | 2.7 | 10 | 8 | 15 | 5.00 | 41.67 | 250.00 | 183.33 | 500.00 | 400.00 | 750.00 | 786.50 | 730.29 | 2686.50 | 913.62 | 3600.12 |
| 4 | Lobby | Reception / Lobby | 70 | 3.0 | 12 | 5 | 15 | 14.00 | 140.00 | 1050.00 | 770.00 | 840.00 | 350.00 | 1050.00 | 2642.64 | 2453.78 | 5932.64 | 3223.78 | 9156.42 |
| 5 | Restaurant | Restaurants | 100 | 3.0 | 12 | 8 | 15 | 66.67 | 666.67 | 5000.00 | 3666.67 | 1200.00 | 800.00 | 1500.00 | 12584.00 | 0.00 | 21084.00 | 3666.67 | 24750.67 |
| 6 | Kitchen | Kitchens (Commercial) | 40 | 2.7 | 8 | 20 | 18 | 8.00 | 120.00 | 600.00 | 440.00 | 320.00 | 800.00 | 720.00 | 2265.12 | 2103.24 | 4705.12 | 2543.24 | 7248.36 |
| 7 | Corridor | Corridors | 80 | 2.7 | 6 | 0 | 10 | 0.00 | 40.00 | 0.00 | 0.00 | 480.00 | 0.00 | 800.00 | 755.04 | 701.08 | 2035.04 | 701.08 | 2736.12 |
| 8 | Storage | Storage / Warehouses | 20 | 3.0 | 5 | 2 | 10 | 0.00 | 10.00 | 0.00 | 0.00 | 100.00 | 40.00 | 200.00 | 188.76 | 175.27 | 528.76 | 175.27 | 704.03 |

## Applicable Standards

- AS 1668.2 — The use of ventilation and airconditioning in buildings, Part 2: Mechanical ventilation in buildings

## Constraints

- No internet access is available. Work from engineering knowledge only.

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
