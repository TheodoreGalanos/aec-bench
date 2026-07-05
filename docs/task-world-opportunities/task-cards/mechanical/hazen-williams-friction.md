# ABOUTME: First-pass task-world opportunity card for hazen-williams-friction.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# mechanical / pipe-hydraulics / hazen-williams-friction

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/mechanical/hazen_williams_friction`
- Discipline: `mechanical`
- Category: `pipe-hydraulics`
- Tool mode: `with-tool`
- Standards: Hazen-Williams
- Tags: mechanical; hydraulics; pipe; friction; deterministic

## Current Task Shape

Calculates head loss and equivalent pressure loss for pressurised water flow using the Hazen-Williams equation. The template converts flow and diameter to SI units, reports hydraulic gradient, and supports water distribution and fire-service pipe checks.

## Existing Deterministic Contract

- Parameters: `5`
- Outputs: `4`
- Archetypes: `2`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `pipe_length_m` | Pipe length | float / m | range=0.1..10000.0 |
| `pipe_internal_diameter_mm` | Internal pipe diameter | float / mm | range=10.0..3000.0 |
| `flow_rate_l_s` | Volumetric flow rate | float / L/s | range=0.01..10000.0 |
| `hazen_williams_c` | Hazen-Williams roughness coefficient | float | range=40.0..160.0 |
| `fluid_density_kg_m3` | Fluid density | float / kg/m3 | range=900.0..1200.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `flow_rate_m3_s` | Flow rate in cubic metres per second |  | tolerance=0.03 |
| `head_loss_m` | Friction head loss |  | tolerance=0.03 |
| `pressure_loss_kpa` | Equivalent pressure loss |  | tolerance=0.03 |
| `hydraulic_gradient_m_per_m` | Hydraulic gradient |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `distribution_main` | Water distribution main friction loss | water-distribution-main; trunk-main |
| `fire_service` | Fire-service pipe friction loss | fire-service-pipe; hydrant-feed |

### Difficulty Notes

```text
easy: all_given | All parameters given for a distribution main
medium: all_given | All parameters given across water pipe contexts
hard: all_given | All parameters given for fire-service pipework
```

## Multimodal Expansion

Candidate modality families: `drawing-geometry`, `tabular-source`, `chart-curve`.

Use network schematics, long sections, asset schedules, rating curves, and source tables.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Pipe and channel outputs naturally feed pump station, detention, outfall, and flood-level checks.

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
