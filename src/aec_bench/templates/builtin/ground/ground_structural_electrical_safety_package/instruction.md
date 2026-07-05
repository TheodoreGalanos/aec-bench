You are a geotechnical/electrical earthing engineer checking a task-owned synthetic SSC-07 package for one ground investigation handoff, shallow foundation bearing check, and separate soil-resistivity earthing check.

Use only the task-owned synthetic source pack values shown below for numeric grading. External ground-investigation, geotechnical analysis, and earthing-design workflows shape the context only; they are not extra data sources for this instance.

## Scene

- Ground package: `GND-SSC07-001`
- Borehole log: `BH-07-03`
- CPT record: `CPT-07-02`
- SPT record: `SPT-07-03-06M`
- Groundwater record: `GW-07-WET-001`
- Soil parameter summary: `SOIL-07-PARAM-01`
- Ground interpretation memo: `GIM-07-001`
- Resistivity record: `RES-07-ERT-01`
- Foundation layout: `FDN-07-MAT-01`
- Earthing layout: `GRID-07-EARTH-01`
- Fault case: `FAULT-07-001`
- Safety memo: `MEMO-07-SAFETY-01`

The mechanical ground model and the electrical resistivity model are related source-pack artifacts, but they are separate interpretations. Do not reuse the strength model as the resistivity model.

## SPT And CPT Basis

| Item | Value |
|------|-------|
| Raw SPT N value | {{ raw_n_value }} |
| Effective overburden at SPT depth | {{ effective_overburden_kpa }} kPa |
| Hammer type | {{ hammer_type }} |
| Borehole diameter class | {{ borehole_diameter_mm }} mm |
| Sampler type | {{ sampler_type }} |
| Rod length | {{ rod_length_m }} m |
| Minimum design N1,60 | {{ minimum_design_n1_60 }} |
| CPT cone resistance qc | {{ qc_mpa }} MPa |
| CPT sleeve friction fs | {{ fs_kpa }} kPa |
| CPT pore pressure u2 | {{ u2_kpa }} kPa |
| CPT interpretation depth | {{ cpt_depth_m }} m |
| Total soil unit weight | {{ total_unit_weight_kn_m3 }} kN/m3 |
| Wet-season water table depth | {{ water_table_depth_m }} m |
| CPT net area ratio | {{ net_area_ratio }} |
| Interpreted design friction angle | {{ interpreted_design_phi_deg }} degrees |

SPT checks:

- Use energy correction `CE = 1.33` for `auto`, borehole correction `CB = 1.00` for `115`, sampler correction `CS = 1.00` for `with_liner`, and rod length correction `CR = 0.95` for an 8 m rod.
- `N60 = raw_n_value x CE x CB x CS x CR`.
- `CN = min(sqrt(100 / effective_overburden_kpa), 2.0)`.
- `N1,60 = N60 x CN`.
- `spt_n1_60_margin = N1,60 - minimum_design_n1_60`.

CPT checks:

- Corrected cone resistance `qt = qc_mpa + (u2_kpa / 1000) x (1 - net_area_ratio)`.
- Total vertical stress `sigma_v0 = total_unit_weight_kn_m3 x cpt_depth_m`.
- Pore pressure above the CPT depth uses `9.81 x max(cpt_depth_m - water_table_depth_m, 0)`.
- Effective vertical stress `sigma_prime_v0 = sigma_v0 - pore_pressure`.
- Normalized cone resistance `Qt = (qt_kpa - sigma_v0) / sigma_prime_v0`.
- Normalized friction ratio `Fr = fs_kpa / (qt_kpa - sigma_v0) x 100`.
- Soil behavior type index `Ic = sqrt((3.47 - log10(Qt))^2 + (log10(Fr) + 1.22)^2)`.
- If `Ic <= 2.6`, `cpt_phi_deg = 17.6 + 11 x log10(Qt)`; otherwise use `0.0`.
- `governing_phi_deg` is the smaller of `interpreted_design_phi_deg` and `cpt_phi_deg`.

