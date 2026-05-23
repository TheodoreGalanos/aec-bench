# ABOUTME: Reference solution for multi-room-mixed multi-room heat load calculation.
# ABOUTME: Uses the heat_load_calc.py tool for each room and writes output.md.

import json
import subprocess
from pathlib import Path

ROOMS = [
    {
        "room_no": 1,
        "name": "Lobby",
        "room_type": "Reception / Lobby",
        "floor_area": 50,
        "ceiling_height": 3.0,
        "lighting_density": 12,
        "small_power_density": 5,
        "conduction_factor": 15,
    },
    {
        "room_no": 2,
        "name": "Office A",
        "room_type": "Office Areas",
        "floor_area": 100,
        "ceiling_height": 2.7,
        "lighting_density": 10,
        "small_power_density": 15,
        "conduction_factor": 18,
    },
    {
        "room_no": 3,
        "name": "Office B",
        "room_type": "Office Areas",
        "floor_area": 80,
        "ceiling_height": 2.7,
        "lighting_density": 10,
        "small_power_density": 12,
        "conduction_factor": 16,
    },
    {
        "room_no": 4,
        "name": "Conference",
        "room_type": "Conference Rooms",
        "floor_area": 40,
        "ceiling_height": 2.7,
        "lighting_density": 10,
        "small_power_density": 10,
        "conduction_factor": 15,
    },
    {
        "room_no": 5,
        "name": "Kitchen",
        "room_type": "Kitchens (Commercial)",
        "floor_area": 30,
        "ceiling_height": 2.7,
        "lighting_density": 8,
        "small_power_density": 20,
        "conduction_factor": 18,
    },
    {
        "room_no": 6,
        "name": "Server Room",
        "room_type": "Data Centres / Server Rooms",
        "floor_area": 15,
        "ceiling_height": 3.0,
        "lighting_density": 5,
        "small_power_density": 300,
        "conduction_factor": 25,
    },
]

rooms_output = []
for room in ROOMS:
    result = subprocess.run(
        [
            "python3", "/workspace/heat_load_calc.py",
            "--room-type", room["room_type"],
            "--floor-area", str(room["floor_area"]),
            "--ceiling-height", str(room["ceiling_height"]),
            "--outdoor-db", "36.4",
            "--outdoor-wb", "20.8",
            "--indoor-db", "24.0",
            "--outdoor-enthalpy", "58.6",
            "--indoor-enthalpy", "48.2",
            "--lighting-density", str(room["lighting_density"]),
            "--small-power-density", str(room["small_power_density"]),
            "--conduction-factor", str(room["conduction_factor"]),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    rooms_output.append({
        "room_no": room["room_no"],
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
    })

floor_totals = {
    "total_sensible_w": sum(r["total_sensible_w"] for r in rooms_output),
    "total_latent_w": sum(r["total_latent_w"] for r in rooms_output),
    "total_cooling_w": sum(r["total_cooling_w"] for r in rooms_output),
}

output = {"rooms": rooms_output, "floor_totals": floor_totals}

solution = f"""# Heat Load Calculation — Multi-Room (Melbourne)

```json
{json.dumps(output, indent=2)}
```
"""

Path("/workspace/output.md").write_text(solution)
