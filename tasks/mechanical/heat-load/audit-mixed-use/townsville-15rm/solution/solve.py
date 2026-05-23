# ABOUTME: Reference solution for audit-mixed-use heat load audit task.
# ABOUTME: Reports the planted errors with correct values.

import json
from pathlib import Path

errors_found = [
    {
        "room_no": 7,
        "field": "num_people",
        "given_value": 9.0,
        "correct_value": 45.0,
        "explanation": "Wrong AS 1668.2 lookup: used Office Areas density (10.0 m²/person) instead of Classrooms (2.0 m²/person)",
    },
    {
        "room_no": 4,
        "field": "ventilation_latent_w",
        "given_value": 23709.48,
        "correct_value": 9243.7,
        "explanation": "Used raw outdoor enthalpy (79.0 kJ/kg) instead of Δh (30.799999999999997 kJ/kg) in latent formula",
    },
    {
        "room_no": 8,
        "field": "ventilation_latent_w",
        "given_value": 0.0,
        "correct_value": 5915.97,
        "explanation": "Ventilation latent heat gain omitted (set to 0)",
    },
    {
        "room_no": 15,
        "field": "conduction_w",
        "given_value": 4900.0,
        "correct_value": 1400,
        "explanation": "Conduction uses volume (245.0 m³ × 20 W/m² = 4900.0) instead of floor area (70 m² × 20 W/m² = 1400)",
    },
    {
        "room_no": 2,
        "field": "people_sensible_w",
        "given_value": 1040.0,
        "correct_value": 1200.0,
        "explanation": "Used 65 W/person instead of 75 W/person for sensible heat gain",
    },
]

output = {"errors_found": errors_found}

solution = f"""# Heat Load Audit — Townsville

```json
{json.dumps(output, indent=2)}
```
"""

Path("/workspace/output.md").write_text(solution)
