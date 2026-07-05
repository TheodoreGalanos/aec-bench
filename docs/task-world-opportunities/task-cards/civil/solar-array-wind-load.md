# ABOUTME: First-pass task-world opportunity card for solar-array-wind-load.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / wind-load-derivation / solar-array-wind-load

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/solar_array_wind_load`
- Discipline: `civil`
- Category: `wind-load-derivation`
- Tool mode: `with-tool`
- Standards: AS/NZS 1170.2; SEAOC PV2-2017; ASCE 7-22
- Tags: wind; solar; photovoltaic; uplift; drag; renewable-energy

## Current Task Shape

Calculates wind loads on ground-mounted photovoltaic arrays by combining AS/NZS 1170.2 dynamic pressure with SEAOC PV2-2017 net pressure coefficients. Interpolates GCrn values for tilt angle and row position to determine uplift suction, downward pressure, per-module uplift force, and horizontal drag force per metre of array width. Applicable to fixed-tilt utility and commercial solar installations in Australian wind regions.

## Existing Deterministic Contract

- Parameters: `8`
- Outputs: `5`
- Archetypes: `5`
- Visibility mix: all_given; partial
- Hidden parameters: `row_position`, `tilt_angle_deg`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `design_wind_speed_m_per_s` | Site design wind speed V_des,theta (after terrain, topographic, shielding, and direction multipliers) | float / m/s | range=20..70 |
| `tilt_angle_deg` | Array tilt angle from horizontal | float / degrees | range=5..45; derivable_from=archetype |
| `array_height_m` | Hub height of array above ground level | float / m | range=0.3..3.0 |
| `module_width_m` | Width of a single PV module (along the slope) | float / m | range=0.8..1.4 |
| `module_length_m` | Length of a single PV module (along the row) | float / m | range=1.5..2.4 |
| `num_modules_wide` | Number of modules arranged in the slope direction per row | int / - | range=1..4 |
| `row_position` | Row position in the array field affecting wind exposure | enum | values=exposed, interior; derivable_from=archetype |
| `air_density_kg_per_m3` | Air density rho (standard atmosphere default 1.2) | float / kg/m3 | range=1.0..1.4 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `dynamic_pressure_kpa` | Base velocity pressure q (kPa) |  | tolerance=0.03 |
| `uplift_pressure_kpa` | Net uplift (suction) pressure on the array surface (kPa) |  | tolerance=0.03 |
| `downforce_pressure_kpa` | Net downward pressure on the array surface (kPa) |  | tolerance=0.03 |
| `uplift_force_per_module_kn` | Uplift force acting on a single PV module (kN) |  | tolerance=0.03 |
| `drag_force_per_m_kn` | Horizontal drag force per metre of array row length (kN/m) |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `utility_scale_flat` | Utility-scale solar farm on flat open terrain with low tilt fixed-tilt racking | western-nsw-solar-farm; north-queensland-solar-park; mildura-solar-precinct |
| `utility_scale_steep` | Utility-scale solar farm with steeper tilt for higher-latitude sites | gippsland-solar-farm; tasmanian-highlands-solar; southern-sa-solar-plant |
| `commercial_rooftop_ground` | Commercial ground-mounted array behind a warehouse or industrial building | sydney-industrial-park; melbourne-logistics-precinct; brisbane-trade-coast |
| `remote_community` | Remote community or mine-site solar installation on exposed terrain | alice-springs-solar; mount-isa-mining-camp; pilbara-remote-solar |
| `coastal_exposed` | Coastal solar farm subject to high cyclonic wind speeds | townsville-coastal-solar; darwin-industrial-solar; geraldton-wind-farm-solar |

### Difficulty Notes

```text
easy: all_given | Low wind speed, exposed row, all parameters given — straightforward pressure and force calculation
medium: all_given | Higher wind speeds and steeper tilts with all parameters given
hard: partial | hidden=tilt_angle_deg, row_position | Tilt angle and row position hidden — agent must infer from site description and array configuration
```

## Multimodal Expansion

Candidate modality families: `drawing-geometry`, `tabular-source`, `document-evidence`.

Use building elevations, terrain/zone diagrams, load schedules, and standards extracts.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Wind-speed and pressure derivations can feed structural member, bracket, cladding, and foundation checks.

First-pass composition tags: `shared-context`, `pipeline`, `evidence-assembly`.

## Meta-Harness Handles

Candidate operation handles: `parameters`, `outputs`, `difficulty`, `archetype`, `evidence_profile`, `hidden_parameter_policy`, `source_geometry`, `source_table`.

Practical operations to consider:

- `projection`: isolate the arithmetic-only world, source-interpretation world, or evidence-review world.
- `difference`: remove visible parameters, calculator access, source labels, or intermediate hints.
- `subset`: restrict to one archetype, standard, modality, or difficulty tier.
- `product`: compose with a downstream or upstream task that consumes/produces compatible engineering quantities.

## Repair/Event Candidates

- Trigger `evidence_profile` repair if the model reaches the right number without citing or preserving the source artifact.
- Trigger `verifier` repair if final-output tolerances pass while intermediate units, assumptions, or handoff values are inconsistent.
- Trigger `world_schema` repair if a promising composition lacks explicit handoff fields or operation handles.
