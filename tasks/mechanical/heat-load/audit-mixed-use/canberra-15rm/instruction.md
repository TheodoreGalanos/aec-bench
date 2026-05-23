You are a senior mechanical engineer specializing in HVAC design review and quality assurance.

## Problem

Audit the following heat load calculation schedule for a mixed-use building in Canberra, Australia. The schedule was prepared by a junior engineer. The schedule contains several errors. Your task is to identify calculation errors — wrong AS 1668.2 lookups, arithmetic mistakes, wrong formulas, or omitted terms in the calculations — wrong AS 1668.2 lookups, arithmetic mistakes, or omitted terms.

Be careful: not everything that looks unusual is wrong. Some room types have high ventilation requirements per AS 1668.2 that may appear surprising but are correct.

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

| Room | Name | AS 1668.2 Type | Area (m²) | Height (m) | Light (W/m²) | SmPwr (W/m²) | Cond (W/m²) | People | OA (L/s) | Ppl Sens (W) | Ppl Lat (W) | Light (W) | SmPwr (W) | Cond (W) | Vent Sens (W) | Vent Lat (W) | Tot Sens (W) | Tot Lat (W) | Tot Cool (W) |
|------|------|----------------|-----------|------------|--------------|--------------|-------------|--------|----------|-------------|------------|-----------|-----------|----------|--------------|-------------|-------------|------------|-------------|
| 1 | Lobby | Reception / Lobby | 60 | 3.0 | 12 | 5 | 15 | 12.00 | 120.00 | 900.00 | 660.00 | 720.00 | 300.00 | 900.00 | 1742.40 | 1008.40 | 4562.40 | 1668.40 | 6230.80 |
| 2 | Classroom A | Classrooms | 70 | 2.7 | 12 | 10 | 15 | 35.00 | 420.00 | 2275.00 | 1925.00 | 840.00 | 700.00 | 1050.00 | 6098.40 | 3529.41 | 10963.40 | 5454.41 | 16417.81 |
| 3 | Classroom B | Classrooms | 60 | 2.7 | 12 | 10 | 15 | 30.00 | 360.00 | 2250.00 | 1650.00 | 720.00 | 600.00 | 900.00 | 0.00 | 3025.21 | 4470.00 | 4675.21 | 9145.21 |
| 4 | Classroom C | Classrooms | 50 | 2.7 | 12 | 10 | 15 | 25.00 | 300.00 | 1875.00 | 1375.00 | 600.00 | 500.00 | 750.00 | 4356.00 | 2521.01 | 8081.00 | 3896.01 | 11977.01 |
| 5 | Library | Libraries | 150 | 2.7 | 10 | 8 | 15 | 30.00 | 300.00 | 2250.00 | 1650.00 | 1500.00 | 1200.00 | 6075.00 | 4356.00 | 2521.01 | 15381.00 | 4171.01 | 19552.01 |
| 6 | Office A | Office Areas | 100 | 2.7 | 10 | 15 | 18 | 10.00 | 100.00 | 750.00 | 550.00 | 1000.00 | 1500.00 | 1800.00 | 1452.00 | 0.00 | 6502.00 | 550.00 | 7052.00 |
| 7 | Office B | Office Areas | 80 | 2.7 | 10 | 12 | 16 | 8.00 | 80.00 | 600.00 | 440.00 | 800.00 | 960.00 | 1280.00 | 1161.60 | 672.27 | 4801.60 | 1112.27 | 5913.87 |
| 8 | Meeting | Meeting Rooms | 25 | 2.7 | 10 | 8 | 15 | 8.33 | 83.33 | 625.00 | 458.33 | 250.00 | 200.00 | 375.00 | 1210.00 | 700.28 | 2660.00 | 1158.61 | 3818.61 |
| 9 | Break Room | Cafeteria / Break Rooms | 35 | 2.7 | 8 | 8 | 12 | 14.00 | 140.00 | 1050.00 | 770.00 | 280.00 | 280.00 | 420.00 | 2032.80 | 1176.47 | 4062.80 | 1946.47 | 6009.27 |
| 10 | Kitchen | Kitchens (Commercial) | 20 | 2.7 | 8 | 20 | 18 | 4.00 | 60.00 | 300.00 | 220.00 | 160.00 | 400.00 | 360.00 | 871.20 | 504.20 | 2091.20 | 724.20 | 2815.40 |
| 11 | Lecture Theatre | Lecture Theatres | 120 | 3.5 | 12 | 10 | 15 | 120.00 | 1440.00 | 9000.00 | 6600.00 | 1440.00 | 1200.00 | 1800.00 | 20908.80 | 95423.77 | 34348.80 | 102023.77 | 136372.57 |
| 12 | Corridor A | Corridors | 90 | 2.7 | 6 | 0 | 10 | 0.00 | 45.00 | 0.00 | 0.00 | 540.00 | 0.00 | 900.00 | 653.40 | 378.15 | 2093.40 | 378.15 | 2471.55 |
| 13 | Corridor B | Corridors | 50 | 2.7 | 6 | 0 | 10 | 0.00 | 25.00 | 0.00 | 0.00 | 300.00 | 0.00 | 500.00 | 363.00 | 210.08 | 1163.00 | 210.08 | 1373.08 |
| 14 | Server Room | Data Centres / Server Rooms | 15 | 3.0 | 5 | 250 | 25 | 0.00 | 15.00 | 0.00 | 0.00 | 75.00 | 3750.00 | 375.00 | 217.80 | 126.05 | 4417.80 | 126.05 | 4543.85 |
| 15 | Storage | Storage / Warehouses | 25 | 3.0 | 5 | 2 | 10 | 0.00 | 12.50 | 0.00 | 0.00 | 125.00 | 50.00 | 250.00 | 181.50 | 105.04 | 606.50 | 105.04 | 711.54 |

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
