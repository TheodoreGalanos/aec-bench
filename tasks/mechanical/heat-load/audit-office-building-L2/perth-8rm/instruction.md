You are a senior mechanical engineer specializing in HVAC design review and quality assurance.

## Problem

Audit the following heat load calculation schedule for a commercial office building in Perth, Australia. The schedule was prepared by a junior engineer. Your task is to identify errors in the calculations — wrong AS 1668.2 lookups, arithmetic mistakes, or omitted terms.

## Design Conditions

| Parameter | Value | Unit |
|-----------|-------|------|
| Location | Perth, Australia | - |
| Outdoor dry-bulb temperature | 45.5 | °C |
| Outdoor wet-bulb temperature | 25.5 | °C |
| Indoor dry-bulb temperature | 24.0 | °C |
| Outdoor air enthalpy | 78.4 | kJ/kg |
| Indoor air enthalpy | 48.2 | kJ/kg |

## Pre-Filled Heat Load Schedule

| Room No | Name | AS 1668.2 Type | Area (m²) | Height (m) | Lighting (W/m²) | Small Power (W/m²) | Conduction (W/m²) | People | OA (L/s) | People Sens (W) | People Lat (W) | Lighting (W) | Sm Power (W) | Conduction (W) | Vent Sens (W) | Vent Lat (W) | Total Sens (W) | Total Lat (W) | Total Cool (W) |
|---------|------|----------------|-----------|------------|-----------------|--------------------|--------------------|--------|----------|-----------------|----------------|--------------|---------------|----------------|---------------|--------------|----------------|----------------|----------------|
| 1 | Lobby | Reception / Lobby | 60 | 3.5 | 15 | 5 | 20 | 12.00 | 120.00 | 900.00 | 660.00 | 900.00 | 300.00 | 1200.00 | 3121.80 | 4350.54 | 6421.80 | 5010.54 | 11432.34 |
| 2 | Office | Office Areas | 250 | 2.7 | 10 | 15 | 18 | 25.00 | 250.00 | 1875.00 | 1375.00 | 2500.00 | 3750.00 | 12150.00 | 6503.75 | 9063.63 | 26778.75 | 10438.63 | 37217.38 |
| 3 | Conference A | Conference Rooms | 30 | 2.7 | 10 | 10 | 15 | 15.00 | 150.00 | 975.00 | 825.00 | 300.00 | 300.00 | 450.00 | 3902.25 | 5438.18 | 5927.25 | 6263.18 | 12190.43 |
| 4 | Conference B | Conference Rooms | 45 | 2.7 | 10 | 10 | 15 | 22.50 | 225.00 | 1687.50 | 1237.50 | 450.00 | 450.00 | 675.00 | 5853.38 | 8157.26 | 9115.88 | 9394.76 | 18510.64 |
| 5 | Restaurant | Restaurants | 120 | 3.0 | 12 | 8 | 15 | 80.00 | 800.00 | 6000.00 | 4400.00 | 1440.00 | 960.00 | 1800.00 | 20812.00 | 75294.12 | 31012.00 | 79694.12 | 110706.12 |
| 6 | Kitchen | Kitchens (Commercial) | 50 | 2.7 | 8 | 20 | 18 | 10.00 | 150.00 | 750.00 | 550.00 | 400.00 | 1000.00 | 900.00 | 3902.25 | 5438.18 | 6952.25 | 5988.18 | 12940.43 |
| 7 | Corridor | Corridors | 90 | 2.7 | 6 | 0 | 10 | 0.00 | 45.00 | 0.00 | 0.00 | 540.00 | 0.00 | 900.00 | 1170.67 | 1631.45 | 2610.68 | 1631.45 | 4242.13 |
| 8 | Storage | Storage / Warehouses | 35 | 3.0 | 5 | 2 | 10 | 0.00 | 17.50 | 0.00 | 0.00 | 175.00 | 70.00 | 350.00 | 455.26 | 634.45 | 1050.26 | 634.45 | 1684.72 |

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
