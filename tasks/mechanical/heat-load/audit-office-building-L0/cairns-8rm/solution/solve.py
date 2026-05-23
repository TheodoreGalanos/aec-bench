# ABOUTME: Reference solution for audit-office-building-L0 heat load audit task.
# ABOUTME: Reports the planted errors with correct values.

import json
from pathlib import Path

errors_found = [
    {
        "room_no": 2,
        "field": "num_people",
        "given_value": 6.0,
        "correct_value": 4.0,
        "explanation": "Wrong AS 1668.2 lookup: used Hotel Bedrooms density (10.0 m²/person) instead of Hotel Suites (15.0 m²/person)",
    },
    {
        "room_no": 3,
        "field": "conduction_w",
        "given_value": 4500.0,
        "correct_value": 1500,
        "explanation": "Conduction uses volume (300.0 m³ × 15 W/m² = 4500.0) instead of floor area (100 m² × 15 W/m² = 1500)",
    },
    {
        "room_no": 1,
        "field": "ventilation_latent_w",
        "given_value": 0.0,
        "correct_value": 1992.8,
        "explanation": "Ventilation latent heat gain omitted (set to 0)",
    },
]

output = {"errors_found": errors_found}

solution = f"""# Heat Load Audit — Cairns

```json
{json.dumps(output, indent=2)}
```
"""

Path("/workspace/output.md").write_text(solution)
