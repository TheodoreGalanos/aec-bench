<!-- ABOUTME: Annotated reference for engine.py files used in aec-bench task generation templates. -->
<!-- ABOUTME: Shows the Terzaghi engine in full with pattern annotations, plus a SPT engine summary. -->

# Engine.py Reference — Annotated Examples

This document shows a working engine.py (Terzaghi bearing capacity) with inline pattern
annotations, followed by a brief summary of a second engine (SPT corrections) that
demonstrates lookup-table-heavy variants.

Use this as your primary reference when writing a new `engine.py` for a template.

---

## 1. Terzaghi Bearing Capacity Engine (Full, Annotated)

Source: `templates/builtin/ground/terzaghi_bearing_capacity/engine.py`

<!-- PATTERN: ABOUTME HEADER
Every code file in this repo MUST start with exactly two comment lines beginning with
"# ABOUTME: ". The first line states what the module IS. The second line states what it
DOES. This is a hard rule from CLAUDE.md — grep relies on it.
-->

```python
# ABOUTME: Terzaghi (1943) bearing capacity computation engine.
# ABOUTME: Calculates bearing capacity for strip, square, and circular footings.

import math
from typing import Literal
```

<!-- PATTERN: MODULE-LEVEL LOOKUP TABLES
Lookup tables are module-level constants (prefixed with underscore) for three reasons:
1. They are immutable reference data — not configuration, not state.
2. Placing them at module level makes them visible without reading any function body.
3. The leading underscore signals "private to this module" — compute() is the only
   public API.

Use list[tuple[...]] when the table has ordered rows you interpolate across.
Use dict[str, ...] when the table maps discrete enum values to factors (see SPT below).
-->

```python
# Terzaghi bearing capacity factor lookup table.
# Each row: (phi_deg, Nc, Nq, Ngamma)
_FACTOR_TABLE: list[tuple[float, float, float, float]] = [
    (0, 5.7, 1.0, 0.0),
    (5, 7.3, 1.6, 0.5),
    (10, 9.6, 2.7, 1.2),
    (15, 12.9, 4.4, 2.5),
    (20, 17.7, 7.4, 5.0),
    (25, 25.1, 12.7, 9.7),
    (30, 37.2, 22.5, 19.7),
    (34, 52.6, 36.5, 36.0),
    (35, 57.8, 41.4, 42.4),
    (40, 95.7, 81.3, 100.4),
    (45, 172.3, 173.3, 297.5),
    (48, 258.3, 287.9, 780.1),
    (50, 347.5, 415.1, 1153.2),
]

# Sorted phi values for binary search.
_PHI_VALUES = [row[0] for row in _FACTOR_TABLE]

# Unit weight of water in kN/m3.
_GAMMA_W = 9.81
```

<!-- PATTERN: ENUM PARAMS VIA DICT LOOKUP
When a parameter is an enum (footing_shape has values "strip", "square", "circular"),
the valid options and their associated factors are stored in a dict.
- The dict keys are the same strings used in params.toml's `values` field.
- _validate_inputs() checks `param not in _DICT` to reject invalid values.
- compute() does a single `_DICT[param]` lookup — no if/elif chains.
-->

```python
# Valid footing shapes and their (sc, sg_coeff) factors.
# sc multiplies Nc term; sg_coeff replaces the 0.5 in the Ngamma term.
_SHAPE_FACTORS: dict[str, tuple[float, float]] = {
    "strip": (1.0, 0.5),
    "square": (1.3, 0.4),
    "circular": (1.3, 0.3),
}
```

<!-- PATTERN: PRIVATE HELPER FUNCTIONS
Complex sub-calculations (interpolation, water table correction) get their own private
functions. Each one:
- Has a clear docstring stating what it returns.
- Takes only the values it needs (no bag-of-params passing).
- Returns a simple type (float, or tuple of floats).
-->

