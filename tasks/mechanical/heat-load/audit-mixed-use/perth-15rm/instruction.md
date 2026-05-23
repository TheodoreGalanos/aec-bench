You are a senior mechanical engineer specializing in HVAC design review and quality assurance.

## Problem

Audit the following heat load calculation schedule for a mixed-use building in Perth, Australia. The schedule was prepared by a junior engineer. The schedule contains several errors. Your task is to identify calculation errors — wrong AS 1668.2 lookups, arithmetic mistakes, wrong formulas, or omitted terms in the calculations — wrong AS 1668.2 lookups, arithmetic mistakes, or omitted terms.

Be careful: not everything that looks unusual is wrong. Some room types have high ventilation requirements per AS 1668.2 that may appear surprising but are correct.

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

| Room | Name | AS 1668.2 Type | Area (m²) | Height (m) | Light (W/m²) | SmPwr (W/m²) | Cond (W/m²) | People | OA (L/s) | Ppl Sens (W) | Ppl Lat (W) | Light (W) | SmPwr (W) | Cond (W) | Vent Sens (W) | Vent Lat (W) | Tot Sens (W) | Tot Lat (W) | Tot Cool (W) |
|------|------|----------------|-----------|------------|--------------|--------------|-------------|--------|----------|-------------|------------|-----------|-----------|----------|--------------|-------------|-------------|------------|-------------|
| 1 | Main Lobby | Reception / Lobby | 120 | 3.5 | 15 | 5 | 20 | 24.00 | 240.00 | 1800.00 | 1320.00 | 1800.00 | 600.00 | 2400.00 | 6243.60 | 8701.08 | 12843.60 | 10021.08 | 22864.68 |
| 2 | Office A | Office Areas | 300 | 2.7 | 10 | 15 | 18 | 30.00 | 300.00 | 2250.00 | 1650.00 | 3000.00 | 4500.00 | 5400.00 | 7804.50 | 10876.35 | 22954.50 | 12526.35 | 35480.85 |
| 3 | Office B | Office Areas | 250 | 2.7 | 10 | 15 | 18 | 25.00 | 250.00 | 1875.00 | 1375.00 | 2500.00 | 3750.00 | 12150.00 | 6503.75 | 9063.63 | 26778.75 | 10438.63 | 37217.38 |
| 4 | Board Room | Conference Rooms | 60 | 2.7 | 12 | 10 | 15 | 30.00 | 300.00 | 2250.00 | 1650.00 | 720.00 | 600.00 | 900.00 | 7804.50 | 10876.35 | 12274.50 | 12526.35 | 24800.85 |
| 5 | Meeting 1 | Meeting Rooms | 20 | 2.7 | 10 | 8 | 15 | 6.67 | 66.67 | 500.00 | 366.67 | 200.00 | 160.00 | 300.00 | 1734.33 | 2416.97 | 2894.33 | 2783.63 | 5677.97 |
| 6 | Meeting 2 | Meeting Rooms | 15 | 2.7 | 10 | 8 | 15 | 5.00 | 50.00 | 375.00 | 275.00 | 150.00 | 120.00 | 225.00 | 1300.75 | 1812.73 | 2170.75 | 2087.73 | 4258.48 |
| 7 | Restaurant | Restaurants | 180 | 3.0 | 12 | 8 | 15 | 120.00 | 1200.00 | 9000.00 | 6600.00 | 2160.00 | 1440.00 | 2700.00 | 31218.00 | 112941.18 | 46518.00 | 119541.18 | 166059.18 |
| 8 | Kitchen | Kitchens (Commercial) | 80 | 3.0 | 8 | 20 | 18 | 8.00 | 240.00 | 1200.00 | 880.00 | 640.00 | 1600.00 | 1440.00 | 6243.60 | 8701.08 | 11123.60 | 9581.08 | 20704.68 |
| 9 | Retail 1 | Retail Shops | 100 | 3.5 | 18 | 10 | 20 | 20.00 | 200.00 | 1500.00 | 1100.00 | 1800.00 | 1000.00 | 2000.00 | 5203.00 | 7250.90 | 11503.00 | 8350.90 | 19853.90 |
| 10 | Retail 2 | Retail Shops | 75 | 3.5 | 18 | 10 | 20 | 15.00 | 150.00 | 1125.00 | 825.00 | 1350.00 | 750.00 | 1500.00 | 3902.25 | 5438.18 | 8627.25 | 6263.18 | 14890.43 |
| 11 | Gymnasium | Gymnasiums | 200 | 4.0 | 10 | 5 | 15 | 40.00 | 600.00 | 3000.00 | 2200.00 | 2000.00 | 1000.00 | 3000.00 | 15609.00 | 21752.70 | 24609.00 | 23952.70 | 48561.70 |
| 12 | Corridor | Corridors | 150 | 2.7 | 6 | 0 | 10 | 0.00 | 75.00 | 0.00 | 0.00 | 900.00 | 0.00 | 1500.00 | 1951.12 | 2719.09 | 4351.12 | 2719.09 | 7070.21 |
| 13 | Storage | Storage / Warehouses | 50 | 3.0 | 5 | 2 | 10 | 0.00 | 25.00 | 0.00 | 0.00 | 250.00 | 100.00 | 500.00 | 650.38 | 906.36 | 1500.38 | 906.36 | 2406.74 |
| 14 | Server Room | Data Centres / Server Rooms | 40 | 3.0 | 5 | 300 | 25 | 0.00 | 40.00 | 0.00 | 0.00 | 200.00 | 12000.00 | 1000.00 | 1040.60 | 0.00 | 14240.60 | 0.00 | 14240.60 |
| 15 | Classroom | Classrooms | 70 | 3.0 | 10 | 10 | 15 | 35.00 | 420.00 | 2275.00 | 1925.00 | 700.00 | 700.00 | 1050.00 | 10926.30 | 15226.89 | 15651.30 | 17151.89 | 32803.19 |

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
