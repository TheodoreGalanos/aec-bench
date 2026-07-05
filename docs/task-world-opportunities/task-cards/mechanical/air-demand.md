# ABOUTME: First-pass task-world opportunity card for air-demand.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# mechanical / compressed-air / air-demand

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/mechanical/air_demand`
- Discipline: `mechanical`
- Category: `compressed-air`
- Tool mode: `with-tool`
- Standards: ISO 8573
- Tags: mechanical; compressed-air; demand; deterministic

## Current Task Shape

Calculates connected and simultaneous compressed air demand from explicit tool flows, quantities, and simultaneity factor. The template reports demand in L/s and m3/min.

## Existing Deterministic Contract

- Parameters: `7`
- Outputs: `4`
- Archetypes: `2`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `tool_1_flow_l_s` | Air flow for first tool group | float / L/s | range=0.0..1000.0 |
| `tool_1_quantity` | Quantity of first tool group | float / - | range=0.0..1000.0 |
| `tool_2_flow_l_s` | Air flow for second tool group | float / L/s | range=0.0..1000.0 |
| `tool_2_quantity` | Quantity of second tool group | float / - | range=0.0..1000.0 |
| `tool_3_flow_l_s` | Air flow for third tool group | float / L/s | range=0.0..1000.0 |
| `tool_3_quantity` | Quantity of third tool group | float / - | range=0.0..1000.0 |
| `simultaneity_factor` | Fraction of connected demand operating simultaneously | float / - | range=0.01..1.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `connected_demand_l_s` | Connected compressed air demand |  | tolerance=0.03 |
| `simultaneous_demand_l_s` | Simultaneous compressed air demand |  | tolerance=0.03 |
| `connected_demand_m3_min` | Connected compressed air demand in cubic metres per minute |  | tolerance=0.03 |
| `simultaneous_demand_m3_min` | Simultaneous compressed air demand in cubic metres per minute |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `workshop` | Maintenance workshop compressed air demand | maintenance-workshop; compressed-air-ring-main |
| `process_air` | Process plant compressed air demand | process-plant; instrument-air |

### Difficulty Notes

```text
easy: all_given | All parameters given for workshop air demand
medium: all_given | All parameters given across compressed air systems
hard: all_given | All parameters given for process air demand
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
