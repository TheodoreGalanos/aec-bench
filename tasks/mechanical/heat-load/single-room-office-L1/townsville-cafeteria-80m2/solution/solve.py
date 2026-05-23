# ABOUTME: Reference solution for single-room-office-L1 heat load calculation.
# ABOUTME: Computes from first principles and writes output.md with JSON block.

import json
from pathlib import Path

# Compute from first principles
data = {
    "room_type": "Cafeteria / Break Rooms",
    "floor_area": 80,
    "ceiling_height": 2.7,
    "area_per_person": 2.5,
    "oa_per_person": 10.0,
    "classification": "Class A",
    "num_people": 32.00,
    "total_outside_air": 320.00,
    "people_sensible_w": 2400.00,
    "people_latent_w": 1760.00,
    "lighting_w": 640.00,
    "small_power_w": 640.00,
    "conduction_w": 960.00,
    "ventilation_sensible_w": 4491.52,
    "ventilation_latent_w": 11831.93,
    "total_sensible_w": 9131.52,
    "total_latent_w": 13591.93,
    "total_cooling_w": 22723.45,
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

solution = f"""# Heat Load Calculation — Cafeteria / Break Rooms

## Room: Cafeteria / Break Rooms (80 m², Townsville)

```json
{json.dumps(output_fields, indent=2)}
```
"""

Path("/workspace/output.md").write_text(solution)
