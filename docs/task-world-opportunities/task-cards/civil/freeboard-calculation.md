# ABOUTME: First-pass task-world opportunity card for freeboard-calculation.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / coastal-drainage / freeboard-calculation

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/freeboard_calculation`
- Discipline: `civil`
- Category: `coastal-drainage`
- Tool mode: `both`
- Standards: NZS 4404:2010; MfE Guidance 2024
- Tags: coastal; flood; freeboard; sea-level-rise; drainage

## Current Task Shape

Determines the total freeboard and minimum crest or floor level for coastal and flood-prone structures by summing component allowances for wave overtopping, sea level rise, construction tolerance, and a consequence-based safety margin, per NZS 4404:2010 and MfE Guidance 2024. Used in coastal and floodplain development to set minimum building levels above the design water surface.

## Existing Deterministic Contract

- Parameters: `5`
- Outputs: `2`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `construction_tolerance_m`, `safety_margin_m`, `slr_allowance_m`, `wave_allowance_m`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `design_water_level_m` | Design still-water level including tidal and storm surge components (m above datum) | float / m | range=0.5..8.0 |
| `wave_allowance_m` | Wave overtopping allowance depending on wave height and structure type | float / m | range=0.3..1.0; derivable_from=archetype |
| `slr_allowance_m` | Climate change sea level rise allowance for planning horizon | float / m | range=0.1..1.0; derivable_from=archetype |
| `construction_tolerance_m` | Construction tolerance allowance | float / m | range=0.05..0.15; derivable_from=archetype |
| `safety_margin_m` | Safety margin based on consequence category | float / m | range=0.15..0.5; derivable_from=archetype |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `total_freeboard_m` | Total freeboard allowance (m) |  | tolerance=0.03 |
| `minimum_crest_level_m` | Minimum crest or floor level (m above datum) |  | tolerance=0.05 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `residential_coastal` | Residential coastal dwelling with low consequence category | gold-coast-beachfront-house; auckland-harbour-dwelling; christchurch-estuary-residence |
| `commercial_waterfront` | Commercial waterfront development with medium consequence category | sydney-darling-harbour-precinct; wellington-waterfront-retail; brisbane-river-commercial |
| `critical_infrastructure` | Critical infrastructure with high consequence category (hospital, power station) | tauranga-port-substation; darwin-hospital-coastal; townsville-water-treatment-plant |
| `seawall_revetment` | Seawall or revetment structure protecting coastal assets | napier-marine-parade-seawall; cairns-esplanade-revetment; perth-scarborough-seawall |

### Difficulty Notes

```text
easy: all_given | Low consequence structure, all parameters given — straightforward addition
medium: all_given | Higher consequence, larger allowances — all parameters given, same formula
hard: partial | hidden=wave_allowance_m, slr_allowance_m, construction_tolerance_m, safety_margin_m | Wave allowance, SLR allowance, construction tolerance, and safety margin hidden — agent must infer from structure type and consequence category
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
