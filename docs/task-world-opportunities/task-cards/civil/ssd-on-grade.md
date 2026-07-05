# ABOUTME: First-pass task-world opportunity card for ssd-on-grade.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / sight-distance / ssd-on-grade

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/ssd_on_grade`
- Discipline: `civil`
- Category: `sight-distance`
- Tool mode: `with-tool`
- Standards: AGRD Part 3 §5
- Tags: civil; roads; sight-distance; stopping; grade; deterministic

## Current Task Shape

Computes stopping sight distance (SSD) on graded road segments as the sum of reaction distance d_r = V*t_r/3.6 and braking distance d_b = V^2/(254*(f+g)), using speed-dependent longitudinal friction coefficients from AGRD Part 3 Table 5.5. Accounts for uphill and downhill grades to verify geometric design adequacy for safe vehicle stopping.

## Existing Deterministic Contract

- Parameters: `3`
- Outputs: `3`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `reaction_time_s`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `design_speed_km_h` | Design speed V | float / km/h | range=40..130 |
| `grade_pct` | Longitudinal grade (positive = uphill, negative = downhill) | float / % | range=-10.0..10.0 |
| `reaction_time_s` | Driver reaction time t_r | float / s | range=1.5..2.5 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `reaction_distance_m` | Reaction distance component d_r (m) |  | tolerance=0.03 |
| `braking_distance_m` | Braking distance component d_b (m) |  | tolerance=0.03 |
| `stopping_sight_distance_m` | Total stopping sight distance SSD (m) |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `urban_local_street` | Low-speed urban local street with pedestrian activity and on-street parking | sydney-residential-street; melbourne-local-road; brisbane-suburban-street |
| `suburban_arterial` | Suburban arterial road with moderate speeds and intersection access | sydney-pennant-hills-road; melbourne-springvale-road; brisbane-waterworks-road |
| `rural_highway` | Rural two-lane highway through open terrain with higher operating speeds | bruce-highway-qld; princes-highway-vic; pacific-highway-nsw |
| `mountain_road` | Winding mountain road with steep grades and limited sight lines | great-ocean-road-vic; bells-line-of-road-nsw; gillies-highway-qld |

### Difficulty Notes

```text
easy: all_given | All parameters given, flat to gentle grade on a suburban arterial
medium: all_given | All parameters given, any road type including steep grades
hard: partial | hidden=reaction_time_s | Reaction time hidden — agent must infer t_r from road type and driver alertness context
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