```python
def _interpolate_factor(phi_deg: float, column_index: int) -> float:
    """Linearly interpolate a bearing capacity factor from the lookup table.

    column_index: 1=Nc, 2=Nq, 3=Ngamma
    """
    # Clamp to [0, 50]
    phi_deg = max(0.0, min(50.0, phi_deg))

    # Find bracketing rows
    for i in range(len(_FACTOR_TABLE) - 1):
        phi_lo = _FACTOR_TABLE[i][0]
        phi_hi = _FACTOR_TABLE[i + 1][0]
        if phi_lo <= phi_deg <= phi_hi:
            val_lo = _FACTOR_TABLE[i][column_index]
            val_hi = _FACTOR_TABLE[i + 1][column_index]
            if phi_hi == phi_lo:
                return val_lo
            fraction = (phi_deg - phi_lo) / (phi_hi - phi_lo)
            return val_lo + fraction * (val_hi - val_lo)

    # Exact match at last row
    return _FACTOR_TABLE[-1][column_index]
```

<!-- PATTERN: SPECIAL CASES (phi=0)
When a formula has a mathematical singularity or special case (e.g. cot(0) is undefined),
handle it with an explicit `if` guard BEFORE the general formula. The comment should
explain WHY the special case exists (division by zero, textbook convention, etc.), not
just WHAT the code does.
-->

```python
def _bearing_capacity_factors(phi_deg: float) -> tuple[float, float, float]:
    """Return (Nc, Nq, Ngamma) for a given friction angle using table interpolation.

    Nc and Nq use the analytical Terzaghi formulae with special cases for phi=0.
    Ngamma uses linear interpolation from the lookup table (no closed-form exists).
    """
    phi_rad = math.radians(phi_deg)

    # Nq
    if phi_deg == 0.0:
        nq = 1.0
    else:
        exponent = 2.0 * (3.0 * math.pi / 4.0 - phi_rad / 2.0) * math.tan(phi_rad)
        denominator = 2.0 * math.cos(math.radians(45.0) + phi_rad / 2.0) ** 2
        nq = math.exp(exponent) / denominator

    # Nc
    if phi_deg == 0.0:
        nc = 5.7
    else:
        nc = (1.0 / math.tan(phi_rad)) * (nq - 1.0)

    # Ngamma from lookup table with linear interpolation
    ngamma = _interpolate_factor(phi_deg, 3)

    return nc, nq, ngamma
```

<!-- PATTERN: _validate_inputs()
Validation is a separate private function, NOT inlined in compute(). Rules:
- One `if` per parameter. Each raises ValueError with a descriptive message.
- The message names the parameter and states the constraint (e.g. "must be >= 0").
- Enum params check membership in their lookup dict and list valid options in the error.
- No return value — it either passes silently or raises.
- compute() calls this as its very first line.
-->

```python
def _validate_inputs(
    cohesion_kpa: float,
    friction_angle_deg: float,
    unit_weight_kn_m3: float,
    footing_width_m: float,
    embedment_depth_m: float,
    footing_shape: str,
    factor_of_safety: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if cohesion_kpa < 0:
        msg = "cohesion_kpa must be >= 0"
        raise ValueError(msg)
    if friction_angle_deg < 0:
        msg = "friction_angle_deg must be >= 0"
        raise ValueError(msg)
    if friction_angle_deg > 50:
        msg = "friction_angle_deg must be <= 50"
        raise ValueError(msg)
    if unit_weight_kn_m3 <= 0:
        msg = "unit_weight_kn_m3 must be > 0"
        raise ValueError(msg)
    if footing_width_m <= 0:
        msg = "footing_width_m must be > 0"
        raise ValueError(msg)
    if embedment_depth_m < 0:
        msg = "embedment_depth_m must be >= 0"
        raise ValueError(msg)
    if factor_of_safety <= 0:
        msg = "factor_of_safety must be > 0"
        raise ValueError(msg)
    if footing_shape not in _SHAPE_FACTORS:
        msg = f"footing_shape must be one of {list(_SHAPE_FACTORS.keys())}, got '{footing_shape}'"
        raise ValueError(msg)
```

<!-- PATTERN: WATER TABLE CORRECTION (domain-specific helper)
This is a good example of a helper that encapsulates a multi-branch domain formula.
It returns a tuple of corrected values used by the main equation. The three cases
(at/above, between, below) are handled with if/elif/else and commented with the
engineering rationale, not just code mechanics.
-->

