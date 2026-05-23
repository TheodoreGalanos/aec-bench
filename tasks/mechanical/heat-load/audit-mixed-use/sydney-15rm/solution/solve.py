# ABOUTME: Reference solution for audit-mixed-use heat load audit task.
# ABOUTME: Reports the planted errors with correct values.

import json
from pathlib import Path

errors_found = [
    {
        "room_no": 5,
        "field": "num_people",
        "given_value": 16.67,
        "correct_value": 25.0,
        "explanation": "Wrong AS 1668.2 lookup: used Meeting Rooms density (3.0 m²/person) instead of Conference Rooms (2.0 m²/person)",
    },
    {
        "room_no": 8,
        "field": "ventilation_latent_w",
        "given_value": 0.0,
        "correct_value": 3380.55,
        "explanation": "Ventilation latent heat gain omitted (set to 0)",
    },
    {
        "room_no": 4,
        "field": "conduction_w",
        "given_value": 5832.0,
        "correct_value": 2160,
        "explanation": "Conduction uses volume (324.0 m³ × 18 W/m² = 5832.0) instead of floor area (120 m² × 18 W/m² = 2160)",
    },
    {
        "room_no": 10,
        "field": "ventilation_latent_w",
        "given_value": 7109.24,
        "correct_value": 1901.56,
        "explanation": "Used raw outdoor enthalpy (65.8 kJ/kg) instead of Δh (17.599999999999994 kJ/kg) in latent formula",
    },
    {
        "room_no": 6,
        "field": "people_sensible_w",
        "given_value": 1137.5,
        "correct_value": 1312.5,
        "explanation": "Used 65 W/person instead of 75 W/person for sensible heat gain",
    },
]

output = {"errors_found": errors_found}

solution = f"""# Heat Load Audit — Sydney

```json
{json.dumps(output, indent=2)}
```
"""

Path("/workspace/output.md").write_text(solution)
