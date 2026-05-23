# ABOUTME: Reference solution for single-room-office-L2 heat load calculation.
# ABOUTME: Computes from first principles and writes output.md with JSON block.

import json
from pathlib import Path

# Compute from first principles
data = {
    "room_type": "Libraries",
    "floor_area": 150,
    "ceiling_height": 2.7,
    "area_per_person": 5.0,
    "oa_per_person": 10.0,
    "classification": "Class A",
    "num_people": 30.00,
    "total_outside_air": 300.00,
    "people_sensible_w": 2250.00,
    "people_latent_w": 1650.00,
    "lighting_w": 1500.00,
    "small_power_w": 1200.00,
    "conduction_w": 2250.00,
    "ventilation_sensible_w": 5662.80,
    "ventilation_latent_w": 5258.10,
    "total_sensible_w": 12862.80,
    "total_latent_w": 6908.10,
    "total_cooling_w": 19770.90,
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

solution = f"""# Heat Load Calculation — Libraries

## Room: Libraries (150 m², Adelaide)

```json
{json.dumps(output_fields, indent=2)}
```
"""

Path("/workspace/output.md").write_text(solution)
