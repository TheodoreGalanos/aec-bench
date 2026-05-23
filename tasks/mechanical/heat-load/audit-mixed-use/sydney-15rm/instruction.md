You are a senior mechanical engineer specializing in HVAC design review and quality assurance.

## Problem

Audit the following heat load calculation schedule for a mixed-use building in Sydney, Australia. The schedule was prepared by a junior engineer. The schedule contains several errors. Your task is to identify calculation errors — wrong AS 1668.2 lookups, arithmetic mistakes, wrong formulas, or omitted terms in the calculations — wrong AS 1668.2 lookups, arithmetic mistakes, or omitted terms.

Be careful: not everything that looks unusual is wrong. Some room types have high ventilation requirements per AS 1668.2 that may appear surprising but are correct.

## Design Conditions

| Parameter | Value | Unit |
|-----------|-------|------|
| Location | Sydney, Australia | - |
| Outdoor dry-bulb temperature | 35.8 | °C |
| Outdoor wet-bulb temperature | 22.4 | °C |
| Indoor dry-bulb temperature | 24.0 | °C |
| Outdoor air enthalpy | 65.8 | kJ/kg |
| Indoor air enthalpy | 48.2 | kJ/kg |

## Pre-Filled Heat Load Schedule

| Room | Name | AS 1668.2 Type | Area (m²) | Height (m) | Light (W/m²) | SmPwr (W/m²) | Cond (W/m²) | People | OA (L/s) | Ppl Sens (W) | Ppl Lat (W) | Light (W) | SmPwr (W) | Cond (W) | Vent Sens (W) | Vent Lat (W) | Tot Sens (W) | Tot Lat (W) | Tot Cool (W) |
|------|------|----------------|-----------|------------|--------------|--------------|-------------|--------|----------|-------------|------------|-----------|-----------|----------|--------------|-------------|-------------|------------|-------------|
| 1 | Lobby | Reception / Lobby | 100 | 3.5 | 15 | 5 | 20 | 20.00 | 200.00 | 1500.00 | 1100.00 | 1500.00 | 500.00 | 2000.00 | 2855.60 | 4225.69 | 8355.60 | 5325.69 | 13681.29 |
| 2 | Office A | Office Areas | 200 | 2.7 | 10 | 15 | 18 | 20.00 | 200.00 | 1500.00 | 1100.00 | 2000.00 | 3000.00 | 3600.00 | 2855.60 | 4225.69 | 12955.60 | 5325.69 | 18281.29 |
| 3 | Office B | Office Areas | 150 | 2.7 | 10 | 12 | 16 | 15.00 | 150.00 | 1125.00 | 825.00 | 1500.00 | 1800.00 | 2400.00 | 2141.70 | 3169.27 | 8966.70 | 3994.27 | 12960.97 |
| 4 | Office C | Office Areas | 120 | 2.7 | 10 | 15 | 18 | 12.00 | 120.00 | 900.00 | 660.00 | 1200.00 | 1800.00 | 5832.00 | 1713.36 | 2535.41 | 11445.36 | 3195.41 | 14640.77 |
| 5 | Conference A | Conference Rooms | 50 | 2.7 | 10 | 10 | 15 | 16.67 | 250.00 | 1875.00 | 1375.00 | 500.00 | 500.00 | 750.00 | 3569.50 | 5282.11 | 7194.50 | 6657.11 | 13851.61 |
| 6 | Conference B | Conference Rooms | 35 | 2.7 | 10 | 10 | 15 | 17.50 | 175.00 | 1137.50 | 962.50 | 350.00 | 350.00 | 525.00 | 2498.65 | 3697.48 | 4861.15 | 4659.98 | 9521.13 |
| 7 | Meeting Room | Meeting Rooms | 20 | 2.7 | 10 | 8 | 15 | 6.67 | 66.67 | 500.00 | 366.67 | 200.00 | 160.00 | 300.00 | 951.87 | 1408.56 | 2111.87 | 1775.23 | 3887.10 |
| 8 | Break Room A | Cafeteria / Break Rooms | 40 | 2.7 | 8 | 8 | 12 | 16.00 | 160.00 | 1200.00 | 880.00 | 320.00 | 320.00 | 480.00 | 2284.48 | 0.00 | 4604.48 | 880.00 | 5484.48 |
| 9 | Break Room B | Cafeteria / Break Rooms | 30 | 2.7 | 8 | 8 | 12 | 12.00 | 120.00 | 900.00 | 660.00 | 240.00 | 240.00 | 360.00 | 1713.36 | 2535.41 | 3453.36 | 3195.41 | 6648.77 |
| 10 | Kitchen | Kitchens (Commercial) | 30 | 2.7 | 8 | 20 | 18 | 6.00 | 90.00 | 450.00 | 330.00 | 240.00 | 600.00 | 540.00 | 1285.02 | 7109.24 | 3115.02 | 7439.24 | 10554.26 |
| 11 | Library | Libraries | 80 | 2.7 | 10 | 8 | 15 | 16.00 | 160.00 | 1200.00 | 880.00 | 800.00 | 640.00 | 1200.00 | 2284.48 | 3380.55 | 6124.48 | 4260.55 | 10385.03 |
| 12 | Corridor A | Corridors | 100 | 2.7 | 6 | 0 | 10 | 0.00 | 50.00 | 0.00 | 0.00 | 600.00 | 0.00 | 1000.00 | 713.90 | 1056.42 | 2313.90 | 1056.42 | 3370.32 |
| 13 | Corridor B | Corridors | 60 | 2.7 | 6 | 0 | 10 | 0.00 | 30.00 | 0.00 | 0.00 | 360.00 | 0.00 | 600.00 | 428.34 | 633.85 | 1388.34 | 633.85 | 2022.19 |
| 14 | Server Room | Data Centres / Server Rooms | 25 | 3.0 | 5 | 250 | 25 | 0.00 | 25.00 | 0.00 | 0.00 | 125.00 | 6250.00 | 625.00 | 356.95 | 528.21 | 7356.95 | 528.21 | 7885.16 |
| 15 | Storage | Storage / Warehouses | 35 | 3.0 | 5 | 2 | 10 | 0.00 | 17.50 | 0.00 | 0.00 | 175.00 | 70.00 | 350.00 | 249.86 | 369.75 | 844.87 | 369.75 | 1214.61 |

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
