You are a senior mechanical engineer specializing in HVAC design review and quality assurance.

## Problem

Audit the following heat load calculation schedule for a commercial office building in Darwin, Australia. The schedule was prepared by a junior engineer. Your task is to identify errors in the calculations — wrong AS 1668.2 lookups, arithmetic mistakes, or omitted terms.

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

| Room No | Name | AS 1668.2 Type | Area (m²) | Height (m) | Lighting (W/m²) | Small Power (W/m²) | Conduction (W/m²) | People | OA (L/s) | People Sens (W) | People Lat (W) | Lighting (W) | Sm Power (W) | Conduction (W) | Vent Sens (W) | Vent Lat (W) | Total Sens (W) | Total Lat (W) | Total Cool (W) |
|---------|------|----------------|-----------|------------|-----------------|--------------------|--------------------|--------|----------|-----------------|----------------|--------------|---------------|----------------|---------------|--------------|----------------|----------------|----------------|
| 1 | Lobby | Reception / Lobby | 55 | 3.0 | 12 | 5 | 15 | 11.00 | 110.00 | 825.00 | 605.00 | 660.00 | 275.00 | 825.00 | 1384.24 | 4542.62 | 3969.24 | 5147.62 | 9116.86 |
| 2 | Office | Office Areas | 140 | 2.7 | 10 | 15 | 18 | 14.00 | 140.00 | 1050.00 | 770.00 | 1400.00 | 2100.00 | 2520.00 | 1761.76 | 13882.35 | 8831.76 | 14652.35 | 23484.11 |
| 3 | Conference | Conference Rooms | 35 | 2.7 | 10 | 10 | 15 | 17.50 | 175.00 | 1312.50 | 962.50 | 350.00 | 350.00 | 525.00 | 2202.20 | 0.00 | 4739.70 | 962.50 | 5702.20 |
| 4 | Break Room | Cafeteria / Break Rooms | 40 | 2.7 | 8 | 8 | 12 | 16.00 | 160.00 | 1200.00 | 880.00 | 320.00 | 320.00 | 480.00 | 2013.44 | 6607.44 | 4333.44 | 7487.44 | 11820.88 |
| 5 | Retail | Retail Shops | 80 | 3.5 | 18 | 10 | 20 | 8.00 | 160.00 | 1200.00 | 880.00 | 1440.00 | 800.00 | 1600.00 | 2013.44 | 6607.44 | 7053.44 | 7487.44 | 14540.88 |
| 6 | Corridor | Corridors | 60 | 2.7 | 6 | 0 | 10 | 0.00 | 30.00 | 0.00 | 0.00 | 360.00 | 0.00 | 600.00 | 377.52 | 1238.90 | 1337.52 | 1238.90 | 2576.42 |
| 7 | Server Room | Data Centres / Server Rooms | 20 | 3.0 | 5 | 200 | 20 | 0.00 | 20.00 | 0.00 | 0.00 | 100.00 | 4000.00 | 400.00 | 251.68 | 825.93 | 4751.68 | 825.93 | 5577.61 |
| 8 | Storage | Storage / Warehouses | 25 | 3.0 | 5 | 2 | 10 | 0.00 | 12.50 | 0.00 | 0.00 | 125.00 | 50.00 | 250.00 | 157.30 | 516.21 | 582.30 | 516.21 | 1098.51 |

## Applicable Standards

- AS 1668.2 — The use of ventilation and airconditioning in buildings, Part 2: Mechanical ventilation in buildings

## Constraints

- No internet access is available. Work from engineering knowledge only.
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
