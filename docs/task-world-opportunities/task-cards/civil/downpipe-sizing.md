# ABOUTME: First-pass task-world opportunity card for downpipe-sizing.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / stormwater-roof / downpipe-sizing

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/downpipe_sizing`
- Discipline: `civil`
- Category: `stormwater-roof`
- Tool mode: `with-tool`
- Standards: AS/NZS 3500.3:2025
- Tags: civil; drainage; stormwater; plumbing; roof-drainage

## Current Task Shape

Sizes roof downpipes by calculating the design stormwater flow per downpipe from the catchment area and rainfall intensity, then selecting the smallest standard uPVC round diameter whose full-bore capacity meets or exceeds the demand per AS/NZS 3500.3 Table 4.3. Used in building plumbing and roof drainage design to ensure adequate stormwater disposal from roofs.

## Existing Deterministic Contract

- Parameters: `3`
- Outputs: `4`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `rainfall_intensity_mm_hr`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `roof_catchment_area_m2` | Effective roof catchment area served by each group of downpipes | float / m² | range=20..5000 |
| `rainfall_intensity_mm_hr` | Design rainfall intensity for the ARI and duration | float / mm/hr | range=50..300; derivable_from=archetype |
| `num_downpipes` | Number of downpipes draining the catchment area | int / - | range=1..20 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `design_flow_l_s` | Design flow per downpipe (L/s) |  | tolerance=0.03 |
| `selected_diameter_mm` | Selected standard downpipe diameter (mm) |  | tolerance=0.01 |
| `selected_capacity_l_s` | Full-bore capacity of the selected downpipe (L/s) |  | tolerance=0.03 |
| `compliance` | Compliance flag: 1.0 if capacity >= design flow, else 0.0 |  | tolerance=0.01 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `residential_house` | Single-storey or two-storey residential dwelling with pitched roof | sydney-inner-west-house; melbourne-bayside-cottage; brisbane-queenslander |
| `commercial_warehouse` | Large commercial warehouse or retail shed with flat or low-pitch metal roof | sydney-industrial-park; melbourne-western-logistics; brisbane-trade-coast |
| `covered_car_park` | Multi-level or single-level covered car park with exposed upper deck | perth-cbd-car-park; adelaide-airport-parking; gold-coast-shopping-centre |
| `industrial_shed` | Industrial manufacturing or storage shed with large-span metal roof | darwin-industrial-estate; townsville-port-shed; cairns-processing-facility |

### Difficulty Notes

```text
easy: all_given | Small residential roof, all parameters given — straightforward table lookup
medium: all_given | Larger commercial or industrial roof, all parameters given, higher flows
hard: partial | hidden=rainfall_intensity_mm_hr | Rainfall intensity hidden — agent must infer I from site context and ARI
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
