You are a senior mechanical engineer specializing in HVAC design review and quality assurance.

## Problem

Audit the following heat load calculation schedule for a mixed-use building in Cairns, Australia. The schedule was prepared by a junior engineer. The schedule contains several errors. Your task is to identify calculation errors — wrong AS 1668.2 lookups, arithmetic mistakes, wrong formulas, or omitted terms in the calculations — wrong AS 1668.2 lookups, arithmetic mistakes, or omitted terms.

Be careful: not everything that looks unusual is wrong. Some room types have high ventilation requirements per AS 1668.2 that may appear surprising but are correct.

## Design Conditions

| Parameter | Value | Unit |
|-----------|-------|------|
| Location | Cairns, Australia | - |
| Outdoor dry-bulb temperature | 34.0 | °C |
| Outdoor wet-bulb temperature | 26.8 | °C |
| Indoor dry-bulb temperature | 24.0 | °C |
| Outdoor air enthalpy | 81.4 | kJ/kg |
| Indoor air enthalpy | 48.2 | kJ/kg |

## Pre-Filled Heat Load Schedule

| Room | Name | AS 1668.2 Type | Area (m²) | Height (m) | Light (W/m²) | SmPwr (W/m²) | Cond (W/m²) | People | OA (L/s) | Ppl Sens (W) | Ppl Lat (W) | Light (W) | SmPwr (W) | Cond (W) | Vent Sens (W) | Vent Lat (W) | Tot Sens (W) | Tot Lat (W) | Tot Cool (W) |
|------|------|----------------|-----------|------------|--------------|--------------|-------------|--------|----------|-------------|------------|-----------|-----------|----------|--------------|-------------|-------------|------------|-------------|
| 1 | Lobby | Reception / Lobby | 90 | 3.0 | 12 | 5 | 15 | 18.00 | 180.00 | 1350.00 | 990.00 | 1080.00 | 450.00 | 1350.00 | 2178.00 | 7174.07 | 6408.00 | 8164.07 | 14572.07 |
| 2 | Hotel Room A | Hotel Bedrooms | 30 | 2.7 | 8 | 5 | 12 | 3.00 | 37.50 | 225.00 | 165.00 | 240.00 | 150.00 | 360.00 | 453.75 | 0.00 | 1428.75 | 165.00 | 1593.75 |
| 3 | Hotel Room B | Hotel Bedrooms | 35 | 2.7 | 8 | 5 | 12 | 3.50 | 43.75 | 262.50 | 192.50 | 280.00 | 175.00 | 420.00 | 529.38 | 1743.70 | 1666.88 | 1936.20 | 3603.07 |
| 4 | Hotel Suite | Hotel Suites | 55 | 2.7 | 10 | 8 | 15 | 5.50 | 45.83 | 275.00 | 201.67 | 550.00 | 440.00 | 825.00 | 554.58 | 1826.73 | 2644.58 | 2028.40 | 4672.98 |
| 5 | Restaurant | Restaurants | 160 | 3.0 | 12 | 8 | 15 | 106.67 | 1066.67 | 8000.00 | 5866.67 | 1920.00 | 1280.00 | 2400.00 | 12906.67 | 104233.69 | 26506.67 | 110100.36 | 136607.03 |
| 6 | Kitchen | Kitchens (Commercial) | 60 | 2.7 | 8 | 20 | 18 | 12.00 | 180.00 | 900.00 | 660.00 | 480.00 | 1200.00 | 1080.00 | 2178.00 | 7174.07 | 5838.00 | 7834.07 | 13672.07 |
| 7 | Retail A | Retail Shops | 80 | 3.5 | 18 | 10 | 20 | 16.00 | 160.00 | 1200.00 | 880.00 | 1440.00 | 800.00 | 5600.00 | 1936.00 | 6376.95 | 10976.00 | 7256.95 | 18232.95 |
| 8 | Retail B | Retail Shops | 50 | 3.5 | 18 | 10 | 20 | 10.00 | 100.00 | 750.00 | 550.00 | 900.00 | 500.00 | 1000.00 | 1210.00 | 3985.59 | 4360.00 | 4535.59 | 8895.59 |
| 9 | Gymnasium | Gymnasiums | 150 | 4.0 | 10 | 5 | 15 | 30.00 | 450.00 | 2250.00 | 1650.00 | 1500.00 | 750.00 | 2250.00 | 5445.00 | 17935.17 | 12195.00 | 19585.17 | 31780.17 |
| 10 | Conference | Conference Rooms | 40 | 2.7 | 10 | 10 | 15 | 20.00 | 200.00 | 1300.00 | 1100.00 | 400.00 | 400.00 | 600.00 | 2420.00 | 7971.19 | 5120.00 | 9071.19 | 14191.19 |
| 11 | Corridor A | Corridors | 100 | 2.7 | 6 | 0 | 10 | 0.00 | 50.00 | 0.00 | 0.00 | 600.00 | 0.00 | 1000.00 | 605.00 | 1992.80 | 2205.00 | 1992.80 | 4197.80 |
| 12 | Corridor B | Corridors | 60 | 2.7 | 6 | 0 | 10 | 0.00 | 30.00 | 0.00 | 0.00 | 360.00 | 0.00 | 600.00 | 363.00 | 1195.68 | 1323.00 | 1195.68 | 2518.68 |
| 13 | Break Room | Cafeteria / Break Rooms | 25 | 2.7 | 8 | 8 | 12 | 10.00 | 100.00 | 750.00 | 550.00 | 200.00 | 200.00 | 300.00 | 1210.00 | 3985.59 | 2660.00 | 4535.59 | 7195.59 |
| 14 | Server Room | Data Centres / Server Rooms | 20 | 3.0 | 5 | 200 | 20 | 0.00 | 20.00 | 0.00 | 0.00 | 100.00 | 4000.00 | 400.00 | 242.00 | 797.12 | 4742.00 | 797.12 | 5539.12 |
| 15 | Storage | Storage / Warehouses | 25 | 3.0 | 5 | 2 | 10 | 0.00 | 12.50 | 0.00 | 0.00 | 125.00 | 50.00 | 250.00 | 151.25 | 498.20 | 576.25 | 498.20 | 1074.45 |

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
