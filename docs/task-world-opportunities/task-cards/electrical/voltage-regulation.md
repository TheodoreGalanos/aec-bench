# ABOUTME: First-pass task-world opportunity card for voltage-regulation.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# electrical / electrical-parameters / voltage-regulation

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/electrical/voltage_regulation`
- Discipline: `electrical`
- Category: `electrical-parameters`
- Tool mode: `with-tool`
- Standards: IEC 60909; AS 2067
- Tags: electrical; voltage-regulation; line-drop; transmission; deterministic

## Current Task Shape

Calculates voltage drop, voltage regulation, receiving-end voltage, and real power loss for a balanced three-phase line. The reduced method uses per-kilometre R and X, line length, real and reactive load, and sending-end voltage.

## Existing Deterministic Contract

- Parameters: `6`
- Outputs: `4`
- Archetypes: `2`
- Visibility mix: all_given; partial
- Hidden parameters: `load_reactive_power_mvar`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `line_resistance_ohm_per_km` | Positive-sequence line resistance | float / ohm/km | range=0..5 |
| `line_reactance_ohm_per_km` | Positive-sequence line reactance | float / ohm/km | range=0..5 |
| `line_length_km` | Line length | float / km | range=0.1..500 |
| `load_real_power_mw` | Three-phase real load | float / MW | range=0.1..1000 |
| `load_reactive_power_mvar` | Three-phase reactive load | float / MVAr | range=-500..500 |
| `sending_voltage_kv` | Sending-end line-to-line voltage | float / kV | range=1..765 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `voltage_drop_kv` | Approximate line voltage drop |  | tolerance=0.03 |
| `voltage_regulation_pct` | Voltage drop as a percentage of sending voltage |  | tolerance=0.03 |
| `receiving_end_voltage_kv` | Receiving-end line-to-line voltage |  | tolerance=0.03 |
| `power_loss_mw` | Three-phase real power loss |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `subtransmission_line` | Subtransmission feeder supplying a regional load | regional-feeder; subtransmission-line |
| `transmission_line` | Transmission line supplying a bulk load | bulk-transmission; interconnector |

### Difficulty Notes

```text
easy: all_given | Subtransmission line with all values visible
medium: all_given | Subtransmission or transmission line
hard: partial | hidden=load_reactive_power_mvar | Reactive load hidden in power factor context
```

## Multimodal Expansion

Candidate modality families: `drawing-geometry`, `tabular-source`, `time-series`.

Use single-line diagrams, layouts, device schedules, demand profiles, and equipment datasheets.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Compose with tasks that share the same site context, source artifact, or downstream output obligation.

First-pass composition tags: `shared-context`, `pipeline`, `evidence-assembly`.

## Meta-Harness Handles

Candidate operation handles: `parameters`, `outputs`, `difficulty`, `archetype`, `evidence_profile`, `hidden_parameter_policy`, `source_geometry`, `source_table`, `source_timeseries`.

Practical operations to consider:

- `projection`: isolate the arithmetic-only world, source-interpretation world, or evidence-review world.
- `difference`: remove visible parameters, calculator access, source labels, or intermediate hints.
- `subset`: restrict to one archetype, standard, modality, or difficulty tier.
- `product`: compose with a downstream or upstream task that consumes/produces compatible engineering quantities.

## Repair/Event Candidates

- Trigger `evidence_profile` repair if the model reaches the right number without citing or preserving the source artifact.
- Trigger `verifier` repair if final-output tolerances pass while intermediate units, assumptions, or handoff values are inconsistent.
- Trigger `world_schema` repair if a promising composition lacks explicit handoff fields or operation handles.
