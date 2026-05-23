You are a senior mechanical engineer specializing in HVAC design review and quality assurance.

## Problem

Audit the following heat load calculation schedule for a commercial office building in Cairns, Australia. The schedule was prepared by a junior engineer. Your task is to identify errors in the calculations — wrong AS 1668.2 lookups, arithmetic mistakes, or omitted terms.

## Design Conditions

| Parameter | Value | Unit |
|-----------|-------|------|
| Location | Cairns, Australia | - |
| Outdoor dry-bulb temperature | 34.0 | °C |
| Outdoor wet-bulb temperature | 26.8 | °C |
| Indoor dry-bulb temperature | 24.0 | °C |
| Outdoor air enthalpy | 81.4 | kJ/kg |
| Indoor air enthalpy | 48.2 | kJ/kg |

## Pre-Filled Heat Load Schedule

| Room No | Name | AS 1668.2 Type | Area (m²) | Height (m) | Lighting (W/m²) | Small Power (W/m²) | Conduction (W/m²) | People | OA (L/s) | People Sens (W) | People Lat (W) | Lighting (W) | Sm Power (W) | Conduction (W) | Vent Sens (W) | Vent Lat (W) | Total Sens (W) | Total Lat (W) | Total Cool (W) |
|---------|------|----------------|-----------|------------|-----------------|--------------------|--------------------|--------|----------|-----------------|----------------|--------------|---------------|----------------|---------------|--------------|----------------|----------------|----------------|
| 1 | Hotel Room | Hotel Bedrooms | 40 | 2.7 | 8 | 5 | 12 | 4.00 | 50.00 | 300.00 | 220.00 | 320.00 | 200.00 | 480.00 | 605.00 | 0.00 | 1905.00 | 220.00 | 2125.00 |
| 2 | Hotel Suite | Hotel Suites | 60 | 2.7 | 10 | 8 | 15 | 6.00 | 50.00 | 300.00 | 220.00 | 600.00 | 480.00 | 900.00 | 605.00 | 1992.80 | 2885.00 | 2212.80 | 5097.80 |
| 3 | Restaurant | Restaurants | 100 | 3.0 | 12 | 8 | 15 | 66.67 | 666.67 | 5000.00 | 3666.67 | 1200.00 | 800.00 | 4500.00 | 8066.67 | 26570.63 | 19566.67 | 30237.30 | 49803.97 |
| 4 | Kitchen | Kitchens (Commercial) | 35 | 2.7 | 8 | 20 | 18 | 7.00 | 105.00 | 525.00 | 385.00 | 280.00 | 700.00 | 630.00 | 1270.50 | 4184.87 | 3405.50 | 4569.87 | 7975.37 |
| 5 | Lobby | Reception / Lobby | 50 | 3.0 | 12 | 5 | 15 | 10.00 | 100.00 | 750.00 | 550.00 | 600.00 | 250.00 | 750.00 | 1210.00 | 3985.59 | 3560.00 | 4535.59 | 8095.59 |
| 6 | Retail | Retail Shops | 60 | 3.5 | 18 | 10 | 20 | 12.00 | 120.00 | 900.00 | 660.00 | 1080.00 | 600.00 | 1200.00 | 1452.00 | 4782.71 | 5232.00 | 5442.71 | 10674.71 |
| 7 | Corridor | Corridors | 50 | 2.7 | 6 | 0 | 10 | 0.00 | 25.00 | 0.00 | 0.00 | 300.00 | 0.00 | 500.00 | 302.50 | 996.40 | 1102.50 | 996.40 | 2098.90 |
| 8 | Storage | Storage / Warehouses | 20 | 3.0 | 5 | 2 | 10 | 0.00 | 10.00 | 0.00 | 0.00 | 100.00 | 40.00 | 200.00 | 121.00 | 398.56 | 461.00 | 398.56 | 859.56 |

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
