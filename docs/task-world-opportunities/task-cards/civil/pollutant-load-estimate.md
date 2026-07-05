# ABOUTME: First-pass task-world opportunity card for pollutant-load-estimate.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / water-quality / pollutant-load-estimate

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/pollutant_load_estimate`
- Discipline: `civil`
- Category: `water-quality`
- Tool mode: `both`
- Standards: MUSIC guidelines; Australian Runoff Quality (ARQ)
- Tags: civil; water-quality; stormwater; pollutant; EMC; TSS; phosphorus; nitrogen

## Current Task Shape

Estimates annual Total Suspended Solids (TSS), Total Phosphorus (TP), and Total Nitrogen (TN) pollutant loads from urban catchments using the Event Mean Concentration (EMC) method. Computes annual runoff volume as V = C*P*A*10 and multiplies by EMC values per MUSIC guidelines and Australian Runoff Quality to support water-sensitive urban design.

## Existing Deterministic Contract

- Parameters: `6`
- Outputs: `4`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `emc_tn_mg_l`, `emc_tp_mg_l`, `emc_tss_mg_l`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `catchment_area_ha` | Contributing catchment area A | float / ha | range=0.5..500.0 |
| `annual_rainfall_mm` | Mean annual rainfall P | float / mm | range=200..3000; derivable_from=archetype |
| `runoff_coefficient` | Volumetric runoff coefficient C (fraction of rainfall that becomes runoff) | float / - | range=0.05..0.95; derivable_from=archetype |
| `emc_tss_mg_l` | Event mean concentration of Total Suspended Solids | float / mg/L | range=10..400; derivable_from=archetype |
| `emc_tp_mg_l` | Event mean concentration of Total Phosphorus | float / mg/L | range=0.05..1.0; derivable_from=archetype |
| `emc_tn_mg_l` | Event mean concentration of Total Nitrogen | float / mg/L | range=0.3..5.0; derivable_from=archetype |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `annual_runoff_volume_m3` | Annual runoff volume V (m³/yr) |  | tolerance=0.03 |
| `tss_load_kg_yr` | Annual Total Suspended Solids load (kg/yr) |  | tolerance=0.03 |
| `tp_load_kg_yr` | Annual Total Phosphorus load (kg/yr) |  | tolerance=0.03 |
| `tn_load_kg_yr` | Annual Total Nitrogen load (kg/yr) |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `residential_suburb` | Residential suburban catchment with moderate impervious fraction and typical domestic pollutant sources | sydney-western-suburbs; melbourne-southeast-growth; brisbane-northern-suburbs; perth-southern-corridor |
| `commercial_centre` | Commercial or mixed-use town centre with high impervious fraction and heavy traffic | sydney-cbd-fringe; melbourne-docklands; brisbane-fortitude-valley; adelaide-north-terrace |
| `industrial_estate` | Industrial estate with high impervious cover and elevated pollutant concentrations from warehousing and logistics | sydney-smithfield-industrial; melbourne-western-ring; brisbane-eagle-farm; perth-kwinana-strip |
| `parkland_open_space` | Parkland or open space catchment with low impervious fraction and minimal pollutant sources | sydney-centennial-park; melbourne-yarra-bend; brisbane-south-bank; canberra-lake-burley-griffin |

### Difficulty Notes

```text
easy: all_given | All parameters given directly — straightforward EMC load calculation
medium: all_given | All parameters given but industrial or commercial land use with higher EMC values — agent must handle larger numbers carefully
hard: partial | hidden=emc_tss_mg_l, emc_tp_mg_l, emc_tn_mg_l | EMC values hidden — agent must infer typical concentrations from land use type and site description
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
