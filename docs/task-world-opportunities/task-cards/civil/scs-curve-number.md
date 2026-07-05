# ABOUTME: First-pass task-world opportunity card for scs-curve-number.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / hydrologic-calculations / scs-curve-number

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/scs_curve_number`
- Discipline: `civil`
- Category: `hydrologic-calculations`
- Tool mode: `with-tool`
- Standards: NRCS TR-55
- Tags: hydrology; drainage; runoff; stormwater; curve-number; SCS

## Current Task Shape

Calculates storm runoff depth from rainfall using the SCS/NRCS curve number method per TR-55. Derives potential maximum retention S = (25400/CN) - 254 and initial abstraction Ia = 0.2*S, then computes excess rainfall as Q = (P - Ia)^2 / (P - Ia + S). Widely used for hydrologic modelling of ungauged catchments based on soil type and land cover.

## Existing Deterministic Contract

- Parameters: `2`
- Outputs: `3`
- Archetypes: `5`
- Visibility mix: all_given; partial
- Hidden parameters: `curve_number`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `rainfall_depth_mm` | Total storm rainfall depth P | float / mm | range=5..300 |
| `curve_number` | SCS/NRCS curve number CN (dimensionless) | float / - | range=30..98; derivable_from=archetype |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `potential_max_retention_mm` | Potential maximum retention S (mm) |  | tolerance=0.03 |
| `initial_abstraction_mm` | Initial abstraction Ia (mm) |  | tolerance=0.03 |
| `runoff_depth_mm` | Runoff depth Q (mm) |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `parkland_sandy_soil` | Parkland and open green space on well-drained sandy soil (HSG A) | adelaide-parklands-sand; perth-coastal-reserve; gold-coast-hinterland-park |
| `suburban_residential` | Suburban residential area with lawns and driveways on loamy soil (HSG B) | sydney-western-suburbs; melbourne-outer-east; brisbane-northern-suburbs |
| `agricultural_pasture` | Agricultural pasture on moderately drained silt-loam soil (HSG C) | hunter-valley-pastoral; darling-downs-farmland; barossa-valley-grazing |
| `commercial_industrial` | Commercial or industrial precinct with mostly impervious surfaces on clay soil (HSG D) | sydney-cbd-redevelopment; melbourne-docklands; brisbane-port-industrial |
| `forest_sandy_loam` | Forested catchment on sandy-loam soil with good ground cover (HSG B) | blue-mountains-bushland; dandenong-ranges-forest; tamborine-mountain-reserve |

### Difficulty Notes

```text
easy: all_given | Direct application of SCS equations with all parameters given
medium: all_given | Wider parameter ranges; agent must handle low-CN cases where Q may be zero
hard: partial | hidden=curve_number | Curve number hidden — agent must infer CN from land cover and soil group description
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
