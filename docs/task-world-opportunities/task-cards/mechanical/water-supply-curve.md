# ABOUTME: First-pass task-world opportunity card for water-supply-curve.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# mechanical / hydrant-flow-test / water-supply-curve

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/mechanical/water_supply_curve`
- Discipline: `mechanical`
- Category: `hydrant-flow-test`
- Tool mode: `with-tool`
- Standards: NFPA 291; NFPA 13
- Tags: mechanical; fire-services; hydrant; water-supply; deterministic

## Current Task Shape

Develops a hydrant water supply curve from static pressure, residual pressure, and measured test flow using the standard 0.54 flow-test exponent. The template reports the curve coefficient, target residual flow, and available flow at 20 psi.

## Existing Deterministic Contract

- Parameters: `4`
- Outputs: `4`
- Archetypes: `2`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `static_pressure_psi` | Static pressure before flow test | float / psi | range=1.0..300.0 |
| `residual_pressure_psi` | Residual pressure during flow test | float / psi | range=0.0..250.0 |
| `test_flow_gpm` | Measured test flow | float / gpm | range=1.0..20000.0 |
| `target_residual_pressure_psi` | Target residual pressure | float / psi | range=0.0..250.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `pressure_drop_test_psi` | Pressure drop during the flow test |  | tolerance=0.03 |
| `curve_coefficient` | Water supply curve coefficient |  | tolerance=0.03 |
| `flow_at_target_residual_gpm` | Flow at the target residual pressure |  | tolerance=0.03 |
| `available_flow_20psi_gpm` | Available flow at 20 psi residual pressure |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `municipal_hydrant` | Municipal hydrant water supply curve | municipal-hydrant; street-main-flow-test |
| `industrial_fire_main` | Industrial fire-main water supply curve | industrial-fire-main; site-hydrant-flow-test |

### Difficulty Notes

```text
easy: all_given | All parameters given for a municipal hydrant
medium: all_given | All parameters given across hydrant supply curves
hard: all_given | All parameters given for an industrial fire main
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

Candidate operation handles: `parameters`, `outputs`, `difficulty`, `archetype`, `evidence_profile`, `source_geometry`, `source_table`.

Practical operations to consider:

- `projection`: isolate the arithmetic-only world, source-interpretation world, or evidence-review world.
- `difference`: remove visible parameters, calculator access, source labels, or intermediate hints.
- `subset`: restrict to one archetype, standard, modality, or difficulty tier.
- `product`: compose with a downstream or upstream task that consumes/produces compatible engineering quantities.

## Repair/Event Candidates

- Trigger `evidence_profile` repair if the model reaches the right number without citing or preserving the source artifact.
- Trigger `verifier` repair if final-output tolerances pass while intermediate units, assumptions, or handoff values are inconsistent.
- Trigger `world_schema` repair if a promising composition lacks explicit handoff fields or operation handles.
