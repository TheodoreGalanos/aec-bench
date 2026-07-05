# ABOUTME: First-pass task-world opportunity card for gutter-sizing.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / stormwater-roof / gutter-sizing

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/gutter_sizing`
- Discipline: `civil`
- Category: `stormwater-roof`
- Tool mode: `with-tool`
- Standards: AS/NZS 3500.3:2025
- Tags: civil; drainage; stormwater; plumbing; roof-drainage; gutter

## Current Task Shape

Sizes eaves gutters by computing the design stormwater flow from the roof catchment area and rainfall intensity, then selecting the smallest standard gutter profile whose capacity (scaled from the AS/NZS 3500.3 Table 4.2 reference grade by the square root of the installed grade ratio) meets or exceeds the demand. Used in building roof drainage design to prevent overflow and water damage.

## Existing Deterministic Contract

- Parameters: `4`
- Outputs: `4`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `rainfall_intensity_mm_hr`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `roof_catchment_area_m2` | Effective roof catchment area draining to the gutter run | float / m² | range=10..5000 |
| `rainfall_intensity_mm_hr` | Design rainfall intensity for the ARI and duration | float / mm/hr | range=50..300; derivable_from=archetype |
| `gutter_profile` | Nominated eaves gutter profile | enum | values=100mm_quad, 115mm_quad, 125mm_half_round, 150mm_quad, 150mm_half_round, 175mm_OG |
| `gutter_grade_pct` | Longitudinal grade of the gutter (percentage) | float / % | range=0.1..2.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `design_flow_l_s` | Design stormwater flow from the catchment (L/s) |  | tolerance=0.03 |
| `gutter_capacity_l_s` | Capacity of the selected gutter at the installed grade (L/s) |  | tolerance=0.05 |
| `required_gutter_size_mm` | Nominal size of the smallest adequate standard gutter (mm) |  | tolerance=0.01 |
| `compliance` | Compliance flag: 1.0 if capacity >= design flow, else 0.0 |  | tolerance=0.01 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `residential_house` | Single or two-storey residential dwelling with pitched roof and standard eaves gutters | sydney-inner-west-house; melbourne-bayside-cottage; brisbane-queenslander |
| `terrace_row` | Terrace or row-house with narrow roof draining to a single gutter run | sydney-paddington-terrace; melbourne-fitzroy-row-house; adelaide-north-terrace |
| `commercial_awning` | Street-front commercial awning or verandah with a short gutter span | brisbane-fortitude-valley-awning; perth-cbd-shopfront; hobart-waterfront-verandah |
| `industrial_shed` | Large industrial or warehouse building with long-span metal roof gutters | darwin-industrial-estate; townsville-port-shed; cairns-processing-facility |

### Difficulty Notes

```text
easy: all_given | Small residential roof, all parameters given — straightforward capacity check
medium: all_given | Larger commercial or industrial roof, all parameters given, higher flows may require upsizing
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
