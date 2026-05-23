You are a senior mechanical engineer specializing in HVAC design review and quality assurance.

## Problem

Audit the following heat load calculation schedule for a mixed-use building in Adelaide, Australia. The schedule was prepared by a junior engineer. The schedule contains several errors. Your task is to identify calculation errors — wrong AS 1668.2 lookups, arithmetic mistakes, wrong formulas, or omitted terms in the calculations — wrong AS 1668.2 lookups, arithmetic mistakes, or omitted terms.

Be careful: not everything that looks unusual is wrong. Some room types have high ventilation requirements per AS 1668.2 that may appear surprising but are correct.

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

| Room | Name | AS 1668.2 Type | Area (m²) | Height (m) | Light (W/m²) | SmPwr (W/m²) | Cond (W/m²) | People | OA (L/s) | Ppl Sens (W) | Ppl Lat (W) | Light (W) | SmPwr (W) | Cond (W) | Vent Sens (W) | Vent Lat (W) | Tot Sens (W) | Tot Lat (W) | Tot Cool (W) |
|------|------|----------------|-----------|------------|--------------|--------------|-------------|--------|----------|-------------|------------|-----------|-----------|----------|--------------|-------------|-------------|------------|-------------|
| 1 | Lobby | Reception / Lobby | 90 | 3.5 | 15 | 5 | 20 | 18.00 | 180.00 | 1350.00 | 990.00 | 1350.00 | 450.00 | 1800.00 | 3397.68 | 3154.86 | 8347.68 | 4144.86 | 12492.54 |
| 2 | Hotel Room A | Hotel Bedrooms | 30 | 2.7 | 8 | 5 | 12 | 3.00 | 37.50 | 225.00 | 165.00 | 240.00 | 150.00 | 360.00 | 707.85 | 0.00 | 1682.85 | 165.00 | 1847.85 |
| 3 | Hotel Room B | Hotel Bedrooms | 35 | 2.7 | 8 | 5 | 12 | 3.50 | 43.75 | 262.50 | 192.50 | 280.00 | 175.00 | 420.00 | 825.83 | 766.81 | 1963.33 | 959.31 | 2922.63 |
| 4 | Hotel Suite A | Hotel Suites | 50 | 2.7 | 10 | 8 | 15 | 5.00 | 41.67 | 250.00 | 183.33 | 500.00 | 400.00 | 750.00 | 786.50 | 730.29 | 2686.50 | 913.62 | 3600.12 |
| 5 | Hotel Suite B | Hotel Suites | 65 | 2.7 | 10 | 8 | 15 | 4.33 | 54.17 | 325.00 | 238.33 | 650.00 | 520.00 | 975.00 | 1022.45 | 949.38 | 3492.45 | 1187.71 | 4680.16 |
| 6 | Restaurant | Restaurants | 150 | 3.0 | 12 | 8 | 15 | 100.00 | 1000.00 | 7500.00 | 5500.00 | 1800.00 | 1200.00 | 2250.00 | 18876.00 | 75390.16 | 31626.00 | 80890.16 | 112516.16 |
| 7 | Kitchen | Kitchens (Commercial) | 60 | 2.7 | 8 | 20 | 18 | 12.00 | 180.00 | 900.00 | 660.00 | 480.00 | 1200.00 | 1080.00 | 3397.68 | 3154.86 | 7057.68 | 3814.86 | 10872.54 |
| 8 | Conference | Conference Rooms | 40 | 2.7 | 10 | 10 | 15 | 20.00 | 200.00 | 1300.00 | 1100.00 | 400.00 | 400.00 | 600.00 | 3775.20 | 3505.40 | 6475.20 | 4605.40 | 11080.60 |
| 9 | Retail | Retail Shops | 80 | 3.5 | 18 | 10 | 20 | 16.00 | 160.00 | 1200.00 | 880.00 | 1440.00 | 800.00 | 5600.00 | 3020.16 | 2804.32 | 12060.16 | 3684.32 | 15744.48 |
| 10 | Gymnasium | Gymnasiums | 120 | 4.0 | 10 | 5 | 15 | 24.00 | 360.00 | 1800.00 | 1320.00 | 1200.00 | 600.00 | 1800.00 | 6795.36 | 6309.72 | 12195.36 | 7629.72 | 19825.08 |
| 11 | Corridor A | Corridors | 80 | 2.7 | 6 | 0 | 10 | 0.00 | 40.00 | 0.00 | 0.00 | 480.00 | 0.00 | 800.00 | 755.04 | 701.08 | 2035.04 | 701.08 | 2736.12 |
| 12 | Corridor B | Corridors | 60 | 2.7 | 6 | 0 | 10 | 0.00 | 30.00 | 0.00 | 0.00 | 360.00 | 0.00 | 600.00 | 566.28 | 525.81 | 1526.28 | 525.81 | 2052.09 |
| 13 | Storage | Storage / Warehouses | 40 | 3.0 | 5 | 2 | 10 | 0.00 | 20.00 | 0.00 | 0.00 | 200.00 | 80.00 | 400.00 | 377.52 | 350.54 | 1057.52 | 350.54 | 1408.06 |
| 14 | Server Room | Data Centres / Server Rooms | 25 | 3.0 | 5 | 200 | 20 | 0.00 | 25.00 | 0.00 | 0.00 | 125.00 | 5000.00 | 500.00 | 471.90 | 438.18 | 6096.90 | 438.18 | 6535.08 |
| 15 | Break Room | Cafeteria / Break Rooms | 30 | 2.7 | 8 | 8 | 12 | 12.00 | 120.00 | 900.00 | 660.00 | 240.00 | 240.00 | 360.00 | 2265.12 | 2103.24 | 4005.12 | 2763.24 | 6768.36 |

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
