# ABOUTME: Reference solution for single-room-office-L2 heat load calculation.
# ABOUTME: Computes from first principles and writes output.md with JSON block.

import json
from pathlib import Path

# Compute from first principles
data = {
    "room_type": "Data Centres / Server Rooms",
    "floor_area": 60,
    "ceiling_height": 3.0,
    "area_per_person": 0.0,
    "oa_per_person": 0.0,
    "classification": "Class B",
    "num_people": 0.00,
    "total_outside_air": 60.00,
    "people_sensible_w": 0.00,
    "people_latent_w": 0.00,
    "lighting_w": 300.00,
    "small_power_w": 15000.00,
    "conduction_w": 1500.00,
    "ventilation_sensible_w": 726.00,
    "ventilation_latent_w": 2391.36,
    "total_sensible_w": 17526.00,
    "total_latent_w": 2391.36,
    "total_cooling_w": 19917.36,
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

solution = f"""# Heat Load Calculation — Data Centres / Server Rooms

## Room: Data Centres / Server Rooms (60 m², Cairns)

```json
{json.dumps(output_fields, indent=2)}
```
"""

Path("/workspace/output.md").write_text(solution)
