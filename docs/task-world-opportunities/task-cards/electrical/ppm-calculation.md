# ABOUTME: First-pass task-world opportunity card for ppm-calculation.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# electrical / cctv-design / ppm-calculation

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/electrical/ppm_calculation`
- Discipline: `electrical`
- Category: `cctv-design`
- Tool mode: `with-tool`
- Standards: IEC 62676-4; EN 62676-4
- Tags: electrical; cctv; ppm; camera; security; deterministic

## Current Task Shape

Calculates CCTV pixel density at a target distance using horizontal camera resolution, sensor width, and lens focal length. The reduced pinhole-camera method estimates horizontal field of view, pixels per metre, and margin against a specified surveillance target density.

## Existing Deterministic Contract

- Parameters: `5`
- Outputs: `3`
- Archetypes: `3`
- Visibility mix: all_given; partial
- Hidden parameters: `target_ppm`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `horizontal_pixels` | Horizontal camera resolution | float / px | range=640..12000 |
| `sensor_width_mm` | Camera sensor width | float / mm | range=2.0..25.0 |
| `lens_focal_length_mm` | Lens focal length | float / mm | range=2.0..80.0 |
| `target_distance_m` | Distance from camera to target plane | float / m | range=1.0..200.0 |
| `target_ppm` | Required pixel density target | float / px/m | range=20..1000 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `horizontal_field_of_view_m` | Horizontal field of view at the target plane |  | tolerance=0.03 |
| `pixels_per_meter` | Pixel density at target distance |  | tolerance=0.03 |
| `target_ppm_margin_pct` | Margin relative to target pixel density |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `detection_camera` | Wide-angle detection camera | car-park; site-perimeter |
| `recognition_camera` | Recognition camera at an access point | building-entry; station-gate |
| `identification_camera` | High-density identification camera | cash-office; secure-room |

### Difficulty Notes

```text
easy: all_given | Detection or recognition camera with all geometry given
medium: all_given | Mixed camera objectives and target densities
hard: partial | hidden=target_ppm | Target PPM hidden in the surveillance objective
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
