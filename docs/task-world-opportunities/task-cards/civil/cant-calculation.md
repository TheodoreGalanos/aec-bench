# ABOUTME: First-pass task-world opportunity card for cant-calculation.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / track-geometry / cant-calculation

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/cant_calculation`
- Discipline: `civil`
- Category: `track-geometry`
- Tool mode: `with-tool`
- Standards: ARTC ETS-05-00; AREMA MRE Chapter 5; FRA 49 CFR Part 213
- Tags: civil; rail; track-geometry; cant; superelevation; curves; deterministic

## Current Task Shape

Computes equilibrium cant, cant deficiency, and maximum allowable speed for curved railway track sections using the ARTC ETS-05-00 / AREMA formula E_eq = C * V^2 / R. Supports both standard and narrow gauge constants, and is used in track geometry design to balance passenger comfort against derailment risk on curves.

## Existing Deterministic Contract

- Parameters: `5`
- Outputs: `3`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `actual_cant_mm`, `max_cant_deficiency_mm`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `design_speed_km_h` | Design operating speed V | float / km/h | range=20..250 |
| `curve_radius_m` | Horizontal curve radius R | float / m | range=150..5000 |
| `actual_cant_mm` | Applied (actual) cant E_a | float / mm | range=0..150; derivable_from=archetype |
| `max_cant_deficiency_mm` | Maximum allowable cant deficiency C_d_max | float / mm | range=50..110; derivable_from=archetype |
| `gauge_type` | Track gauge classification | enum | values=standard, narrow |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `equilibrium_cant_mm` | Equilibrium cant E_eq (mm) |  | tolerance=0.03 |
| `cant_deficiency_mm` | Cant deficiency C_d = E_eq - E_a (mm) |  | tolerance=0.03 |
| `maximum_speed_km_h` | Maximum allowable speed V_max (km/h) |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `urban_metro` | Urban metro or light rail line with tight curves and frequent stops | sydney-metro-northwest; melbourne-metro-tunnel; brisbane-cross-river-rail |
| `mainline_freight` | Mainline freight corridor with gentle curves and heavy axle loads | artc-hunter-valley-coal; artc-north-south-corridor; pilbara-iron-ore-wa |
| `high_speed_passenger` | High-speed passenger rail corridor with sweeping curves | sydney-melbourne-hsr; brisbane-gold-coast-fast-rail; perth-bunbury-fast-rail |
| `branch_line` | Regional branch line with moderate curves and mixed traffic | nsw-north-coast-line; vic-geelong-warrnambool; qld-western-line |

### Difficulty Notes

```text
easy: all_given | All parameters given, gentle curves on mainline or branch
medium: all_given | All parameters given, any corridor type including tight metro curves and high speed
hard: partial | hidden=actual_cant_mm, max_cant_deficiency_mm | Actual cant and max deficiency hidden — agent must infer from corridor type and operating context
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
