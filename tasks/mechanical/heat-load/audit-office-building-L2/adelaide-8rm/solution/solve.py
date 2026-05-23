# ABOUTME: Reference solution for audit-office-building-L2 heat load audit task.
# ABOUTME: Reports the planted errors with correct values.

import json
from pathlib import Path

errors_found = [
    {
        "room_no": 3,
        "field": "num_people",
        "given_value": 5.0,
        "correct_value": 3.33,
        "explanation": "Wrong AS 1668.2 lookup: used Hotel Bedrooms density (10.0 m²/person) instead of Hotel Suites (15.0 m²/person)",
    },
    {
        "room_no": 5,
        "field": "ventilation_latent_w",
        "given_value": 0.0,
        "correct_value": 11684.67,
        "explanation": "Ventilation latent heat gain omitted (set to 0)",
    },
    {
        "room_no": 1,
        "field": "conduction_w",
        "given_value": 972.0,
        "correct_value": 360,
        "explanation": "Conduction uses volume (81.0 m³ × 12 W/m² = 972.0) instead of floor area (30 m² × 12 W/m² = 360)",
    },
]

output = {"errors_found": errors_found}

solution = f"""# Heat Load Audit — Adelaide

```json
{json.dumps(output, indent=2)}
```
"""

Path("/workspace/output.md").write_text(solution)
