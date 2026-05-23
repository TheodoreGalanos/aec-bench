You are a senior mechanical engineer specializing in HVAC design review and quality assurance.

## Problem

Audit the following heat load calculation schedule for a commercial office building in Canberra, Australia. The schedule was prepared by a junior engineer. Your task is to identify errors in the calculations — wrong AS 1668.2 lookups, arithmetic mistakes, or omitted terms.

## Design Conditions

| Parameter | Value | Unit |
|-----------|-------|------|
| Location | Canberra, Australia | - |
| Outdoor dry-bulb temperature | 36.0 | °C |
| Outdoor wet-bulb temperature | 19.4 | °C |
| Indoor dry-bulb temperature | 24.0 | °C |
| Outdoor air enthalpy | 55.2 | kJ/kg |
| Indoor air enthalpy | 48.2 | kJ/kg |

## Pre-Filled Heat Load Schedule

| Room No | Name | AS 1668.2 Type | Area (m²) | Height (m) | Lighting (W/m²) | Small Power (W/m²) | Conduction (W/m²) | People | OA (L/s) | People Sens (W) | People Lat (W) | Lighting (W) | Sm Power (W) | Conduction (W) | Vent Sens (W) | Vent Lat (W) | Total Sens (W) | Total Lat (W) | Total Cool (W) |
|---------|------|----------------|-----------|------------|-----------------|--------------------|--------------------|--------|----------|-----------------|----------------|--------------|---------------|----------------|---------------|--------------|----------------|----------------|----------------|
| 1 | Classroom A | Classrooms | 60 | 2.7 | 12 | 10 | 15 | 30.00 | 360.00 | 1950.00 | 1650.00 | 720.00 | 600.00 | 900.00 | 5227.20 | 3025.21 | 9397.20 | 4675.21 | 14072.41 |
| 2 | Classroom B | Classrooms | 70 | 2.7 | 12 | 10 | 15 | 35.00 | 420.00 | 2625.00 | 1925.00 | 840.00 | 700.00 | 1050.00 | 0.00 | 3529.41 | 5215.00 | 5454.41 | 10669.41 |
| 3 | Library | Libraries | 100 | 2.7 | 10 | 8 | 15 | 20.00 | 200.00 | 1500.00 | 1100.00 | 1000.00 | 800.00 | 1500.00 | 2904.00 | 1680.67 | 7704.00 | 2780.67 | 10484.67 |
| 4 | Office | Office Areas | 80 | 2.7 | 10 | 15 | 18 | 8.00 | 80.00 | 600.00 | 440.00 | 800.00 | 1200.00 | 1440.00 | 1161.60 | 0.00 | 5201.60 | 440.00 | 5641.60 |
| 5 | Meeting | Meeting Rooms | 20 | 2.7 | 10 | 8 | 15 | 6.67 | 66.67 | 500.00 | 366.67 | 200.00 | 160.00 | 300.00 | 968.00 | 560.22 | 2128.00 | 926.89 | 3054.89 |
| 6 | Corridor | Corridors | 50 | 2.7 | 6 | 0 | 10 | 0.00 | 25.00 | 0.00 | 0.00 | 300.00 | 0.00 | 500.00 | 363.00 | 210.08 | 1163.00 | 210.08 | 1373.08 |
| 7 | Break Room | Cafeteria / Break Rooms | 30 | 2.7 | 8 | 8 | 12 | 12.00 | 120.00 | 900.00 | 660.00 | 240.00 | 240.00 | 360.00 | 1742.40 | 1008.40 | 3482.40 | 1668.40 | 5150.80 |
| 8 | Storage | Storage / Warehouses | 15 | 3.0 | 5 | 2 | 10 | 0.00 | 7.50 | 0.00 | 0.00 | 75.00 | 30.00 | 150.00 | 108.90 | 63.03 | 363.90 | 63.03 | 426.93 |

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
