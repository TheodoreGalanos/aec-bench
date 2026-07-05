# ABOUTME: First-pass task-world opportunity card for min-curve-radius.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / horizontal-geometry / min-curve-radius

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/min_curve_radius`
- Discipline: `civil`
- Category: `horizontal-geometry`
- Tool mode: `with-tool`
- Standards: AGRD Part 3 §7
- Tags: civil; roads; horizontal-geometry; curves; radius; deterministic

## Current Task Shape

Calculates the absolute minimum and desirable minimum horizontal curve radius for road design using R_min = V^2 / (127 * (e_max + f)) per Austroads Guide to Road Design Part 3 Section 7. The desirable radius uses a reduced friction factor (0.7f) for an additional safety margin. Used in road geometric design to ensure vehicle stability and driver comfort on horizontal curves.

## Existing Deterministic Contract

- Parameters: `3`
- Outputs: `2`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `side_friction_factor`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `design_speed_km_h` | Design speed V | float / km/h | range=40..130 |
| `max_superelevation_pct` | Maximum superelevation rate e_max | float / % | range=3.0..8.0 |
| `side_friction_factor` | Side friction factor f (speed-dependent, from AGRD Table 7.5) | float / - | range=0.09..0.35; derivable_from=archetype |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `min_radius_m` | Absolute minimum horizontal curve radius R_min (m) |  | tolerance=0.03 |
| `desirable_min_radius_m` | Desirable minimum horizontal curve radius R_desirable (m) |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `urban_local` | Low-speed urban local road with frequent intersections and pedestrian activity | sydney-local-street; melbourne-inner-suburb; brisbane-residential-road |
| `suburban_arterial` | Suburban arterial road with moderate traffic and signalised intersections | sydney-parramatta-road; melbourne-springvale-road; brisbane-waterworks-road |
| `rural_highway` | Rural two-lane highway through open terrain with higher operating speeds | bruce-highway-qld; princes-highway-vic; great-western-highway-nsw |
| `motorway` | High-speed divided motorway with grade-separated interchanges | m1-pacific-motorway; m2-hills-motorway; western-ring-road-melbourne |

### Difficulty Notes

```text
easy: all_given | All parameters given, low-speed urban or suburban road
medium: all_given | All parameters given, any road type and speed environment
hard: partial | hidden=side_friction_factor | Side friction factor hidden — agent must infer f from design speed using AGRD Table 7.5
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
