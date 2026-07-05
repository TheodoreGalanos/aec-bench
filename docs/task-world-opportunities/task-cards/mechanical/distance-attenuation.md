# ABOUTME: First-pass task-world opportunity card for distance-attenuation.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# mechanical / fundamental-calculations / distance-attenuation

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/mechanical/distance_attenuation`
- Discipline: `mechanical`
- Category: `fundamental-calculations`
- Tool mode: `with-tool`
- Standards: ISO 9613-2
- Tags: mechanical; acoustics; sound-pressure-level; distance-attenuation; deterministic

## Current Task Shape

Calculates the free-field sound pressure level at a target distance from a known reference level and distance. The template uses inverse-square geometric spreading, expressed as L2 = L1 - 20 log10(r2/r1), for deterministic first-pass acoustic propagation checks.

## Existing Deterministic Contract

- Parameters: `3`
- Outputs: `3`
- Archetypes: `3`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `reference_spl_db` | Sound pressure level at the reference distance | float / dB | range=40.0..130.0 |
| `reference_distance_m` | Reference distance from the point source | float / m | range=0.5..50.0 |
| `target_distance_m` | Target distance from the point source | float / m | range=1.0..500.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `distance_ratio` | Distance ratio r2/r1 |  | tolerance=0.03 |
| `attenuation_db` | Geometric spreading attenuation |  | tolerance=0.03 |
| `target_spl_db` | Sound pressure level at the target distance |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `plant_room_equipment` | Mechanical plant item assessed at occupied-area setback | hospital-plant-room; commercial-rooftop-plant |
| `industrial_fan` | Industrial fan or blower assessed at site boundary | water-treatment-plant; industrial-process-building |
| `construction_noise` | Temporary construction equipment assessed at a receiver | urban-construction-site; rail-corridor-works |

### Difficulty Notes

```text
easy: all_given | All parameters given for nearby plant equipment
medium: all_given | All parameters given across plant and industrial noise scenarios
hard: all_given | All parameters given for longer-distance environmental noise checks
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
