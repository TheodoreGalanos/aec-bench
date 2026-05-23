You are a senior mechanical engineer specializing in HVAC design review and quality assurance.

## Problem

Audit the following heat load calculation schedule for a mixed-use building in Hobart, Australia. The schedule was prepared by a junior engineer. The schedule contains several errors. Your task is to identify calculation errors — wrong AS 1668.2 lookups, arithmetic mistakes, wrong formulas, or omitted terms in the calculations — wrong AS 1668.2 lookups, arithmetic mistakes, or omitted terms.

Be careful: not everything that looks unusual is wrong. Some room types have high ventilation requirements per AS 1668.2 that may appear surprising but are correct.

## Design Conditions

| Parameter | Value | Unit |
|-----------|-------|------|
| Location | Hobart, Australia | - |
| Outdoor dry-bulb temperature | 31.0 | °C |
| Outdoor wet-bulb temperature | 18.5 | °C |
| Indoor dry-bulb temperature | 24.0 | °C |
| Outdoor air enthalpy | 50.8 | kJ/kg |
| Indoor air enthalpy | 48.2 | kJ/kg |

## Pre-Filled Heat Load Schedule

| Room | Name | AS 1668.2 Type | Area (m²) | Height (m) | Light (W/m²) | SmPwr (W/m²) | Cond (W/m²) | People | OA (L/s) | Ppl Sens (W) | Ppl Lat (W) | Light (W) | SmPwr (W) | Cond (W) | Vent Sens (W) | Vent Lat (W) | Tot Sens (W) | Tot Lat (W) | Tot Cool (W) |
|------|------|----------------|-----------|------------|--------------|--------------|-------------|--------|----------|-------------|------------|-----------|-----------|----------|--------------|-------------|-------------|------------|-------------|
| 1 | Lobby | Reception / Lobby | 60 | 3.0 | 12 | 5 | 15 | 12.00 | 120.00 | 900.00 | 660.00 | 720.00 | 300.00 | 900.00 | 1016.40 | 374.55 | 3836.40 | 1034.55 | 4870.95 |
| 2 | Retail A | Retail Shops | 120 | 3.5 | 18 | 10 | 20 | 24.00 | 240.00 | 1800.00 | 1320.00 | 2160.00 | 1200.00 | 8400.00 | 2032.80 | 749.10 | 15592.80 | 2069.10 | 17661.90 |
| 3 | Retail B | Retail Shops | 90 | 3.5 | 18 | 10 | 20 | 18.00 | 180.00 | 1350.00 | 990.00 | 1620.00 | 900.00 | 1800.00 | 1524.60 | 561.82 | 7194.60 | 1551.82 | 8746.42 |
| 4 | Retail C | Retail Shops | 60 | 3.5 | 18 | 10 | 20 | 6.00 | 120.00 | 900.00 | 660.00 | 1080.00 | 600.00 | 1200.00 | 1016.40 | 374.55 | 4796.40 | 1034.55 | 5830.95 |
| 5 | Office A | Office Areas | 100 | 2.7 | 10 | 15 | 18 | 10.00 | 100.00 | 650.00 | 550.00 | 1000.00 | 1500.00 | 1800.00 | 847.00 | 312.12 | 5797.00 | 862.12 | 6659.12 |
| 6 | Office B | Office Areas | 80 | 2.7 | 10 | 12 | 16 | 8.00 | 80.00 | 600.00 | 440.00 | 800.00 | 960.00 | 1280.00 | 677.60 | 249.70 | 4317.60 | 689.70 | 5007.30 |
| 7 | Conference | Conference Rooms | 30 | 2.7 | 10 | 10 | 15 | 15.00 | 150.00 | 1125.00 | 825.00 | 300.00 | 300.00 | 450.00 | 0.00 | 468.19 | 2175.00 | 1293.19 | 3468.19 |
| 8 | Meeting | Meeting Rooms | 15 | 2.7 | 10 | 8 | 15 | 5.00 | 50.00 | 375.00 | 275.00 | 150.00 | 120.00 | 225.00 | 423.50 | 0.00 | 1293.50 | 275.00 | 1568.50 |
| 9 | Break Room | Cafeteria / Break Rooms | 25 | 2.7 | 8 | 8 | 12 | 10.00 | 100.00 | 750.00 | 550.00 | 200.00 | 200.00 | 300.00 | 847.00 | 312.12 | 2297.00 | 862.12 | 3159.12 |
| 10 | Kitchen | Kitchens (Commercial) | 20 | 2.7 | 8 | 20 | 18 | 4.00 | 60.00 | 300.00 | 220.00 | 160.00 | 400.00 | 360.00 | 508.20 | 187.27 | 1728.20 | 407.27 | 2135.47 |
| 11 | Corridor A | Corridors | 80 | 2.7 | 6 | 0 | 10 | 0.00 | 40.00 | 0.00 | 0.00 | 480.00 | 0.00 | 800.00 | 338.80 | 124.85 | 1618.80 | 124.85 | 1743.65 |
| 12 | Corridor B | Corridors | 50 | 2.7 | 6 | 0 | 10 | 0.00 | 25.00 | 0.00 | 0.00 | 300.00 | 0.00 | 500.00 | 211.75 | 78.03 | 1011.75 | 78.03 | 1089.78 |
| 13 | Storage A | Storage / Warehouses | 25 | 3.0 | 5 | 2 | 10 | 0.00 | 12.50 | 0.00 | 0.00 | 125.00 | 50.00 | 250.00 | 105.87 | 39.02 | 530.88 | 39.02 | 569.89 |
| 14 | Storage B | Storage / Warehouses | 20 | 3.0 | 5 | 2 | 10 | 0.00 | 10.00 | 0.00 | 0.00 | 100.00 | 40.00 | 200.00 | 84.70 | 31.21 | 424.70 | 31.21 | 455.91 |
| 15 | Server Room | Data Centres / Server Rooms | 15 | 3.0 | 5 | 300 | 25 | 0.00 | 15.00 | 0.00 | 0.00 | 75.00 | 4500.00 | 375.00 | 127.05 | 46.82 | 5077.05 | 46.82 | 5123.87 |

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
