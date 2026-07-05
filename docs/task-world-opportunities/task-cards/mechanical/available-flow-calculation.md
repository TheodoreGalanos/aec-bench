# ABOUTME: First-pass task-world opportunity card for available-flow-calculation.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# mechanical / hydrant-flow-test / available-flow-calculation

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/mechanical/available_flow_calculation`
- Discipline: `mechanical`
- Category: `hydrant-flow-test`
- Tool mode: `with-tool`
- Standards: NFPA 291
- Tags: mechanical; fire-services; hydrant; available-flow; deterministic

## Current Task Shape

Calculates available flow at a target residual pressure from static pressure, residual pressure, and measured test flow using the standard hydrant flow extrapolation exponent. The template reports pressure drops and available flow in L/s and m3/h.

## Existing Deterministic Contract

- Parameters: `4`
- Outputs: `4`
- Archetypes: `2`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `static_pressure_kpa` | Static pressure before flow test | float / kPa | range=1.0..5000.0 |
| `residual_pressure_kpa` | Residual pressure during flow test | float / kPa | range=0.0..5000.0 |
| `test_flow_l_s` | Measured test flow | float / L/s | range=0.0..10000.0 |
| `target_residual_pressure_kpa` | Target residual pressure for available flow | float / kPa | range=0.0..5000.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `pressure_drop_test_kpa` | Pressure drop during the flow test |  | tolerance=0.03 |
| `pressure_drop_target_kpa` | Pressure drop from static to target residual |  | tolerance=0.03 |
| `available_flow_l_s` | Available flow at target residual pressure |  | tolerance=0.03 |
| `available_flow_m3_h` | Available flow in cubic metres per hour |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `urban_hydrant` | Urban hydrant available flow estimate | urban-hydrant; fire-flow-test |
| `industrial_site` | Industrial fire water available flow estimate | industrial-fire-water; hydrant-flow-test |

### Difficulty Notes

```text
easy: all_given | All parameters given for an urban hydrant
medium: all_given | All parameters given across hydrant flow tests
hard: all_given | All parameters given for industrial fire water systems
```

## Multimodal Expansion

Candidate modality families: `chart-curve`, `drawing-geometry`, `tabular-source`.

Use pump curves, system schematics, hydrant flow tests, pipe schedules, and fire-service drawings.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Hydraulic duty points can feed pump power, motor sizing, NPSH, backup power, and transient checks.

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
