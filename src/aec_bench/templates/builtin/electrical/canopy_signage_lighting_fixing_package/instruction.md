You are an electrical and facade interface engineer checking a task-owned synthetic SSC-09 canopy, signage, lighting, and envelope fixing package.

Use only the task-owned synthetic source pack values shown below for numeric grading. Canopy/signage wind, lighting load, anchor/fixing, and DC feeder workflows shape the context only; this instance does not run lighting software, parse real drawings, validate a product certificate, or prove authority approval.

## Scene

- Product: `SSC-09-LH-04`
- Canopy elevation: `CANOPY-09-ELEV-04`
- Sign geometry: `SIGN-09-GEOM-04`
- Lighting/device schedule: `LIGHT-09-LOAD-04`
- Canopy anchor table: `ANCH-09-CANOPY-04`
- Lighting feeder: `FEEDER-09-LIGHT-04`
- Integrated facade memo: `MEMO-09-FACADE-04`

## Source Values

| Item | Value |
| --- | --- |
| Sign area | {{ sign_area_m2 }} m2 |
| Canopy area | {{ canopy_area_m2 }} m2 |
| Wind pressure | {{ wind_pressure_kpa }} kPa |
| Sign dead load | {{ sign_dead_load_kpa }} kPa |
| Canopy dead load | {{ canopy_dead_load_kpa }} kPa |
| Fixing capacity | {{ fixing_capacity_kn }} kN |
| Anchor count | {{ anchor_count }} |
| Anchor capacity | {{ anchor_capacity_kn }} kN |
| Lighting load | {{ lighting_load_w }} W |
| Driver load | {{ driver_load_w }} W |
| Sign control load | {{ sign_control_load_w }} W |
| Feeder voltage | {{ feeder_voltage_v }} V |
| Cable length | {{ cable_length_m }} m |
| Conductor resistance | {{ conductor_resistance_ohm_km }} ohm/km |
| Maximum voltage drop | {{ max_voltage_drop_percent }} % |

## Checks

- Wind load equals sign plus canopy area times wind pressure.
- Dead load equals sign area times sign dead load plus canopy area times canopy dead load.
- Combined fixing demand equals the vector combination of wind load and dead load.
- Lighting connected load equals lighting plus driver plus sign-control loads.
- DC voltage drop uses a two-wire circuit: `2 x current x length x resistance / 1000 / voltage x 100`.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the object IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, lighting software validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "wind_load_kn": <numeric_value>,
  "dead_load_kn": <numeric_value>,
  "combined_fixing_demand_kn": <numeric_value>,
  "fixing_capacity_margin_kn": <numeric_value>,
  "anchor_group_margin_kn": <numeric_value>,
  "lighting_connected_load_w": <numeric_value>,
  "lighting_current_a": <numeric_value>,
  "voltage_drop_percent": <numeric_value>,
  "voltage_drop_margin_percent": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
