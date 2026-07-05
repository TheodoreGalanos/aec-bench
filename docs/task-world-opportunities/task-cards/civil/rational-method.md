# ABOUTME: First-pass task-world opportunity card for rational-method.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / hydrologic-calculations / rational-method

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/rational_method`
- Discipline: `civil`
- Category: `hydrologic-calculations`
- Tool mode: `with-tool`
- Standards: ARR; HEC-22
- Tags: hydrology; drainage; runoff; stormwater

## Current Task Shape

Computes peak stormwater runoff discharge using the rational method formula Q = C*I*A/360, where C is the runoff coefficient, I is the design rainfall intensity, and A is the catchment area. Applicable to small catchments up to 80 hectares per ARR and HEC-22, widely used for sizing drainage infrastructure in urban and rural settings.

## Existing Deterministic Contract

- Parameters: `3`
- Outputs: `2`
- Archetypes: `5`
- Visibility mix: all_given; partial
- Hidden parameters: `runoff_coefficient`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `runoff_coefficient` | Runoff coefficient C (dimensionless) | float / - | range=0.1..0.95; derivable_from=archetype |
| `rainfall_intensity_mm_hr` | Design rainfall intensity I | float / mm/hr | range=10..300 |
| `catchment_area_ha` | Catchment area A | float / ha | range=0.1..80 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `peak_runoff_m3_s` | Peak runoff Q (m³/s) |  | tolerance=0.03 |
| `peak_runoff_l_s` | Peak runoff Q (L/s) |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `paved_commercial` | Dense commercial area with impervious surfaces | sydney-cbd; melbourne-cbd; brisbane-cbd |
| `suburban_residential` | Suburban residential area with mixed surfaces | sydney-western-suburbs; melbourne-outer; perth-northern-suburbs |
| `low_density_rural` | Low-density rural or semi-rural area | hunter-valley-rural; darling-downs-pastoral; barossa-valley |
| `industrial_warehouse` | Industrial or warehouse precinct with large roof areas | sydney-western-industrial; melbourne-northern-industrial |
| `parkland_open_space` | Parks, playing fields, and open green space | brisbane-parkland; adelaide-parklands; canberra-green-belt |

### Difficulty Notes

```text
easy: all_given | Small catchment, moderate intensity — straightforward application of Q = CIA / 360
medium: all_given | Larger catchment with higher intensity — same formula, bigger numbers
hard: partial | hidden=runoff_coefficient | Runoff coefficient hidden — agent must infer C from site description
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
