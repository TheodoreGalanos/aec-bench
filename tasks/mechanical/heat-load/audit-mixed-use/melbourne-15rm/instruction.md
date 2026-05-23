You are a senior mechanical engineer specializing in HVAC design review and quality assurance.

## Problem

Audit the following heat load calculation schedule for a mixed-use building in Melbourne, Australia. The schedule was prepared by a junior engineer. The schedule contains several errors. Your task is to identify calculation errors — wrong AS 1668.2 lookups, arithmetic mistakes, wrong formulas, or omitted terms in the calculations — wrong AS 1668.2 lookups, arithmetic mistakes, or omitted terms.

Be careful: not everything that looks unusual is wrong. Some room types have high ventilation requirements per AS 1668.2 that may appear surprising but are correct.

## Design Conditions

| Parameter | Value | Unit |
|-----------|-------|------|
| Location | Melbourne, Australia | - |
| Outdoor dry-bulb temperature | 36.4 | °C |
| Outdoor wet-bulb temperature | 20.8 | °C |
| Indoor dry-bulb temperature | 24.0 | °C |
| Outdoor air enthalpy | 58.6 | kJ/kg |
| Indoor air enthalpy | 48.2 | kJ/kg |

## Pre-Filled Heat Load Schedule

| Room | Name | AS 1668.2 Type | Area (m²) | Height (m) | Light (W/m²) | SmPwr (W/m²) | Cond (W/m²) | People | OA (L/s) | Ppl Sens (W) | Ppl Lat (W) | Light (W) | SmPwr (W) | Cond (W) | Vent Sens (W) | Vent Lat (W) | Tot Sens (W) | Tot Lat (W) | Tot Cool (W) |
|------|------|----------------|-----------|------------|--------------|--------------|-------------|--------|----------|-------------|------------|-----------|-----------|----------|--------------|-------------|-------------|------------|-------------|
| 1 | Lobby | Reception / Lobby | 80 | 3.0 | 12 | 5 | 15 | 16.00 | 160.00 | 1200.00 | 880.00 | 960.00 | 400.00 | 1200.00 | 2400.64 | 1997.60 | 6160.64 | 2877.60 | 9038.24 |
| 2 | Office A | Office Areas | 250 | 2.7 | 10 | 15 | 18 | 25.00 | 250.00 | 1625.00 | 1375.00 | 2500.00 | 3750.00 | 4500.00 | 3751.00 | 3121.25 | 16126.00 | 4496.25 | 20622.25 |
| 3 | Office B | Office Areas | 180 | 2.7 | 10 | 12 | 16 | 18.00 | 180.00 | 1350.00 | 990.00 | 1800.00 | 2160.00 | 2880.00 | 2700.72 | 2247.30 | 10890.72 | 3237.30 | 14128.02 |
| 4 | Conference | Conference Rooms | 55 | 2.7 | 10 | 10 | 15 | 27.50 | 275.00 | 2062.50 | 1512.50 | 550.00 | 550.00 | 825.00 | 0.00 | 3433.37 | 3987.50 | 4945.87 | 8933.37 |
| 5 | Meeting A | Meeting Rooms | 25 | 2.7 | 10 | 8 | 15 | 8.33 | 83.33 | 625.00 | 458.33 | 250.00 | 200.00 | 375.00 | 1250.33 | 1040.42 | 2700.33 | 1498.75 | 4199.08 |
| 6 | Meeting B | Meeting Rooms | 20 | 2.7 | 10 | 8 | 15 | 6.67 | 66.67 | 500.00 | 366.67 | 200.00 | 160.00 | 300.00 | 1000.27 | 832.33 | 2160.27 | 1199.00 | 3359.27 |
| 7 | Break Room | Cafeteria / Break Rooms | 45 | 2.7 | 8 | 8 | 12 | 18.00 | 180.00 | 1350.00 | 990.00 | 360.00 | 360.00 | 540.00 | 2700.72 | 12662.67 | 5310.72 | 13652.67 | 18963.39 |
| 8 | Retail A | Retail Shops | 100 | 3.5 | 18 | 10 | 20 | 10.00 | 200.00 | 1500.00 | 1100.00 | 1800.00 | 1000.00 | 2000.00 | 3000.80 | 2497.00 | 9300.80 | 3597.00 | 12897.80 |
| 9 | Retail B | Retail Shops | 80 | 3.5 | 18 | 10 | 20 | 16.00 | 160.00 | 1200.00 | 880.00 | 1440.00 | 800.00 | 5600.00 | 2400.64 | 1997.60 | 11440.64 | 2877.60 | 14318.24 |
| 10 | Gymnasium | Gymnasiums | 150 | 4.0 | 10 | 5 | 15 | 30.00 | 450.00 | 2250.00 | 1650.00 | 1500.00 | 750.00 | 2250.00 | 6751.80 | 5618.25 | 13501.80 | 7268.25 | 20770.05 |
| 11 | Corridor A | Corridors | 90 | 2.7 | 6 | 0 | 10 | 0.00 | 45.00 | 0.00 | 0.00 | 540.00 | 0.00 | 900.00 | 675.18 | 561.82 | 2115.18 | 561.82 | 2677.00 |
| 12 | Corridor B | Corridors | 70 | 2.7 | 6 | 0 | 10 | 0.00 | 35.00 | 0.00 | 0.00 | 420.00 | 0.00 | 700.00 | 525.14 | 436.97 | 1645.14 | 436.97 | 2082.11 |
| 13 | Kitchen | Kitchens (Commercial) | 35 | 2.7 | 8 | 20 | 18 | 7.00 | 105.00 | 525.00 | 385.00 | 280.00 | 700.00 | 630.00 | 1575.42 | 1310.92 | 3710.42 | 1695.92 | 5406.34 |
| 14 | Server Room | Data Centres / Server Rooms | 20 | 3.0 | 5 | 300 | 25 | 0.00 | 20.00 | 0.00 | 0.00 | 100.00 | 6000.00 | 500.00 | 300.08 | 249.70 | 6900.08 | 249.70 | 7149.78 |
| 15 | Storage | Storage / Warehouses | 30 | 3.0 | 5 | 2 | 10 | 0.00 | 15.00 | 0.00 | 0.00 | 150.00 | 60.00 | 300.00 | 225.06 | 187.27 | 735.06 | 187.27 | 922.33 |

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
