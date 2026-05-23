# ABOUTME: Reference solution for audit-office-building-L2 heat load audit task.
# ABOUTME: Reports the planted errors with correct values.

import json
from pathlib import Path

errors_found = [
    {
        "room_no": 1,
        "field": "conduction_w",
        "given_value": 6300.0,
        "correct_value": 1800,
        "explanation": "Conduction uses volume (315.0 m³ × 20 W/m² = 6300.0) instead of floor area (90 m² × 20 W/m² = 1800)",
    },
    {
        "room_no": 3,
        "field": "people_sensible_w",
        "given_value": 390.0,
        "correct_value": 450.0,
        "explanation": "Used 65 W/person instead of 75 W/person for sensible heat gain",
    },
    {
        "room_no": 5,
        "field": "ventilation_sensible_w",
        "given_value": 0.0,
        "correct_value": 677.6,
        "explanation": "Ventilation sensible uses indoor-indoor delta T (0°C) instead of outdoor-indoor (7.0°C)",
    },
]

output = {"errors_found": errors_found}

solution = f"""# Heat Load Audit — Hobart

```json
{json.dumps(output, indent=2)}
```
"""

Path("/workspace/output.md").write_text(solution)
