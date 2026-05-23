You are a senior mechanical engineer specializing in HVAC design review and quality assurance.

## Problem

Audit the following heat load calculation schedule for a mixed-use building in Brisbane, Australia. The schedule was prepared by a junior engineer. The schedule contains several errors. Your task is to identify calculation errors — wrong AS 1668.2 lookups, arithmetic mistakes, wrong formulas, or omitted terms in the calculations — wrong AS 1668.2 lookups, arithmetic mistakes, or omitted terms.

Be careful: not everything that looks unusual is wrong. Some room types have high ventilation requirements per AS 1668.2 that may appear surprising but are correct.

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

| Room | Name | AS 1668.2 Type | Area (m²) | Height (m) | Light (W/m²) | SmPwr (W/m²) | Cond (W/m²) | People | OA (L/s) | Ppl Sens (W) | Ppl Lat (W) | Light (W) | SmPwr (W) | Cond (W) | Vent Sens (W) | Vent Lat (W) | Tot Sens (W) | Tot Lat (W) | Tot Cool (W) |
|------|------|----------------|-----------|------------|--------------|--------------|-------------|--------|----------|-------------|------------|-----------|-----------|----------|--------------|-------------|-------------|------------|-------------|
| 1 | Lobby | Reception / Lobby | 70 | 3.0 | 12 | 5 | 15 | 14.00 | 140.00 | 1050.00 | 770.00 | 840.00 | 350.00 | 1050.00 | 2422.42 | 3865.55 | 5712.42 | 4635.55 | 10347.97 |
| 2 | Office A | Office Areas | 200 | 2.7 | 10 | 15 | 18 | 20.00 | 200.00 | 1500.00 | 1100.00 | 2000.00 | 3000.00 | 3600.00 | 3460.60 | 17094.84 | 13560.60 | 18194.84 | 31755.44 |
| 3 | Office B | Office Areas | 160 | 2.7 | 10 | 12 | 16 | 16.00 | 160.00 | 1200.00 | 880.00 | 1600.00 | 1920.00 | 2560.00 | 2768.48 | 4417.77 | 10048.48 | 5297.77 | 15346.25 |
| 4 | Classroom A | Classrooms | 80 | 2.7 | 12 | 10 | 15 | 8.00 | 480.00 | 3000.00 | 2200.00 | 960.00 | 800.00 | 1200.00 | 8305.44 | 13253.30 | 14265.44 | 15453.30 | 29718.74 |
| 5 | Classroom B | Classrooms | 60 | 2.7 | 12 | 10 | 15 | 30.00 | 360.00 | 2250.00 | 1650.00 | 720.00 | 600.00 | 900.00 | 0.00 | 9939.98 | 4470.00 | 11589.98 | 16059.98 |
| 6 | Library | Libraries | 120 | 2.7 | 10 | 8 | 15 | 24.00 | 240.00 | 1800.00 | 1320.00 | 1200.00 | 960.00 | 1800.00 | 4152.72 | 0.00 | 9912.72 | 1320.00 | 11232.72 |
| 7 | Conference | Conference Rooms | 40 | 2.7 | 10 | 10 | 15 | 20.00 | 200.00 | 1500.00 | 1100.00 | 400.00 | 400.00 | 1620.00 | 3460.60 | 5522.21 | 7380.60 | 6622.21 | 14002.81 |
| 8 | Meeting | Meeting Rooms | 20 | 2.7 | 10 | 8 | 15 | 6.67 | 66.67 | 500.00 | 366.67 | 200.00 | 160.00 | 300.00 | 1153.53 | 1840.74 | 2313.53 | 2207.40 | 4520.94 |
| 9 | Break Room | Cafeteria / Break Rooms | 35 | 2.7 | 8 | 8 | 12 | 14.00 | 140.00 | 1050.00 | 770.00 | 280.00 | 280.00 | 420.00 | 2422.42 | 3865.55 | 4452.42 | 4635.55 | 9087.97 |
| 10 | Kitchen | Kitchens (Commercial) | 25 | 2.7 | 8 | 20 | 18 | 5.00 | 75.00 | 375.00 | 275.00 | 200.00 | 500.00 | 450.00 | 1297.72 | 2070.83 | 2822.72 | 2345.83 | 5168.55 |
| 11 | Corridor A | Corridors | 80 | 2.7 | 6 | 0 | 10 | 0.00 | 40.00 | 0.00 | 0.00 | 480.00 | 0.00 | 800.00 | 692.12 | 1104.44 | 1972.12 | 1104.44 | 3076.56 |
| 12 | Corridor B | Corridors | 50 | 2.7 | 6 | 0 | 10 | 0.00 | 25.00 | 0.00 | 0.00 | 300.00 | 0.00 | 500.00 | 432.57 | 690.28 | 1232.57 | 690.28 | 1922.85 |
| 13 | Gymnasium | Gymnasiums | 180 | 4.0 | 10 | 5 | 15 | 36.00 | 540.00 | 2700.00 | 1980.00 | 1800.00 | 900.00 | 2700.00 | 9343.62 | 14909.96 | 17443.62 | 16889.96 | 34333.58 |
| 14 | Server Room | Data Centres / Server Rooms | 20 | 3.0 | 5 | 250 | 25 | 0.00 | 20.00 | 0.00 | 0.00 | 100.00 | 5000.00 | 500.00 | 346.06 | 552.22 | 5946.06 | 552.22 | 6498.28 |
| 15 | Storage | Storage / Warehouses | 30 | 3.0 | 5 | 2 | 10 | 0.00 | 15.00 | 0.00 | 0.00 | 150.00 | 60.00 | 300.00 | 259.54 | 414.17 | 769.54 | 414.17 | 1183.71 |

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