```python
def _water_table_correction(
    gamma: float,
    embedment_depth_m: float,
    footing_width_m: float,
    water_table_depth_m: float,
) -> tuple[float, float]:
    """Calculate overburden pressure (q) and effective unit weight (gamma_eff).

    Returns (q_kpa, gamma_eff_kn_m3) corrected for water table position.
    Three cases based on water table depth relative to foundation level.
    """
    dw = water_table_depth_m
    df = embedment_depth_m
    b = footing_width_m

    if dw <= df:
        # Case 1: Water at or above foundation level
        # Overburden uses full weight above water table, buoyant weight below
        q = gamma * dw + (gamma - _GAMMA_W) * (df - dw)
        # Soil below foundation is fully submerged
        gamma_eff = gamma - _GAMMA_W
    elif dw < df + b:
        # Case 2: Water between foundation level and Df+B
        # Overburden is fully above water table
        q = gamma * df
        # Interpolated effective unit weight
        gamma_eff = (gamma - _GAMMA_W) + ((dw - df) / b) * _GAMMA_W
    else:
        # Case 3: Water below failure zone — no correction
        q = gamma * df
        gamma_eff = gamma

    return q, gamma_eff
```

<!-- PATTERN: compute() — THE PUBLIC API
This is the ONLY public function in the module. Structure is always:

    1. Validate inputs          → _validate_inputs(...)
    2. Compute intermediates    → factors, corrections, lookups
    3. Assemble final result    → the domain equation
    4. Round all outputs        → round(value, 2) on every value
    5. Return flat dict         → keys MUST match the output param names in params.toml

Key conventions:
- Signature uses `Literal[...]` for enum params (matches params.toml values list).
- Optional params with engineering defaults (water_table_depth_m=100.0 means "deep").
- Docstring lists the return dict keys explicitly.
- round(value, 2) on ALL numeric outputs — the generation framework expects this
  so that generated instructions show clean numbers, not floating-point artifacts.
- The return dict is FLAT (no nesting). Each key corresponds to an [outputs.<key>]
  section in params.toml.
-->

```python
def compute(
    cohesion_kpa: float,
    friction_angle_deg: float,
    unit_weight_kn_m3: float,
    footing_width_m: float,
    embedment_depth_m: float,
    footing_shape: Literal["strip", "square", "circular"],
    water_table_depth_m: float = 100.0,
    factor_of_safety: float = 3.0,
) -> dict[str, float]:
    """Compute ultimate and allowable bearing capacity using Terzaghi's 1943 equation.

    Returns a dict with keys: nc, nq, ngamma, ultimate_bearing_capacity_kpa,
    allowable_bearing_capacity_kpa.
    """
    _validate_inputs(
        cohesion_kpa,
        friction_angle_deg,
        unit_weight_kn_m3,
        footing_width_m,
        embedment_depth_m,
        footing_shape,
        factor_of_safety,
    )

    nc, nq, ngamma = _bearing_capacity_factors(friction_angle_deg)
    sc, sg = _SHAPE_FACTORS[footing_shape]

    q, gamma_eff = _water_table_correction(
        unit_weight_kn_m3,
        embedment_depth_m,
        footing_width_m,
        water_table_depth_m,
    )

    # Terzaghi bearing capacity equation
    # qu = c' * Nc * sc + q * Nq + gamma_eff * B * sg * Ngamma
    qu = cohesion_kpa * nc * sc + q * nq + gamma_eff * footing_width_m * sg * ngamma
    qa = qu / factor_of_safety

    return {
        "nc": round(nc, 2),
        "nq": round(nq, 2),
        "ngamma": round(ngamma, 2),
        "ultimate_bearing_capacity_kpa": round(qu, 2),
        "allowable_bearing_capacity_kpa": round(qa, 2),
    }
```

---

## 2. SPT Corrections Engine (Summary)

Source: `templates/builtin/ground/spt_corrections/engine.py`

This engine demonstrates a **lookup-table-heavy** variant where most of the computation
is just reading factors from tables and multiplying them together.

