# ABOUTME: Reference solution for audit-mixed-use heat load audit task.
# ABOUTME: Reports the planted errors with correct values.

import json
from pathlib import Path

errors_found = [
    {
        "room_no": 4,
        "field": "num_people",
        "given_value": 8.0,
        "correct_value": 40.0,
        "explanation": "Wrong AS 1668.2 lookup: used Office Areas density (10.0 m²/person) instead of Classrooms (2.0 m²/person)",
    },
    {
        "room_no": 6,
        "field": "ventilation_latent_w",
        "given_value": 0.0,
        "correct_value": 6626.65,
        "explanation": "Ventilation latent heat gain omitted (set to 0)",
    },
    {
        "room_no": 7,
        "field": "conduction_w",
        "given_value": 1620.0,
        "correct_value": 600,
        "explanation": "Conduction uses volume (108.0 m³ × 15 W/m² = 1620.0) instead of floor area (40 m² × 15 W/m² = 600)",
    },
    {
        "room_no": 2,
        "field": "ventilation_latent_w",
        "given_value": 17094.84,
        "correct_value": 5522.21,
        "explanation": "Used raw outdoor enthalpy (71.2 kJ/kg) instead of Δh (23.0 kJ/kg) in latent formula",
    },
    {
        "room_no": 5,
        "field": "ventilation_sensible_w",
        "given_value": 0.0,
        "correct_value": 6229.08,
        "explanation": "Ventilation sensible uses indoor-indoor delta T (0°C) instead of outdoor-indoor (14.299999999999997°C)",
    },
]

output = {"errors_found": errors_found}

solution = f"""# Heat Load Audit — Brisbane

```json
{json.dumps(output, indent=2)}
```
"""

Path("/workspace/output.md").write_text(solution)
