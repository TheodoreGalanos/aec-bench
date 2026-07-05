# ABOUTME: First-pass task-world opportunity card for overlap-calculation.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# electrical / signal-sighting / overlap-calculation

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/electrical/overlap_calculation`
- Discipline: `electrical`
- Category: `signal-sighting`
- Tool mode: `with-tool`
- Standards: Network Rail NR/L2/SIG/10158; AS 7711
- Tags: electrical; rail; signalling; overlap; braking; deterministic

## Current Task Shape

Calculates a reduced rail signalling overlap distance from approach speed, braking rate, track gradient, reaction time, danger point distance, and low-adhesion factor. The template reports full-speed overlap, braking-only timed overlap, and residual danger point clearance.

## Existing Deterministic Contract

- Parameters: `6`
- Outputs: `6`
- Archetypes: `2`
- Visibility mix: all_given; partial
- Hidden parameters: `low_adhesion_factor`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `maximum_approach_speed_kmh` | Maximum train approach speed | float / km/h | range=10..160 |
| `emergency_braking_rate_m_s2` | Emergency braking deceleration rate before adhesion and gradient adjustments | float / m/s2 | range=0.3..1.5 |
| `track_gradient_pct` | Track gradient, positive for rising grade in the direction of travel | float / % | range=-4..4 |
| `reaction_time_s` | Reaction or system allowance time | float / s | range=0.5..5 |
| `danger_point_distance_m` | Available distance from stop signal to danger point | float / m | range=20..2000 |
| `low_adhesion_factor` | Multiplier applied to braking rate for low adhesion | float / - | range=0.4..1 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `approach_speed_m_s` | Approach speed converted to metres per second |  | tolerance=0.03 |
| `gradient_adjusted_braking_rate_m_s2` | Effective braking rate after adhesion and gradient effects |  | tolerance=0.03 |
| `reaction_distance_m` | Distance travelled during reaction time |  | tolerance=0.03 |
| `full_speed_overlap_m` | Full-speed overlap including reaction and braking distance |  | tolerance=0.03 |
| `timed_overlap_option_m` | Braking-only timed overlap distance |  | tolerance=0.03 |
| `danger_point_clearance_m` | Residual distance to the danger point after full-speed overlap |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `metro_signal` | Metro rail signal overlap | metro-rail; signal-overlap |
| `regional_signal` | Regional rail signal overlap | regional-rail; signal-overlap |

### Difficulty Notes

```text
easy: all_given | Metro overlap case with all values visible
medium: all_given | Signal overlap case selected from metro or regional lines
hard: partial | hidden=low_adhesion_factor | Regional signal with low adhesion factor embedded in context
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
