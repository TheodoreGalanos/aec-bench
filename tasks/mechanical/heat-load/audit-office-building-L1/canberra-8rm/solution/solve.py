# ABOUTME: Reference solution for audit-office-building-L1 heat load audit task.
# ABOUTME: Reports the planted errors with correct values.

import json
from pathlib import Path

errors_found = [
    {
        "room_no": 1,
        "field": "people_sensible_w",
        "given_value": 1950.0,
        "correct_value": 2250.0,
        "explanation": "Used 65 W/person instead of 75 W/person for sensible heat gain",
    },
    {
        "room_no": 4,
        "field": "ventilation_latent_w",
        "given_value": 0.0,
        "correct_value": 672.27,
        "explanation": "Ventilation latent heat gain omitted (set to 0)",
    },
    {
        "room_no": 2,
        "field": "ventilation_sensible_w",
        "given_value": 0.0,
        "correct_value": 6098.4,
        "explanation": "Ventilation sensible uses indoor-indoor delta T (0°C) instead of outdoor-indoor (12.0°C)",
    },
]

output = {"errors_found": errors_found}

solution = f"""# Heat Load Audit — Canberra

```json
{json.dumps(output, indent=2)}
```
"""

Path("/workspace/output.md").write_text(solution)
