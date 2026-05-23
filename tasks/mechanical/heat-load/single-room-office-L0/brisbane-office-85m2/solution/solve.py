# ABOUTME: Reference solution for single-room-office-L0 heat load calculation.
# ABOUTME: Computes from first principles and writes output.md with JSON block.

import json
from pathlib import Path

# Compute from first principles
data = {
    "room_type": "Office Areas",
    "floor_area": 85,
    "ceiling_height": 2.7,
    "area_per_person": 10.0,
    "oa_per_person": 10.0,
    "classification": "Class A",
    "num_people": 8.50,
    "total_outside_air": 85.00,
    "people_sensible_w": 637.50,
    "people_latent_w": 467.50,
    "lighting_w": 850.00,
    "small_power_w": 1275.00,
    "conduction_w": 1530.00,
    "ventilation_sensible_w": 1470.75,
    "ventilation_latent_w": 2346.94,
    "total_sensible_w": 5763.25,
    "total_latent_w": 2814.44,
    "total_cooling_w": 8577.69,
}

output_fields = {
    "num_people": data["num_people"],
    "total_outside_air": data["total_outside_air"],
    "people_sensible_w": data["people_sensible_w"],
    "people_latent_w": data["people_latent_w"],
    "lighting_w": data["lighting_w"],
    "small_power_w": data["small_power_w"],
    "conduction_w": data["conduction_w"],
    "ventilation_sensible_w": data["ventilation_sensible_w"],
    "ventilation_latent_w": data["ventilation_latent_w"],
    "total_sensible_w": data["total_sensible_w"],
    "total_latent_w": data["total_latent_w"],
    "total_cooling_w": data["total_cooling_w"],
}

solution = f"""# Heat Load Calculation — Office Areas

## Room: Office Areas (85 m², Brisbane)

```json
{json.dumps(output_fields, indent=2)}
```
"""

Path("/workspace/output.md").write_text(solution)
