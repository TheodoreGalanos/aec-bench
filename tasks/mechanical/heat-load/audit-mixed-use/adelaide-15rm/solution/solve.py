# ABOUTME: Reference solution for audit-mixed-use heat load audit task.
# ABOUTME: Reports the planted errors with correct values.

import json
from pathlib import Path

errors_found = [
    {
        "room_no": 4,
        "field": "num_people",
        "given_value": 5.0,
        "correct_value": 3.33,
        "explanation": "Wrong AS 1668.2 lookup: used Hotel Bedrooms density (10.0 m²/person) instead of Hotel Suites (15.0 m²/person)",
    },
    {
        "room_no": 6,
        "field": "ventilation_latent_w",
        "given_value": 75390.16,
        "correct_value": 17527.01,
        "explanation": "Used raw outdoor enthalpy (62.8 kJ/kg) instead of Δh (14.599999999999994 kJ/kg) in latent formula",
    },
    {
        "room_no": 2,
        "field": "ventilation_latent_w",
        "given_value": 0.0,
        "correct_value": 657.26,
        "explanation": "Ventilation latent heat gain omitted (set to 0)",
    },
    {
        "room_no": 9,
        "field": "conduction_w",
        "given_value": 5600.0,
        "correct_value": 1600,
        "explanation": "Conduction uses volume (280.0 m³ × 20 W/m² = 5600.0) instead of floor area (80 m² × 20 W/m² = 1600)",
    },
    {
        "room_no": 8,
        "field": "people_sensible_w",
        "given_value": 1300.0,
        "correct_value": 1500.0,
        "explanation": "Used 65 W/person instead of 75 W/person for sensible heat gain",
    },
]

output = {"errors_found": errors_found}

solution = f"""# Heat Load Audit — Adelaide

```json
{json.dumps(output, indent=2)}
```
"""

Path("/workspace/output.md").write_text(solution)
