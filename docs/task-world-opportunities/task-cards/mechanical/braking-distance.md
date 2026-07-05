# ABOUTME: First-pass task-world opportunity card for braking-distance.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# mechanical / braking-systems / braking-distance

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/mechanical/braking_distance`
- Discipline: `mechanical`
- Category: `braking-systems`
- Tool mode: `with-tool`
- Standards: EN 14531-1; AS 7520.3
- Tags: mechanical; rolling-stock; braking-distance; deceleration; deterministic

## Current Task Shape

Calculates train stopping distance under constant deceleration from train mass, initial speed, brake effort, adhesion limit, and track gradient. The template caps braking effort by wheel-rail adhesion and reports net deceleration, stopping distance, and stopping time.

## Existing Deterministic Contract

- Parameters: `5`
- Outputs: `4`
- Archetypes: `2`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `train_mass_t` | Train mass | float / t | range=5.0..2000.0 |
| `initial_speed_km_h` | Initial speed before braking | float / km/h | range=5.0..200.0 |
| `brake_effort_kn` | Available braking effort | float / kN | range=1.0..5000.0 |
| `adhesion_coefficient` | Wheel-rail adhesion coefficient | float | range=0.03..0.35 |
| `track_gradient_pct` | Track gradient, positive for downhill in braking direction | float / % | range=-5.0..5.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `adhesion_limited_brake_effort_kn` | Effective brake effort after adhesion limit |  | tolerance=0.03 |
| `net_deceleration_m_s2` | Net braking deceleration |  | tolerance=0.03 |
| `stopping_distance_m` | Stopping distance |  | tolerance=0.03 |
| `stopping_time_s` | Stopping time |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `light_rail_vehicle` | Light rail vehicle braking on urban alignment | urban-light-rail; depot-approach-track |
| `heavy_freight_train` | Heavy freight train braking on mainline track | regional-mainline; freight-terminal-approach |

### Difficulty Notes

```text
easy: all_given | All parameters given for light rail braking
medium: all_given | All parameters given across passenger and freight braking cases
hard: all_given | All parameters given for heavy freight braking cases
```

## Multimodal Expansion

Candidate modality families: `chart-curve`, `drawing-geometry`, `tabular-source`.

Use schematics, equipment curves, schedules, commissioning tables, and source datasheets.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Compose with tasks that share the same site context, source artifact, or downstream output obligation.

First-pass composition tags: `shared-context`, `pipeline`, `evidence-assembly`.

## Meta-Harness Handles

Candidate operation handles: `parameters`, `outputs`, `difficulty`, `archetype`, `evidence_profile`, `source_geometry`, `source_table`, `source_curve`.

Practical operations to consider:

- `projection`: isolate the arithmetic-only world, source-interpretation world, or evidence-review world.
- `difference`: remove visible parameters, calculator access, source labels, or intermediate hints.
- `subset`: restrict to one archetype, standard, modality, or difficulty tier.
- `product`: compose with a downstream or upstream task that consumes/produces compatible engineering quantities.

## Repair/Event Candidates

- Trigger `evidence_profile` repair if the model reaches the right number without citing or preserving the source artifact.
- Trigger `verifier` repair if final-output tolerances pass while intermediate units, assumptions, or handoff values are inconsistent.
- Trigger `world_schema` repair if a promising composition lacks explicit handoff fields or operation handles.
