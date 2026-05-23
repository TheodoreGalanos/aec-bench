# ABOUTME: Reference solution for audit-office-building-L2 heat load audit task.
# ABOUTME: Reports the planted errors with correct values.

import json
from pathlib import Path

errors_found = [
    {
        "room_no": 5,
        "field": "ventilation_latent_w",
        "given_value": 75294.12,
        "correct_value": 29003.6,
        "explanation": "Used raw outdoor enthalpy (78.4 kJ/kg) instead of Δh (30.200000000000003 kJ/kg) in latent formula",
    },
    {
        "room_no": 2,
        "field": "conduction_w",
        "given_value": 12150.0,
        "correct_value": 4500,
        "explanation": "Conduction uses volume (675.0 m³ × 18 W/m² = 12150.0) instead of floor area (250 m² × 18 W/m² = 4500)",
    },
    {
        "room_no": 3,
        "field": "people_sensible_w",
        "given_value": 975.0,
        "correct_value": 1125.0,
        "explanation": "Used 65 W/person instead of 75 W/person for sensible heat gain",
    },
]

output = {"errors_found": errors_found}

solution = f"""# Heat Load Audit — Perth

```json
{json.dumps(output, indent=2)}
```
"""

Path("/workspace/output.md").write_text(solution)
