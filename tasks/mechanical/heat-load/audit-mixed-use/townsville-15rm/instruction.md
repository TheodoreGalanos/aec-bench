You are a senior mechanical engineer specializing in HVAC design review and quality assurance.

## Problem

Audit the following heat load calculation schedule for a mixed-use building in Townsville, Australia. The schedule was prepared by a junior engineer. The schedule contains several errors. Your task is to identify calculation errors — wrong AS 1668.2 lookups, arithmetic mistakes, wrong formulas, or omitted terms in the calculations — wrong AS 1668.2 lookups, arithmetic mistakes, or omitted terms.

Be careful: not everything that looks unusual is wrong. Some room types have high ventilation requirements per AS 1668.2 that may appear surprising but are correct.

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

| Room | Name | AS 1668.2 Type | Area (m²) | Height (m) | Light (W/m²) | SmPwr (W/m²) | Cond (W/m²) | People | OA (L/s) | Ppl Sens (W) | Ppl Lat (W) | Light (W) | SmPwr (W) | Cond (W) | Vent Sens (W) | Vent Lat (W) | Tot Sens (W) | Tot Lat (W) | Tot Cool (W) |
|------|------|----------------|-----------|------------|--------------|--------------|-------------|--------|----------|-------------|------------|-----------|-----------|----------|--------------|-------------|-------------|------------|-------------|
| 1 | Lobby | Reception / Lobby | 70 | 3.0 | 12 | 5 | 15 | 14.00 | 140.00 | 1050.00 | 770.00 | 840.00 | 350.00 | 1050.00 | 1965.04 | 5176.47 | 5255.04 | 5946.47 | 11201.51 |
| 2 | Office A | Office Areas | 160 | 2.7 | 10 | 15 | 18 | 16.00 | 160.00 | 1040.00 | 880.00 | 1600.00 | 2400.00 | 2880.00 | 2245.76 | 5915.97 | 10165.76 | 6795.97 | 16961.73 |
| 3 | Office B | Office Areas | 130 | 2.7 | 10 | 12 | 16 | 13.00 | 130.00 | 975.00 | 715.00 | 1300.00 | 1560.00 | 2080.00 | 1824.68 | 4806.72 | 7739.68 | 5521.72 | 13261.40 |
| 4 | Conference | Conference Rooms | 50 | 2.7 | 10 | 10 | 15 | 25.00 | 250.00 | 1875.00 | 1375.00 | 500.00 | 500.00 | 750.00 | 3509.00 | 23709.48 | 7134.00 | 25084.48 | 32218.48 |
| 5 | Meeting A | Meeting Rooms | 25 | 2.7 | 10 | 8 | 15 | 8.33 | 83.33 | 625.00 | 458.33 | 250.00 | 200.00 | 375.00 | 1169.67 | 3081.23 | 2619.67 | 3539.57 | 6159.23 |
| 6 | Meeting B | Meeting Rooms | 15 | 2.7 | 10 | 8 | 15 | 5.00 | 50.00 | 375.00 | 275.00 | 150.00 | 120.00 | 225.00 | 701.80 | 1848.74 | 1571.80 | 2123.74 | 3695.54 |
| 7 | Classroom | Classrooms | 90 | 2.7 | 12 | 10 | 15 | 9.00 | 540.00 | 3375.00 | 2475.00 | 1080.00 | 900.00 | 1350.00 | 7579.44 | 19966.39 | 14284.44 | 22441.39 | 36725.83 |
| 8 | Break Room | Cafeteria / Break Rooms | 40 | 2.7 | 8 | 8 | 12 | 16.00 | 160.00 | 1200.00 | 880.00 | 320.00 | 320.00 | 480.00 | 2245.76 | 0.00 | 4565.76 | 880.00 | 5445.76 |
| 9 | Kitchen | Kitchens (Commercial) | 30 | 2.7 | 8 | 20 | 18 | 6.00 | 90.00 | 450.00 | 330.00 | 240.00 | 600.00 | 540.00 | 1263.24 | 3327.73 | 3093.24 | 3657.73 | 6750.97 |
| 10 | Gymnasium | Gymnasiums | 200 | 4.0 | 10 | 5 | 15 | 40.00 | 600.00 | 3000.00 | 2200.00 | 2000.00 | 1000.00 | 3000.00 | 8421.60 | 22184.87 | 17421.60 | 24384.87 | 41806.47 |
| 11 | Corridor A | Corridors | 90 | 2.7 | 6 | 0 | 10 | 0.00 | 45.00 | 0.00 | 0.00 | 540.00 | 0.00 | 900.00 | 631.62 | 1663.87 | 2071.62 | 1663.87 | 3735.49 |
| 12 | Corridor B | Corridors | 60 | 2.7 | 6 | 0 | 10 | 0.00 | 30.00 | 0.00 | 0.00 | 360.00 | 0.00 | 600.00 | 421.08 | 1109.24 | 1381.08 | 1109.24 | 2490.32 |
| 13 | Server Room | Data Centres / Server Rooms | 20 | 3.0 | 5 | 250 | 25 | 0.00 | 20.00 | 0.00 | 0.00 | 100.00 | 5000.00 | 500.00 | 280.72 | 739.50 | 5880.72 | 739.50 | 6620.22 |
| 14 | Storage | Storage / Warehouses | 30 | 3.0 | 5 | 2 | 10 | 0.00 | 15.00 | 0.00 | 0.00 | 150.00 | 60.00 | 300.00 | 210.54 | 554.62 | 720.54 | 554.62 | 1275.16 |
| 15 | Retail | Retail Shops | 70 | 3.5 | 18 | 10 | 20 | 14.00 | 140.00 | 1050.00 | 770.00 | 1260.00 | 700.00 | 4900.00 | 1965.04 | 5176.47 | 9875.04 | 5946.47 | 15821.51 |

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
