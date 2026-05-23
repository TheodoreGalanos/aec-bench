You are a senior mechanical engineer specializing in HVAC design review and quality assurance.

## Problem

Audit the following heat load calculation schedule for a mixed-use building in Darwin, Australia. The schedule was prepared by a junior engineer. The schedule contains several errors. Your task is to identify calculation errors — wrong AS 1668.2 lookups, arithmetic mistakes, wrong formulas, or omitted terms in the calculations — wrong AS 1668.2 lookups, arithmetic mistakes, or omitted terms.

Be careful: not everything that looks unusual is wrong. Some room types have high ventilation requirements per AS 1668.2 that may appear surprising but are correct.

## Design Conditions

| Parameter | Value | Unit |
|-----------|-------|------|
| Location | Darwin, Australia | - |
| Outdoor dry-bulb temperature | 34.4 | °C |
| Outdoor wet-bulb temperature | 27.0 | °C |
| Indoor dry-bulb temperature | 24.0 | °C |
| Outdoor air enthalpy | 82.6 | kJ/kg |
| Indoor air enthalpy | 48.2 | kJ/kg |

## Pre-Filled Heat Load Schedule

| Room | Name | AS 1668.2 Type | Area (m²) | Height (m) | Light (W/m²) | SmPwr (W/m²) | Cond (W/m²) | People | OA (L/s) | Ppl Sens (W) | Ppl Lat (W) | Light (W) | SmPwr (W) | Cond (W) | Vent Sens (W) | Vent Lat (W) | Tot Sens (W) | Tot Lat (W) | Tot Cool (W) |
|------|------|----------------|-----------|------------|--------------|--------------|-------------|--------|----------|-------------|------------|-----------|-----------|----------|--------------|-------------|-------------|------------|-------------|
| 1 | Lobby | Reception / Lobby | 80 | 3.0 | 12 | 5 | 15 | 16.00 | 160.00 | 1200.00 | 880.00 | 960.00 | 400.00 | 1200.00 | 2013.44 | 6607.44 | 5773.44 | 7487.44 | 13260.88 |
| 2 | Office A | Office Areas | 180 | 2.7 | 10 | 15 | 18 | 18.00 | 180.00 | 1350.00 | 990.00 | 1800.00 | 2700.00 | 8748.00 | 2265.12 | 7433.37 | 16863.12 | 8423.37 | 25286.49 |
| 3 | Office B | Office Areas | 120 | 2.7 | 10 | 12 | 16 | 12.00 | 120.00 | 900.00 | 660.00 | 1200.00 | 1440.00 | 1920.00 | 1510.08 | 4955.58 | 6970.08 | 5615.58 | 12585.66 |
| 4 | Conference | Conference Rooms | 45 | 2.7 | 10 | 10 | 15 | 22.50 | 225.00 | 1687.50 | 1237.50 | 450.00 | 450.00 | 675.00 | 2831.40 | 0.00 | 6093.90 | 1237.50 | 7331.40 |
| 5 | Meeting | Meeting Rooms | 20 | 2.7 | 10 | 8 | 15 | 6.67 | 66.67 | 500.00 | 366.67 | 200.00 | 160.00 | 300.00 | 838.93 | 2753.10 | 1998.93 | 3119.77 | 5118.70 |
| 6 | Break Room | Cafeteria / Break Rooms | 35 | 2.7 | 8 | 8 | 12 | 14.00 | 140.00 | 1050.00 | 770.00 | 280.00 | 280.00 | 420.00 | 1761.76 | 5781.51 | 3791.76 | 6551.51 | 10343.27 |
| 7 | Restaurant | Restaurants | 140 | 3.0 | 12 | 8 | 15 | 93.33 | 933.33 | 7000.00 | 5133.33 | 1680.00 | 1120.00 | 2100.00 | 11745.07 | 92549.02 | 23645.07 | 97682.35 | 121327.42 |
| 8 | Kitchen | Kitchens (Commercial) | 50 | 2.7 | 8 | 20 | 18 | 10.00 | 150.00 | 750.00 | 550.00 | 400.00 | 1000.00 | 900.00 | 1887.60 | 6194.48 | 4937.60 | 6744.48 | 11682.08 |
| 9 | Retail | Retail Shops | 90 | 3.5 | 18 | 10 | 20 | 9.00 | 180.00 | 1350.00 | 990.00 | 1620.00 | 900.00 | 1800.00 | 2265.12 | 7433.37 | 7935.12 | 8423.37 | 16358.49 |
| 10 | Gymnasium | Gymnasiums | 180 | 4.0 | 10 | 5 | 15 | 36.00 | 540.00 | 2700.00 | 1980.00 | 1800.00 | 900.00 | 2700.00 | 6795.36 | 22300.12 | 14895.36 | 24280.12 | 39175.48 |
| 11 | Corridor A | Corridors | 100 | 2.7 | 6 | 0 | 10 | 0.00 | 50.00 | 0.00 | 0.00 | 600.00 | 0.00 | 1000.00 | 629.20 | 2064.83 | 2229.20 | 2064.83 | 4294.03 |
| 12 | Corridor B | Corridors | 70 | 2.7 | 6 | 0 | 10 | 0.00 | 35.00 | 0.00 | 0.00 | 420.00 | 0.00 | 700.00 | 440.44 | 1445.38 | 1560.44 | 1445.38 | 3005.82 |
| 13 | Hotel Room | Hotel Bedrooms | 35 | 2.7 | 8 | 5 | 12 | 3.50 | 43.75 | 227.50 | 192.50 | 280.00 | 175.00 | 420.00 | 550.55 | 1806.72 | 1653.05 | 1999.22 | 3652.27 |
| 14 | Server Room | Data Centres / Server Rooms | 20 | 3.0 | 5 | 200 | 20 | 0.00 | 20.00 | 0.00 | 0.00 | 100.00 | 4000.00 | 400.00 | 251.68 | 825.93 | 4751.68 | 825.93 | 5577.61 |
| 15 | Storage | Storage / Warehouses | 30 | 3.0 | 5 | 2 | 10 | 0.00 | 15.00 | 0.00 | 0.00 | 150.00 | 60.00 | 300.00 | 188.76 | 619.45 | 698.76 | 619.45 | 1318.21 |

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
