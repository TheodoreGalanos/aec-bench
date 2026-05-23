# ABOUTME: Reference solution for single-room-office heat load calculation.
# ABOUTME: Uses the heat_load_calc.py tool and writes output.md with JSON block.

import json
import subprocess
from pathlib import Path

result = subprocess.run(
    [
        "python3", "/workspace/heat_load_calc.py",
        "--room-type", "Retail Shops",
        "--floor-area", "100",
        "--ceiling-height", "3.5",
        "--outdoor-db", "31.0",
        "--outdoor-wb", "18.5",
        "--indoor-db", "24.0",
        "--outdoor-enthalpy", "50.8",
        "--indoor-enthalpy", "48.2",
        "--lighting-density", "18",
        "--small-power-density", "10",
        "--conduction-factor", "20",
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

solution = f"""# Heat Load Calculation — Retail Shops

## Room: Retail Shops (100 m², Hobart)

```json
{json.dumps(output_fields, indent=2)}
```
"""

Path("/workspace/output.md").write_text(solution)
