# ABOUTME: First-pass task-world opportunity card for road-uniformity-check.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# electrical / road-lighting / road-uniformity-check

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/electrical/road_uniformity_check`
- Discipline: `electrical`
- Category: `road-lighting`
- Tool mode: `with-tool`
- Standards: EN 13201-2; AS/NZS 1158.2
- Tags: electrical; lighting; road-lighting; uniformity; deterministic

## Current Task Shape

Calculates overall and longitudinal road lighting uniformity ratios and the margin against a target overall uniformity class requirement.

## Existing Deterministic Contract

- Parameters: `5`
- Outputs: `3`
- Archetypes: `2`
- Visibility mix: all_given; partial
- Hidden parameters: `target_overall_uniformity`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `minimum_luminance_cd_m2` | Minimum calculated luminance on the road grid | float / cd/m2 | range=0..5 |
| `average_luminance_cd_m2` | Average calculated luminance on the road grid | float / cd/m2 | range=0.1..10 |
| `longitudinal_min_luminance_cd_m2` | Minimum luminance along the relevant lane line | float / cd/m2 | range=0..5 |
| `longitudinal_max_luminance_cd_m2` | Maximum luminance along the relevant lane line | float / cd/m2 | range=0.1..10 |
| `target_overall_uniformity` | Target overall uniformity ratio | float / - | range=0.1..0.8 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `overall_uniformity_uo` | Overall uniformity ratio |  | tolerance=0.03 |
| `longitudinal_uniformity_ul` | Longitudinal uniformity ratio |  | tolerance=0.03 |
| `overall_uniformity_margin_pct` | Percentage margin against target overall uniformity |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `local_road_grid` | Local road lighting calculation grid | local-road; lighting-grid |
| `arterial_road_grid` | Arterial road luminance calculation grid | arterial-road; lighting-grid |

### Difficulty Notes

```text
easy: all_given | Local road grid with all values visible
medium: all_given | Road lighting grid selected from local or arterial cases
hard: partial | hidden=target_overall_uniformity | Arterial road grid with target class embedded in context
```

## Multimodal Expansion

Candidate modality families: `drawing-geometry`, `spatial-map`, `tabular-source`.

Use alignment drawings, chainage tables, long sections, route maps, and design-speed schedules.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Alignment geometry can feed sight-distance, cant/superelevation, vertical-curve, and comfort checks.

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
