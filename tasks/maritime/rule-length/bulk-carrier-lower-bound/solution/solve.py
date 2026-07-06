# ABOUTME: Reference solution for bulk-carrier-lower-bound Rule length calculation.
# ABOUTME: Computes from first principles and writes output.md with JSON block.

import json
from pathlib import Path

# Compute from first principles
data = {
    "vessel_type": "Panamax bulk carrier",
    "extreme_length_on_waterline_at_TSC_m": 229.0,
    "has_rudder_stock": True,
    "stem_to_rudder_stock_distance_m": 215.0,
    "lower_bound_m": 219.84,
    "upper_bound_m": 222.13,
    "rule_length_L_m": 219.84,
}

output_fields = {
    "rule_length_L_m": data["rule_length_L_m"],
}

solution = f"""# Rule Length Calculation — Panamax Bulk Carrier

## Vessel: Panamax bulk carrier (extreme length 229.0 m on waterline at T_SC)

Per IACS CSR-H (01 JUL 2025) Pt 1 Ch 1 Sec 4 §3.1.1, the Rule length L is clamped
to the range [0.96 x extreme length, 0.97 x extreme length] when a rudder stock
is fitted.

- Lower bound = 0.96 x 229.0 = 219.84 m
- Upper bound = 0.97 x 229.0 = 222.13 m
- Measured stem-to-rudder-stock distance = 215.0 m (below the lower bound)

Since the measured distance (215.0 m) is less than the lower bound (219.84 m),
the Rule length is clamped up to the lower bound: L = 219.84 m.

```json
{json.dumps(output_fields, indent=2)}
```
"""

Path("/workspace/output.md").write_text(solution)
