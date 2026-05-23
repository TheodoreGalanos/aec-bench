You are a senior mechanical engineer specializing in HVAC design review and quality assurance.

## Problem

Audit the following heat load calculation schedule for a commercial office building in Townsville, Australia. The schedule was prepared by a junior engineer. Your task is to identify errors in the calculations — wrong AS 1668.2 lookups, arithmetic mistakes, or omitted terms.

## Design Conditions

| Parameter | Value | Unit |
|-----------|-------|------|
| Location | Townsville, Australia | - |
| Outdoor dry-bulb temperature | 35.6 | °C |
| Outdoor wet-bulb temperature | 26.2 | °C |
| Indoor dry-bulb temperature | 24.0 | °C |
| Outdoor air enthalpy | 79.0 | kJ/kg |
| Indoor air enthalpy | 48.2 | kJ/kg |

## Pre-Filled Heat Load Schedule

| Room No | Name | AS 1668.2 Type | Area (m²) | Height (m) | Lighting (W/m²) | Small Power (W/m²) | Conduction (W/m²) | People | OA (L/s) | People Sens (W) | People Lat (W) | Lighting (W) | Sm Power (W) | Conduction (W) | Vent Sens (W) | Vent Lat (W) | Total Sens (W) | Total Lat (W) | Total Cool (W) |
|---------|------|----------------|-----------|------------|-----------------|--------------------|--------------------|--------|----------|-----------------|----------------|--------------|---------------|----------------|---------------|--------------|----------------|----------------|----------------|
| 1 | Gymnasium | Gymnasiums | 200 | 4.0 | 10 | 5 | 15 | 20.00 | 600.00 | 3000.00 | 2200.00 | 2000.00 | 1000.00 | 3000.00 | 8421.60 | 22184.87 | 17421.60 | 24384.87 | 41806.47 |
| 2 | Classroom | Classrooms | 80 | 2.7 | 12 | 10 | 15 | 40.00 | 480.00 | 3000.00 | 2200.00 | 960.00 | 800.00 | 1200.00 | 6737.28 | 0.00 | 12697.28 | 2200.00 | 14897.28 |
| 3 | Office | Office Areas | 50 | 2.7 | 10 | 15 | 18 | 5.00 | 50.00 | 375.00 | 275.00 | 500.00 | 750.00 | 900.00 | 701.80 | 4741.90 | 3226.80 | 5016.90 | 8243.70 |
| 4 | Meeting | Meeting Rooms | 20 | 2.7 | 10 | 8 | 15 | 6.67 | 66.67 | 500.00 | 366.67 | 200.00 | 160.00 | 300.00 | 935.73 | 2464.99 | 2095.73 | 2831.65 | 4927.39 |
| 5 | Break Room | Cafeteria / Break Rooms | 30 | 2.7 | 8 | 8 | 12 | 12.00 | 120.00 | 900.00 | 660.00 | 240.00 | 240.00 | 360.00 | 1684.32 | 4436.97 | 3424.32 | 5096.97 | 8521.29 |
| 6 | Corridor | Corridors | 60 | 2.7 | 6 | 0 | 10 | 0.00 | 30.00 | 0.00 | 0.00 | 360.00 | 0.00 | 600.00 | 421.08 | 1109.24 | 1381.08 | 1109.24 | 2490.32 |
| 7 | Storage | Storage / Warehouses | 25 | 3.0 | 5 | 2 | 10 | 0.00 | 12.50 | 0.00 | 0.00 | 125.00 | 50.00 | 250.00 | 175.45 | 462.18 | 600.45 | 462.18 | 1062.63 |
| 8 | Server Room | Data Centres / Server Rooms | 15 | 3.0 | 5 | 300 | 25 | 0.00 | 15.00 | 0.00 | 0.00 | 75.00 | 4500.00 | 375.00 | 210.54 | 554.62 | 5160.54 | 554.62 | 5715.16 |

## Available Tool

A heat load calculation tool is available at `/workspace/heat_load_calc.py`. Run it with:

```bash
python3 /workspace/heat_load_calc.py --help
python3 /workspace/heat_load_calc.py --list-room-types
```

You may use this tool to verify any room's calculations independently.

## Applicable Standards

- AS 1668.2 — The use of ventilation and airconditioning in buildings, Part 2: Mechanical ventilation in buildings

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
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
