# ABOUTME: First-pass task-world opportunity card for mass-balance.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# mechanical / convergence-assessment / mass-balance

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/mechanical/mass_balance`
- Discipline: `mechanical`
- Category: `convergence-assessment`
- Tool mode: `with-tool`
- Standards: ISO 15926
- Tags: mechanical; process; mass-balance; closure; deterministic

## Current Task Shape

Calculates global mass balance closure from two inlet and two outlet streams using an explicit closure tolerance. The template reports total inlet, total outlet, imbalance, closure error percentage, and a numeric closure flag.

## Existing Deterministic Contract

- Parameters: `5`
- Outputs: `5`
- Archetypes: `2`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `inlet_1_kg_h` | First inlet mass flow | float / kg/h | range=0.0..100000000.0 |
| `inlet_2_kg_h` | Second inlet mass flow | float / kg/h | range=0.0..100000000.0 |
| `outlet_1_kg_h` | First outlet mass flow | float / kg/h | range=0.0..100000000.0 |
| `outlet_2_kg_h` | Second outlet mass flow | float / kg/h | range=0.0..100000000.0 |
| `closure_tolerance_pct` | Allowed absolute closure error percentage | float / % | range=0.0..20.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `total_inlet_kg_h` | Total inlet mass flow |  | tolerance=0.03 |
| `total_outlet_kg_h` | Total outlet mass flow |  | tolerance=0.03 |
| `imbalance_kg_h` | Mass imbalance, positive when inlet exceeds outlet |  | tolerance=0.03 |
| `closure_error_pct` | Absolute closure error percentage |  | tolerance=0.03 |
| `closure_satisfied` | Numeric flag where 1 means closure is within tolerance |  | tolerance=0.01 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `process_unit` | Industrial process unit mass balance | process-unit; steady-state-model |
| `treatment_train` | Water or wastewater treatment train mass balance | treatment-train; process-simulation |

### Difficulty Notes

```text
easy: all_given | All parameters given for a process unit
medium: all_given | All parameters given across process balance settings
hard: all_given | All parameters given for treatment train balances
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
