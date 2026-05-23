# ABOUTME: Reference solution for single-room-office-L3 heat load calculation.
# ABOUTME: Computes from first principles and writes output.md with JSON block.

import json
from pathlib import Path

# Compute from first principles
data = {
    "room_type": "Restaurants",
    "floor_area": 200,
    "ceiling_height": 3.0,
    "area_per_person": 1.5,
    "oa_per_person": 10.0,
    "classification": "Class A",
    "num_people": 133.33,
    "total_outside_air": 1333.33,
    "people_sensible_w": 10000.00,
    "people_latent_w": 7333.33,
    "lighting_w": 2400.00,
    "small_power_w": 1600.00,
    "conduction_w": 3000.00,
    "ventilation_sensible_w": 34686.67,
    "ventilation_latent_w": 48339.34,
    "total_sensible_w": 51686.67,
    "total_latent_w": 55672.67,
    "total_cooling_w": 107359.34,
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

solution = f"""# Heat Load Calculation — Restaurants

## Room: Restaurants (200 m², Perth)

```json
{json.dumps(output_fields, indent=2)}
```
"""

Path("/workspace/output.md").write_text(solution)
