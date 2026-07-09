# ABOUTME: Reference solution for capesize-bulk-carrier Block coefficient calculation.
# ABOUTME: Computes from first principles and writes output.md with JSON block.

import json
from pathlib import Path

# Compute from first principles
data = {
    "vessel_type": "Capesize bulk carrier",
    "moulded_displacement_t": 180000.0,
    "rule_length_L_m": 280.0,
    "moulded_breadth_B_m": 45.0,
    "scantling_draught_TSC_m": 18.0,
    "seawater_density_t_m3": 1.025,
    "block_coefficient_CB": 0.77,
}

output_fields = {
    "block_coefficient_CB": data["block_coefficient_CB"],
}

solution = f"""# Block Coefficient Calculation — Capesize Bulk Carrier

## Vessel: Capesize bulk carrier

Per IACS CSR-H (01 JUL 2025) Pt 1 Ch 1 Sec 4 §3.1.8, the block coefficient at
the scantling draught is:

C_B = Delta / (1.025 x L x B x T_SC)

- Delta (moulded displacement) = 180,000 t
- L (Rule length) = 280.0 m
- B (moulded breadth) = 45.0 m
- T_SC (scantling draught) = 18.0 m

C_B = 180000 / (1.025 x 280.0 x 45.0 x 18.0)
    = 180000 / 232470.0
    = 0.7744 -> 0.77

```json
{json.dumps(output_fields, indent=2)}
```
"""

Path("/workspace/output.md").write_text(solution)
