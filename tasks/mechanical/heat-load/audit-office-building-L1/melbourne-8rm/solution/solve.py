# ABOUTME: Reference solution for audit-office-building-L1 heat load audit task.
# ABOUTME: Reports the planted errors with correct values.

import json
from pathlib import Path

errors_found = [
    {
        "room_no": 2,
        "field": "num_people",
        "given_value": 66.67,
        "correct_value": 20.0,
        "explanation": "Wrong AS 1668.2 lookup: used Meeting Rooms density (3.0 m²/person) instead of Office Areas (10.0 m²/person)",
    },
    {
        "room_no": 5,
        "field": "ventilation_sensible_w",
        "given_value": 0.0,
        "correct_value": 3751.0,
        "explanation": "Ventilation sensible uses indoor-indoor delta T (0°C) instead of outdoor-indoor (12.399999999999999°C)",
    },
    {
        "room_no": 4,
        "field": "ventilation_latent_w",
        "given_value": 0.0,
        "correct_value": 1498.2,
        "explanation": "Ventilation latent heat gain omitted (set to 0)",
    },
]

output = {"errors_found": errors_found}

solution = f"""# Heat Load Audit — Melbourne

```json
{json.dumps(output, indent=2)}
```
"""

Path("/workspace/output.md").write_text(solution)