## Bearing And Earthing Basis

| Item | Value |
|------|-------|
| Effective cohesion | {{ cohesion_kpa }} kPa |
| Footing width | {{ footing_width_m }} m |
| Embedment depth | {{ embedment_depth_m }} m |
| Footing shape | {{ footing_shape }} |
| Bearing factor of safety | {{ factor_of_safety }} |
| Applied service bearing pressure | {{ applied_bearing_pressure_kpa }} kPa |
| Apparent soil resistivity | {{ soil_resistivity_ohm_m }} ohm-m |
| Grid length | {{ grid_length_m }} m |
| Grid width | {{ grid_width_m }} m |
| Total buried conductor length | {{ total_conductor_length_m }} m |
| Burial depth | {{ burial_depth_m }} m |
| Grid current | {{ grid_current_ka }} kA |
| GPR screening limit | {{ gpr_limit_v }} V |

Bearing checks:

- Use the template's source-bound Terzaghi bearing factors for `governing_phi_deg = 32.0`: `Nc = 44.0357`, `Nq = 28.5166`, and `Ngamma = 27.85`.
- The source-bound convention is `Nq = exp(2 x (3*pi/4 - phi/2) x tan(phi)) / (2 x cos(45deg + phi/2)^2)`, `Nc = (Nq - 1) / tan(phi)`, and linear interpolation of `Ngamma` between 30 degrees (`19.7`) and 34 degrees (`36.0`).
- For a square footing use `sc = 1.3` and `sg = 0.4`.
- Apply the wet-season water-table correction exactly as follows: because `water_table_depth_m = 2.1` is between `embedment_depth_m = 1.2` and `embedment_depth_m + footing_width_m = 3.6`, use `q = total_unit_weight_kn_m3 x embedment_depth_m = 22.2` and `gamma_eff = (total_unit_weight_kn_m3 - 9.81) + ((water_table_depth_m - embedment_depth_m) / footing_width_m) x 9.81 = 12.36875`.
- Do not replace this interpolated `gamma_eff = 12.36875` with the fully submerged unit weight `8.69`.
- `ultimate_bearing_capacity = cohesion_kpa x Nc x sc + q x Nq + gamma_eff x footing_width_m x sg x Ngamma`.
- `allowable_bearing_capacity_kpa = ultimate_bearing_capacity / factor_of_safety`.
- `bearing_utilization = applied_bearing_pressure_kpa / allowable_bearing_capacity_kpa`.
- `bearing_margin_kpa = allowable_bearing_capacity_kpa - applied_bearing_pressure_kpa`.

Earthing checks:

- Grid area equals `grid_length_m x grid_width_m`.
- `grid_resistance_ohm = soil_resistivity_ohm_m x (1 / total_conductor_length_m + 1 / sqrt(20 x grid_area) x (1 + 1 / (1 + burial_depth_m x sqrt(20 / grid_area))))`.
- `ground_potential_rise_v = grid_current_ka x 1000 x grid_resistance_ohm`.
- `gpr_margin_v = gpr_limit_v - ground_potential_rise_v`.
- `overall_pass_score` is `1.0` only when the SPT N1,60 margin, bearing margin, and GPR margin are all non-negative; otherwise it is `0.0`.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Explain the calculations briefly, preserve the object IDs above, and state whether the baseline source pack passes the current synthetic checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "spt_n60": <numeric_value>,
  "spt_n1_60": <numeric_value>,
  "spt_n1_60_margin": <numeric_value>,
  "cpt_qt_mpa": <numeric_value>,
  "cpt_ic": <numeric_value>,
  "cpt_phi_deg": <numeric_value>,
  "governing_phi_deg": <numeric_value>,
  "allowable_bearing_capacity_kpa": <numeric_value>,
  "bearing_utilization": <numeric_value>,
  "bearing_margin_kpa": <numeric_value>,
  "grid_resistance_ohm": <numeric_value>,
  "ground_potential_rise_v": <numeric_value>,
  "gpr_margin_v": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
