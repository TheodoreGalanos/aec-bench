# ABOUTME: First-pass task-world opportunity card for vertical-curve-design.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / track-geometry / vertical-curve-design

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/vertical_curve_design`
- Discipline: `civil`
- Category: `track-geometry`
- Tool mode: `with-tool`
- Standards: ARTC ETS-05-00; AREMA MRE Chapter 5
- Tags: civil; rail; track-geometry; vertical-curve; grade-transition; deterministic

## Current Task Shape

Computes the minimum vertical curve radius and length required at railway grade transition points using R_v = V^2 / (12.96 * a_v) and L_v = (A/100) * R_v. Ensures vertical acceleration remains within passenger comfort and rolling stock safety limits per ARTC ETS-05-00 and AREMA Chapter 5.

## Existing Deterministic Contract

- Parameters: `4`
- Outputs: `3`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `max_vertical_acceleration_m_s2`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `initial_grade_pct` | Initial longitudinal grade g1 (positive = uphill) | float / % | range=-5.0..5.0 |
| `final_grade_pct` | Final longitudinal grade g2 (positive = uphill) | float / % | range=-5.0..5.0 |
| `design_speed_km_h` | Design operating speed V | float / km/h | range=20..300 |
| `max_vertical_acceleration_m_s2` | Maximum acceptable vertical acceleration a_v for passenger comfort | float / m/s² | range=0.01..0.1; derivable_from=archetype |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `algebraic_grade_difference_pct` | Algebraic grade difference A = /g1 - g2/ (%) |  | tolerance=0.01 |
| `min_vertical_curve_radius_m` | Minimum vertical curve radius R_v (m) |  | tolerance=0.03 |
| `min_vertical_curve_length_m` | Minimum vertical curve length L_v (m) |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `mainline_passenger` | Mainline passenger rail corridor with moderate speeds and comfort requirements | artc-north-south-corridor; sydney-central-west; melbourne-geelong-mainline |
| `heavy_haul_freight` | Heavy haul freight corridor with low speeds and relaxed comfort limits | artc-hunter-valley-coal; pilbara-iron-ore-wa; qld-north-coast-freight |
| `urban_metro` | Urban metro or commuter rail with tight gradients and frequent grade transitions | sydney-metro-northwest; melbourne-metro-tunnel; brisbane-cross-river-rail |
| `branch_line` | Regional branch line with moderate gradients and mixed traffic | nsw-north-coast-line; vic-geelong-warrnambool; qld-western-line |

### Difficulty Notes

```text
easy: all_given | All parameters given, moderate gradients on mainline or freight corridors
medium: all_given | All parameters given, any corridor type including steep metro grades
hard: partial | hidden=max_vertical_acceleration_m_s2 | Vertical acceleration hidden — agent must infer from corridor type and passenger comfort requirements
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
