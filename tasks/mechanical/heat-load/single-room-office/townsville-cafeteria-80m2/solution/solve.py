# ABOUTME: Reference solution for single-room-office heat load calculation.
# ABOUTME: Uses the heat_load_calc.py tool and writes output.md with JSON block.

import json
import subprocess
from pathlib import Path

result = subprocess.run(
    [
        "python3", "/workspace/heat_load_calc.py",
        "--room-type", "Cafeteria / Break Rooms",
        "--floor-area", "80",
        "--ceiling-height", "2.7",
        "--outdoor-db", "35.6",
        "--outdoor-wb", "26.2",
        "--indoor-db", "24.0",
        "--outdoor-enthalpy", "79.0",
        "--indoor-enthalpy", "48.2",
        "--lighting-density", "8",
        "--small-power-density", "8",
        "--conduction-factor", "12",
    ],
    capture_output=True,
    text=True,
    check=True,
)

data = json.loads(result.stdout)

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
