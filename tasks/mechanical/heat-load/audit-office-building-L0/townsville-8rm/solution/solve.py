# ABOUTME: Reference solution for audit-office-building-L0 heat load audit task.
# ABOUTME: Reports the planted errors with correct values.

import json
from pathlib import Path

errors_found = [
    {
        "room_no": 1,
        "field": "num_people",
        "given_value": 20.0,
        "correct_value": 40.0,
        "explanation": "Wrong AS 1668.2 lookup: used Office Areas density (10.0 m²/person) instead of Gymnasiums (5.0 m²/person)",
    },
    {
        "room_no": 2,
        "field": "ventilation_latent_w",
        "given_value": 0.0,
        "correct_value": 17747.9,
        "explanation": "Ventilation latent heat gain omitted (set to 0)",
    },
    {
        "room_no": 3,
        "field": "ventilation_latent_w",
        "given_value": 4741.9,
        "correct_value": 1848.74,
        "explanation": "Used raw outdoor enthalpy (79.0 kJ/kg) instead of Δh (30.799999999999997 kJ/kg) in latent formula",
    },
]

output = {"errors_found": errors_found}

solution = f"""# Heat Load Audit — Townsville

```json
{json.dumps(output, indent=2)}
```
"""

Path("/workspace/output.md").write_text(solution)
