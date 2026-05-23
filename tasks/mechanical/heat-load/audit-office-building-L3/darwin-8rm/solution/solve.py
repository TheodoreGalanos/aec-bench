# ABOUTME: Reference solution for audit-office-building-L3 heat load audit task.
# ABOUTME: Reports the planted errors with correct values.

import json
from pathlib import Path

errors_found = [
    {
        "room_no": 2,
        "field": "ventilation_latent_w",
        "given_value": 13882.35,
        "correct_value": 5781.51,
        "explanation": "Used raw outdoor enthalpy (82.6 kJ/kg) instead of Δh (34.39999999999999 kJ/kg) in latent formula",
    },
    {
        "room_no": 5,
        "field": "num_people",
        "given_value": 8.0,
        "correct_value": 16.0,
        "explanation": "Wrong AS 1668.2 lookup: used Office Areas density (10.0 m²/person) instead of Retail Shops (5.0 m²/person)",
    },
    {
        "room_no": 3,
        "field": "ventilation_latent_w",
        "given_value": 0.0,
        "correct_value": 7226.89,
        "explanation": "Ventilation latent heat gain omitted (set to 0)",
    },
]

output = {"errors_found": errors_found}

solution = f"""# Heat Load Audit — Darwin

```json
{json.dumps(output, indent=2)}
```
"""

Path("/workspace/output.md").write_text(solution)
