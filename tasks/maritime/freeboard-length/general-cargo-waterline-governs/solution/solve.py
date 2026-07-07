# ABOUTME: Reference solution for general-cargo-waterline-governs Freeboard length calculation.
# ABOUTME: Computes from first principles and writes output.md with JSON block.

import json
from pathlib import Path

# Compute from first principles
data = {
    "vessel_type": "General cargo ship",
    "total_length_on_85pct_depth_waterline_m": 180.0,
    "has_rudder_stock": True,
    "stem_to_rudder_stock_axis_distance_m": 170.0,
    "waterline_fraction_m": 172.8,
    "freeboard_length_LLL_m": 172.8,
}

output_fields = {
    "freeboard_length_LLL_m": data["freeboard_length_LLL_m"],
}

solution = f"""# Freeboard Length Calculation — General Cargo Ship

## Vessel: General cargo ship (total length 180.0 m on the 85%-depth waterline)

Per IACS CSR-H (01 JUL 2025) Pt 1 Ch 1 Sec 4 §3.1.2, the Freeboard length L_LL is the
greater of 96% of the total length on the 85%-depth waterline and the measured length
from the fore side of the stem to the axis of the rudder stock on that waterline.

- Waterline fraction = 0.96 x 180.0 = 172.8 m
- Measured stem-to-rudder-stock-axis distance = 170.0 m

Since the waterline fraction (172.8 m) is greater than the measured distance (170.0 m),
the waterline fraction governs: L_LL = 172.8 m.

```json
{json.dumps(output_fields, indent=2)}
```
"""

Path("/workspace/output.md").write_text(solution)
