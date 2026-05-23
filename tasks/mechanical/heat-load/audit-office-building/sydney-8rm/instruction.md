You are a senior mechanical engineer specializing in HVAC design review and quality assurance.

## Problem

Audit the following heat load calculation schedule for a commercial office building in Sydney, Australia. The schedule was prepared by a junior engineer. Your task is to identify errors in the calculations — wrong AS 1668.2 lookups, arithmetic mistakes, or omitted terms.

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

| Room No | Name | AS 1668.2 Type | Area (m²) | Height (m) | Lighting (W/m²) | Small Power (W/m²) | Conduction (W/m²) | People | OA (L/s) | People Sens (W) | People Lat (W) | Lighting (W) | Sm Power (W) | Conduction (W) | Vent Sens (W) | Vent Lat (W) | Total Sens (W) | Total Lat (W) | Total Cool (W) |
|---------|------|----------------|-----------|------------|-----------------|--------------------|--------------------|--------|----------|-----------------|----------------|--------------|---------------|----------------|---------------|--------------|----------------|----------------|----------------|
| 1 | Lobby | Reception / Lobby | 50 | 3.0 | 12 | 5 | 15 | 10.00 | 100.00 | 750.00 | 550.00 | 600.00 | 250.00 | 750.00 | 1427.80 | 2112.85 | 3777.80 | 2662.85 | 6440.65 |
| 2 | Office A | Office Areas | 180 | 2.7 | 10 | 15 | 18 | 18.00 | 180.00 | 1350.00 | 990.00 | 1800.00 | 2700.00 | 3240.00 | 2570.04 | 3803.12 | 11660.04 | 4793.12 | 16453.16 |
| 3 | Office B | Office Areas | 100 | 2.7 | 10 | 12 | 16 | 10.00 | 100.00 | 750.00 | 550.00 | 1000.00 | 1200.00 | 4320.00 | 1427.80 | 2112.85 | 8697.80 | 2662.85 | 11360.65 |
| 4 | Conference | Conference Rooms | 40 | 2.7 | 10 | 10 | 15 | 20.00 | 200.00 | 1300.00 | 1100.00 | 400.00 | 400.00 | 600.00 | 2855.60 | 4225.69 | 5555.60 | 5325.69 | 10881.29 |
| 5 | Break Room | Cafeteria / Break Rooms | 35 | 2.7 | 8 | 8 | 12 | 14.00 | 140.00 | 1050.00 | 770.00 | 280.00 | 280.00 | 420.00 | 1998.92 | 2957.98 | 4028.92 | 3727.98 | 7756.90 |
| 6 | Kitchen | Kitchens (Commercial) | 25 | 2.7 | 8 | 20 | 18 | 5.00 | 75.00 | 375.00 | 275.00 | 200.00 | 500.00 | 450.00 | 1070.85 | 0.00 | 2595.85 | 275.00 | 2870.85 |
| 7 | Corridor | Corridors | 70 | 2.7 | 6 | 0 | 10 | 0.00 | 35.00 | 0.00 | 0.00 | 420.00 | 0.00 | 700.00 | 499.73 | 739.50 | 1619.73 | 739.50 | 2359.23 |
| 8 | Storage | Storage / Warehouses | 30 | 3.0 | 5 | 2 | 10 | 0.00 | 15.00 | 0.00 | 0.00 | 150.00 | 60.00 | 300.00 | 214.17 | 316.93 | 724.17 | 316.93 | 1041.10 |

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
