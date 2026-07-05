# ABOUTME: First-pass task-world opportunity card for intersection-sight-distance.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / sight-distance / intersection-sight-distance

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/intersection_sight_distance`
- Discipline: `civil`
- Category: `sight-distance`
- Tool mode: `with-tool`
- Standards: AGRD Part 4A §3
- Tags: civil; roads; sight-distance; intersection; gap-acceptance; deterministic

## Current Task Shape

Calculates the required intersection sight distance (ISD) along the major road at unsignalised intersections using ISD = V × t_gap / 3.6 per AGRD Part 4A. Adjusts the base gap acceptance time for control type, vehicle class, approach grade, and number of crossing lanes, then derives sight-triangle dimensions for clearance verification.

## Existing Deterministic Contract

- Parameters: `6`
- Outputs: `4`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `setback_distance_m`, `vehicle_type`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `design_speed_kmh` | Design speed of the major road V | float / km/h | range=40..130 |
| `control_type` | Traffic control on the minor approach | enum | values=give_way, stop |
| `approach_grade_pct` | Grade of the minor-road approach (positive = upgrade from intersection) | float / % | range=-6.0..10.0 |
| `num_lanes_to_cross` | Number of lanes on the major road the minor-road vehicle must cross | int / lanes | range=2..6 |
| `vehicle_type` | Design vehicle entering from the minor road | enum | values=passenger, single_unit_truck, semi_trailer |
| `setback_distance_m` | Distance from major-road edge to driver eye on the minor approach | float / m | range=3.0..15.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `gap_time_s` | Total gap acceptance time including all corrections (s) |  | tolerance=0.03 |
| `required_isd_m` | Required intersection sight distance along the major road (m) |  | tolerance=0.03 |
| `sight_triangle_major_m` | Sight triangle leg along the major road (m) |  | tolerance=0.03 |
| `sight_triangle_minor_m` | Sight triangle leg along the minor road (m) |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `suburban_t_intersection` | T-intersection on a suburban arterial with give-way control and flat approach | sydney-suburban-arterial; melbourne-local-collector; brisbane-suburban-road |
| `rural_crossroad` | Rural crossroads intersection with stop control on the minor road serving passenger vehicles | bruce-highway-side-road-qld; princes-highway-crossroad-vic; new-england-highway-nsw |
| `urban_multilane` | Urban multilane road with stop-controlled side street serving passenger and single-unit truck traffic | sydney-pacific-highway-side-road; melbourne-punt-road-lane; gold-coast-highway-access |
| `industrial_access` | Industrial estate access onto a collector road designed for semi-trailer turning movements | wetherill-park-industrial-nsw; laverton-north-industrial-vic; acacia-ridge-industrial-qld |

### Difficulty Notes

```text
easy: all_given | All parameters given, flat grade, passenger vehicle on a two-lane road
medium: all_given | All parameters given, any intersection type including steep grades and extra lanes
hard: partial | hidden=vehicle_type, setback_distance_m | Vehicle type and setback distance hidden — agent must infer from intersection context
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
