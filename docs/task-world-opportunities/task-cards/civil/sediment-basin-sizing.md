# ABOUTME: First-pass task-world opportunity card for sediment-basin-sizing.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / erosion-sediment / sediment-basin-sizing

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/sediment_basin_sizing`
- Discipline: `civil`
- Category: `erosion-sediment`
- Tool mode: `with-tool`
- Standards: Managing Urban Stormwater: Soils and Construction (Blue Book)
- Tags: civil; erosion; sediment; stormwater; basin; construction

## Current Task Shape

Sizes construction-phase sediment basins for erosion and sediment control per the Blue Book (Managing Urban Stormwater: Soils and Construction). Calculates settling zone volume (V_s = Cv*A), sediment storage volume (V_sed = R*A*D), and total basin volume for Type D (dry) or Type F (wet with permanent pool) configurations based on soil loss rates and climate region.

## Existing Deterministic Contract

- Parameters: `6`
- Outputs: `3`
- Archetypes: `5`
- Visibility mix: all_given; partial
- Hidden parameters: `soil_loss_rate_m3_ha_yr`, `volumetric_runoff_coeff_m3_ha`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `catchment_area_ha` | Contributing catchment area A | float / ha | range=0.1..50.0 |
| `volumetric_runoff_coeff_m3_ha` | Volumetric runoff coefficient Cv (varies by rainfall region) | float / m³/ha | range=150..400; derivable_from=archetype |
| `soil_loss_rate_m3_ha_yr` | Soil loss rate R | float / m³/ha/yr | range=1..50; derivable_from=archetype |
| `cleanout_interval_yr` | Sediment clean-out interval D | float / years | range=0.25..2.0 |
| `basin_type` | Basin type: D (dry) or F (wet with permanent pool) | enum | values=D, F |
| `permanent_pool_volume_m3` | Permanent pool volume for Type F basins | float / m³ | range=0..5000 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `settling_volume_m3` | Settling zone volume V_s (m³) |  | tolerance=0.03 |
| `sediment_storage_volume_m3` | Sediment storage volume V_sed (m³) |  | tolerance=0.03 |
| `total_basin_volume_m3` | Total basin volume V_total (m³) |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `dispersive_clay` | Dispersive clay soil construction site in a high-rainfall coastal region | sydney-western-suburbs; wollongong-escarpment; brisbane-southern-suburbs |
| `reactive_clay` | Reactive clay soil construction site in a moderate-rainfall inland region | melbourne-western-suburbs; geelong-growth-corridor; ballarat-residential |
| `sandy_coastal` | Sandy soil construction site in a coastal region with moderate rainfall | perth-northern-coastal; gold-coast-hinterland; sunshine-coast-subdivision |
| `rocky_terrain` | Rocky terrain construction site with shallow topsoil and steep grades | cairns-hillside; townsville-range; hobart-derwent-valley |
| `alluvial_floodplain` | Alluvial floodplain construction site with silty soils in a tropical region | darwin-palmerston; mackay-river-flats; bundaberg-burnett-river |

### Difficulty Notes

```text
easy: all_given | Type D basin with all parameters given — straightforward volume calculation
medium: all_given | Type F basin with permanent pool — agent must combine three volume components
hard: partial | hidden=volumetric_runoff_coeff_m3_ha, soil_loss_rate_m3_ha_yr | Soil parameters hidden — agent must infer Cv and R from site description and soil type
```

## Multimodal Expansion

Candidate modality families: `spatial-map`, `tabular-source`, `time-series`.

Use catchment plans, rainfall tables, hyetographs, and drainage schedules as source artifacts.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Connect rainfall/runoff outputs to detention, pipe, HGL, outlet, and water-quality checks.

First-pass composition tags: `shared-context`, `pipeline`, `evidence-assembly`.

## Meta-Harness Handles

Candidate operation handles: `parameters`, `outputs`, `difficulty`, `archetype`, `evidence_profile`, `hidden_parameter_policy`, `source_geometry`, `source_table`, `source_timeseries`.

Practical operations to consider:

- `projection`: isolate the arithmetic-only world, source-interpretation world, or evidence-review world.
- `difference`: remove visible parameters, calculator access, source labels, or intermediate hints.
- `subset`: restrict to one archetype, standard, modality, or difficulty tier.
- `product`: compose with a downstream or upstream task that consumes/produces compatible engineering quantities.

## Repair/Event Candidates

- Trigger `evidence_profile` repair if the model reaches the right number without citing or preserving the source artifact.
- Trigger `verifier` repair if final-output tolerances pass while intermediate units, assumptions, or handoff values are inconsistent.
- Trigger `world_schema` repair if a promising composition lacks explicit handoff fields or operation handles.
