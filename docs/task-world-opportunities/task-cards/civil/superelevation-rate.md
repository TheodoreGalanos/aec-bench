# ABOUTME: First-pass task-world opportunity card for superelevation-rate.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / horizontal-geometry / superelevation-rate

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/superelevation_rate`
- Discipline: `civil`
- Category: `horizontal-geometry`
- Tool mode: `with-tool`
- Standards: AGRD Part 3 §7.5; AASHTO Green Book Ch. 3
- Tags: civil; roads; horizontal-geometry; superelevation; curves; deterministic

## Current Task Shape

Determines the required superelevation rate and transition development length for horizontal road curves using the point-mass equilibrium equation e + f = V^2/(127*R) per AASHTO Green Book and Austroads AGRD Part 3 Section 7.5. Balances centripetal force demand between pavement banking and tyre side friction to ensure vehicle stability through curves.

## Existing Deterministic Contract

- Parameters: `5`
- Outputs: `2`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `side_friction_factor`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `design_speed_km_h` | Design speed V | float / km/h | range=60..130 |
| `curve_radius_m` | Horizontal curve radius R | float / m | range=50..500 |
| `side_friction_factor` | Side friction factor f | float / - | range=0.08..0.19; derivable_from=archetype |
| `lane_width_m` | Lane width w | float / m | range=3.0..4.5 |
| `rotation_rate` | Maximum rate of pavement rotation (e.g. 1/200 = 0.005) | float / m/m | range=0.005..0.01 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `superelevation_rate_pct` | Required superelevation rate e (%) |  | tolerance=0.03 |
| `development_length_m` | Superelevation development (runoff) length Ls (m) |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `rural_highway` | Rural two-lane highway with moderate traffic and open terrain | bruce-highway-qld; princes-highway-vic; great-western-highway-nsw |
| `urban_arterial` | Urban multi-lane arterial road with signalised intersections | sydney-parramatta-road; melbourne-hoddle-street; brisbane-coronation-drive |
| `freeway` | High-speed divided freeway or motorway | m1-pacific-motorway; m2-hills-motorway; western-ring-road-melbourne |
| `mountain_road` | Winding mountain road with tight curves and steep grades | great-ocean-road-vic; bells-line-of-road-nsw; gillies-highway-qld |

### Difficulty Notes

```text
easy: all_given | All parameters given, gentle curve on a rural highway
medium: all_given | All parameters given, any road type and curve geometry
hard: partial | hidden=side_friction_factor | Side friction factor hidden — agent must infer f from road type and design speed
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
