# ABOUTME: First-pass task-world opportunity card for gci-calculation.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# mechanical / mesh-independence / gci-calculation

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/mechanical/gci_calculation`
- Discipline: `mechanical`
- Category: `mesh-independence`
- Tool mode: `with-tool`
- Standards: ASME V&V 20-2009
- Tags: mechanical; cfd; mesh; gci; deterministic

## Current Task Shape

Calculates observed order of accuracy, Richardson extrapolated value, and fine-grid convergence index for a monotonic three-grid study with equal refinement ratio. The template uses a fixed safety factor of 1.25 and requires the three QoI values to show monotonic convergence.

## Existing Deterministic Contract

- Parameters: `4`
- Outputs: `5`
- Archetypes: `2`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `coarse_grid_value` | Quantity of interest on the coarse grid | float | range=-1000000.0..1000000.0 |
| `medium_grid_value` | Quantity of interest on the medium grid | float | range=-1000000.0..1000000.0 |
| `fine_grid_value` | Quantity of interest on the fine grid | float | range=-1000000.0..1000000.0 |
| `refinement_ratio` | Grid refinement ratio between successive grids | float | range=1.01..4.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `observed_order` | Observed order of accuracy |  | tolerance=0.03 |
| `extrapolated_value` | Richardson extrapolated fine-grid value |  | tolerance=0.03 |
| `approximate_relative_error_pct` | Approximate relative error between fine and medium grids |  | tolerance=0.03 |
| `gci_fine_pct` | Fine-grid convergence index |  | tolerance=0.03 |
| `asymptotic_range_ratio` | Asymptotic range ratio |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `drag_coefficient` | Monotonic drag coefficient mesh convergence study | cfd-drag-study; external-flow-model |
| `pressure_drop` | Monotonic pressure-drop mesh convergence study | duct-cfd-model; pipe-loss-cfd-study |

### Difficulty Notes

```text
easy: all_given | All parameters given for a drag coefficient convergence study
medium: all_given | All parameters given across convergence study types
hard: all_given | All parameters given for a pressure-drop convergence study
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
