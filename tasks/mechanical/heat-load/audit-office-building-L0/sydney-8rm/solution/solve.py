# ABOUTME: Reference solution for audit-office-building-L0 heat load audit task.
# ABOUTME: Reports the planted errors with correct values.

import json
from pathlib import Path

errors_found = [
    {
        "room_no": 3,
        "field": "conduction_w",
        "given_value": 4320.0,
        "correct_value": 1600,
        "explanation": "Conduction uses volume (270.0 m³ × 16 W/m² = 4320.0) instead of floor area (100 m² × 16 W/m² = 1600)",
    },
    {
        "room_no": 4,
        "field": "people_sensible_w",
        "given_value": 1300.0,
        "correct_value": 1500.0,
        "explanation": "Used 65 W/person instead of 75 W/person for sensible heat gain",
    },
    {
        "room_no": 6,
        "field": "ventilation_latent_w",
        "given_value": 0.0,
        "correct_value": 1584.63,
        "explanation": "Ventilation latent heat gain omitted (set to 0)",
    },
]

output = {"errors_found": errors_found}

solution = f"""# Heat Load Audit — Sydney

```json
{json.dumps(output, indent=2)}
```
"""

Path("/workspace/output.md").write_text(solution)
