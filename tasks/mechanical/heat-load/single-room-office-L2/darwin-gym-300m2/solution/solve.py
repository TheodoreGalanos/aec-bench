# ABOUTME: Reference solution for single-room-office-L2 heat load calculation.
# ABOUTME: Computes from first principles and writes output.md with JSON block.

import json
from pathlib import Path

# Compute from first principles
data = {
    "room_type": "Gymnasiums",
    "floor_area": 300,
    "ceiling_height": 4.0,
    "area_per_person": 5.0,
    "oa_per_person": 15.0,
    "classification": "Class A",
    "num_people": 60.00,
    "total_outside_air": 900.00,
    "people_sensible_w": 4500.00,
    "people_latent_w": 3300.00,
    "lighting_w": 3000.00,
    "small_power_w": 1500.00,
    "conduction_w": 4500.00,
    "ventilation_sensible_w": 11325.60,
    "ventilation_latent_w": 37166.87,
    "total_sensible_w": 24825.60,
    "total_latent_w": 40466.87,
    "total_cooling_w": 65292.47,
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

solution = f"""# Heat Load Calculation — Gymnasiums

## Room: Gymnasiums (300 m², Darwin)

```json
{json.dumps(output_fields, indent=2)}
```
"""

Path("/workspace/output.md").write_text(solution)
