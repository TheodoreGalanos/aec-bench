# ABOUTME: First-pass task-world opportunity card for 4-20ma-scaling.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# electrical / signal-processing / 4-20ma-scaling

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/electrical/four_twenty_ma_scaling`
- Discipline: `electrical`
- Category: `signal-processing`
- Tool mode: `with-tool`
- Standards: ISA-5.1; IEC 60381
- Tags: electrical; instrumentation; 4-20ma; signal-scaling; deterministic

## Current Task Shape

Calculates the current signal for a process variable over a configured lower and upper range. The deterministic linear scaling reports percentage of span, 4-20 mA current, and reconstructed process value from the current signal for instrumentation checks.

## Existing Deterministic Contract

- Parameters: `3`
- Outputs: `3`
- Archetypes: `2`
- Visibility mix: all_given; partial
- Hidden parameters: `upper_range_value`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `process_value` | Process variable value | float | range=0..1000 |
| `lower_range_value` | Lower range value | float | range=-1000..500 |
| `upper_range_value` | Upper range value | float | range=1..2000 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `span_pct` | Percentage of configured span |  | tolerance=0.03 |
| `current_signal_ma` | Current signal |  | tolerance=0.03 |
| `reconstructed_process_value` | Process variable reconstructed from current |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `level_transmitter` | Tank level transmitter scaled in percent | pump-station; water-treatment |
| `pressure_transmitter` | Pressure transmitter scaled over a positive engineering range | process-skid; gas-metering |

### Difficulty Notes

```text
easy: all_given | Percent range scaling
medium: all_given | Engineering range scaling
hard: partial | hidden=upper_range_value | Upper range value hidden in context
```

## Multimodal Expansion

Candidate modality families: `drawing-geometry`, `tabular-source`, `spatial-map`.

Use layout plans, device schedules, coverage diagrams, timing tables, and network topology artifacts.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Communications and ITS tasks combine through shared layouts, device counts, coverage, storage, and power constraints.

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
