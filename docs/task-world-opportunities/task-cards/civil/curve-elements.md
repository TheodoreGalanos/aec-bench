# ABOUTME: First-pass task-world opportunity card for curve-elements.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / horizontal-geometry / curve-elements

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/curve_elements`
- Discipline: `civil`
- Category: `horizontal-geometry`
- Tool mode: `with-tool`
- Standards: AGRD Part 3
- Tags: civil; roads; horizontal-geometry; curves; chainage; deterministic

## Current Task Shape

Computes the geometric elements of a simple horizontal circular curve given the radius, deflection angle, and intersection-point chainage, per AGRD Part 3. Derives tangent length (T = R tan(delta/2)), arc length, external distance, mid-ordinate, and PC/PT chainages. Used in road and rail alignment design to set out curve geometry in the field.

## Existing Deterministic Contract

- Parameters: `3`
- Outputs: `6`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `ip_chainage_m`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `curve_radius_m` | Horizontal curve radius R | float / m | range=25..2000 |
| `deflection_angle_deg` | Deflection (intersection) angle Δ between tangents | float / degrees | range=5..120 |
| `ip_chainage_m` | Chainage of the intersection point (IP) | float / m | range=100..50000 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `tangent_length_m` | Tangent length T (m) |  | tolerance=0.03 |
| `arc_length_m` | Arc length L (m) |  | tolerance=0.03 |
| `external_distance_m` | External distance E (m) |  | tolerance=0.03 |
| `mid_ordinate_m` | Mid-ordinate M (m) |  | tolerance=0.03 |
| `pc_chainage_m` | Chainage of the point of curvature PC (m) |  | tolerance=0.03 |
| `pt_chainage_m` | Chainage of the point of tangency PT (m) |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `urban_intersection` | Urban intersection approach with tight curve radius and large deflection angle | sydney-cbd-intersection; melbourne-city-roundabout; brisbane-inner-junction |
| `rural_highway` | Rural two-lane highway with large-radius sweeping curves | bruce-highway-qld; pacific-highway-nsw; hume-highway-vic |
| `motorway_ramp` | Motorway on/off ramp with moderate radius and variable deflection | m1-pacific-motorway-ramp; m2-hills-motorway-ramp; citylink-melbourne-ramp |
| `residential_street` | Low-speed residential street with tight geometry | suburban-cul-de-sac; estate-road-curve; local-collector-bend |

### Difficulty Notes

```text
easy: all_given | All parameters given, gentle curve on a rural highway
medium: all_given | All parameters given, any road type and curve geometry
hard: partial | hidden=ip_chainage_m | IP chainage hidden — agent must back-calculate from PC chainage and tangent length
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
