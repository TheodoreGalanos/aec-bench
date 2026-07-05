# ABOUTME: First-pass task-world opportunity card for signal-sighting-distance.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# electrical / signal-sighting / signal-sighting-distance

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/electrical/signal_sighting_distance`
- Discipline: `electrical`
- Category: `signal-sighting`
- Tool mode: `with-tool`
- Standards: Network Rail NR/L2/SIG/10158; AS 7711
- Tags: electrical; rail; signal-sighting; braking-distance; deterministic

## Current Task Shape

Calculates the minimum signal sighting distance required for a train driver to perceive, react, and brake to a stop. The reduced kinematic method combines reaction distance with braking distance adjusted for track gradient.

## Existing Deterministic Contract

- Parameters: `4`
- Outputs: `5`
- Archetypes: `2`
- Visibility mix: all_given; partial
- Hidden parameters: `track_gradient_pct`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `maximum_line_speed_kmh` | Maximum line speed | float / km/h | range=5..250 |
| `service_braking_rate_m_s2` | Service braking rate | float / m/s2 | range=0.2..2.0 |
| `driver_reaction_time_s` | Driver perception-reaction time | float / s | range=0..10 |
| `track_gradient_pct` | Track gradient, positive for upgrade and negative for downgrade | float / % | range=-5..5 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `line_speed_m_s` | Line speed converted to m/s |  | tolerance=0.01 |
| `reaction_distance_m` | Distance travelled during driver reaction |  | tolerance=0.03 |
| `grade_adjusted_braking_rate_m_s2` | Braking rate adjusted for track gradient |  | tolerance=0.03 |
| `braking_distance_m` | Kinematic braking distance |  | tolerance=0.03 |
| `required_sighting_distance_m` | Total required signal sighting distance |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `metro_signal` | Metro or suburban signal sighting check | metro-line; suburban-corridor |
| `mainline_signal` | Mainline signal sighting check | regional-mainline; freight-corridor |

### Difficulty Notes

```text
easy: all_given | Metro signal with all inputs visible
medium: all_given | Metro or mainline signal
hard: partial | hidden=track_gradient_pct | Track gradient hidden in alignment context
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