### Key differences from Terzaghi

<!-- PATTERN: MULTIPLE SMALL DICTS VS ONE BIG TABLE
When every parameter maps independently to a correction factor, use one dict per
parameter instead of a single combined table. This makes it trivial to add new enum
values — just add a row to the right dict.
-->

```python
# One dict per correction factor — each maps an enum value to a float.
_CE_TABLE: dict[str, float] = {"auto": 1.33, "safety": 0.96, "donut": 0.79}
_CB_TABLE: dict[str, float] = {"65": 1.00, "115": 1.00, "150": 1.05, "200": 1.15}
_CS_TABLE: dict[str, float] = {"with_liner": 1.00, "without_liner": 1.20}
```

<!-- PATTERN: STRING KEYS FOR ENUM PARAMS
borehole_diameter_mm uses string keys ("65", "115", ...) even though the values are
numeric. This is because the generation sampler always produces string values for enum
params defined in params.toml. The compute() signature types this as `str`, not `int`.
Match whatever type the sampler emits.
-->

<!-- PATTERN: STEPPED-INTERVAL LOOKUP (rod length correction)
When a correction factor varies by continuous ranges rather than discrete values,
use a boundary list with a loop. Each tuple is (upper_boundary, factor). The loop
returns the factor for the first interval the value falls into. A module-level
default covers the final open interval.
-->

```python
# Half-open intervals: [3, 4) = 0.75, [4, 6) = 0.85, [6, 10) = 0.95, >= 10 = 1.00.
_CR_BOUNDARIES: list[tuple[float, float]] = [
    (4.0, 0.75),
    (6.0, 0.85),
    (10.0, 0.95),
]
_CR_DEFAULT = 1.00

def _get_cr(rod_length_m: float) -> float:
    """Look up rod length correction factor using half-open intervals."""
    for boundary, factor in _CR_BOUNDARIES:
        if rod_length_m < boundary:
            return factor
    return _CR_DEFAULT
```

### SPT compute() — same structure, simpler body

The compute function follows the identical pattern: validate, look up factors,
multiply, round, return flat dict.

```python
def compute(
    raw_n_value: int,
    effective_overburden_kpa: float,
    hammer_type: str,
    borehole_diameter_mm: str,
    sampler_type: str,
    rod_length_m: float,
) -> dict[str, float]:
    _validate_inputs(
        raw_n_value, effective_overburden_kpa, hammer_type,
        borehole_diameter_mm, sampler_type, rod_length_m,
    )

    ce = _CE_TABLE[hammer_type]
    cb = _CB_TABLE[borehole_diameter_mm]
    cs = _CS_TABLE[sampler_type]
    cr = _get_cr(rod_length_m)

    n60 = raw_n_value * ce * cb * cs * cr
    cn = min(math.sqrt(_PA / effective_overburden_kpa), _CN_MAX)
    n1_60 = cn * n60

    return {
        "ce": round(ce, 2),
        "cb": round(cb, 2),
        "cs": round(cs, 2),
        "cr": round(cr, 2),
        "n60": round(n60, 2),
        "cn": round(cn, 2),
        "n1_60": round(n1_60, 2),
    }
```

---

## 3. Quick Checklist for New Engines

When writing a new `engine.py`, verify:

- [ ] Two-line `# ABOUTME:` header at the top of the file
- [ ] Lookup tables are module-level `_CONSTANTS` (underscore prefix, type-annotated)
- [ ] `_validate_inputs()` is a separate function, raises `ValueError` with param name in message
- [ ] Enum params validated with `if param not in _TABLE`; error lists valid options
- [ ] `compute()` is the only public function
- [ ] `compute()` signature uses `Literal[...]` for enum params where applicable
- [ ] `compute()` structure: validate -> compute intermediates -> assemble result -> round -> return
- [ ] All returned values wrapped in `round(value, 2)`
- [ ] Return dict is flat; keys match `[outputs.<key>]` names in `params.toml`
- [ ] Special cases (division by zero, boundary values) handled with explicit guards
- [ ] Comments explain engineering rationale, not code mechanics
