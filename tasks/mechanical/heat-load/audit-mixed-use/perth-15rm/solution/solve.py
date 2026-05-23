# ABOUTME: Reference solution for audit-mixed-use heat load audit task.
# ABOUTME: Reports the planted errors with correct values.

import json
from pathlib import Path

errors_found = [
    {
        "room_no": 7,
        "field": "ventilation_latent_w",
        "given_value": 112941.18,
        "correct_value": 43505.4,
        "explanation": "Used raw outdoor enthalpy (78.4 kJ/kg) instead of Δh (30.200000000000003 kJ/kg) in latent formula",
    },
    {
        "room_no": 3,
        "field": "conduction_w",
        "given_value": 12150.0,
        "correct_value": 4500,
        "explanation": "Conduction uses volume (675.0 m³ × 18 W/m² = 12150.0) instead of floor area (250 m² × 18 W/m² = 4500)",
    },
    {
        "room_no": 15,
        "field": "people_sensible_w",
        "given_value": 2275.0,
        "correct_value": 2625.0,
        "explanation": "Used 65 W/person instead of 75 W/person for sensible heat gain",
    },
    {
        "room_no": 8,
        "field": "num_people",
        "given_value": 8.0,
        "correct_value": 16.0,
        "explanation": "Wrong AS 1668.2 lookup: used Office Areas density (10.0 m²/person) instead of Kitchens (Commercial) (5.0 m²/person)",
    },
    {
        "room_no": 14,
        "field": "ventilation_latent_w",
        "given_value": 0.0,
        "correct_value": 1450.18,
        "explanation": "Ventilation latent heat gain omitted (set to 0)",
    },
]

output = {"errors_found": errors_found}

solution = f"""# Heat Load Audit — Perth

```json
{json.dumps(output, indent=2)}
```
"""

Path("/workspace/output.md").write_text(solution)
