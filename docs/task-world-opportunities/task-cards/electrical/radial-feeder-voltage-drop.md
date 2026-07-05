# ABOUTME: First-pass task-world opportunity card for radial-feeder-voltage-drop.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# electrical / load-flow / radial-feeder-voltage-drop

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/electrical/radial_feeder_voltage_drop`
- Discipline: `electrical`
- Category: `load-flow`
- Tool mode: `with-tool`
- Standards: IEEE 3002.2; AS/NZS 3008.1
- Tags: electrical; radial-feeder; voltage-drop; distribution; deterministic

## Current Task Shape

Calculates current, voltage drop, receiving voltage, and real losses for a balanced single-section radial feeder. The reduced method uses feeder R and X over the route length, load kW and kVAr, and source line-to-line voltage.

## Existing Deterministic Contract

- Parameters: `6`
- Outputs: `5`
- Archetypes: `2`
- Visibility mix: all_given; partial
- Hidden parameters: `load_reactive_power_kvar`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `feeder_resistance_ohm_per_km` | Feeder resistance per kilometre | float / ohm/km | range=0..5 |
| `feeder_reactance_ohm_per_km` | Feeder reactance per kilometre | float / ohm/km | range=0..5 |
| `feeder_length_km` | Feeder route length | float / km | range=0.01..100 |
| `load_real_power_kw` | Three-phase real load | float / kW | range=1..50000 |
| `load_reactive_power_kvar` | Three-phase reactive load | float / kVAr | range=-20000..20000 |
| `source_voltage_v` | Source line-to-line voltage | float / V | range=100..132000 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `feeder_current_a` | Three-phase feeder current |  | tolerance=0.03 |
| `voltage_drop_v` | Line-to-line feeder voltage drop |  | tolerance=0.03 |
| `voltage_drop_pct` | Voltage drop percentage |  | tolerance=0.03 |
| `receiving_end_voltage_v` | Receiving-end line-to-line voltage |  | tolerance=0.03 |
| `feeder_loss_kw` | Three-phase real feeder loss |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `lv_feeder` | Low-voltage radial distribution feeder | industrial-lv-feeder; campus-switchboard |
| `mv_feeder` | Medium-voltage radial distribution feeder | rural-mv-feeder; mine-site-feeder |

### Difficulty Notes

```text
easy: all_given | Low-voltage feeder with all values visible
medium: all_given | Low-voltage or medium-voltage feeder
hard: partial | hidden=load_reactive_power_kvar | Reactive load hidden in feeder context
```

## Multimodal Expansion

Candidate modality families: `drawing-geometry`, `tabular-source`, `document-evidence`.

Use building elevations, terrain/zone diagrams, load schedules, and standards extracts.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Wind-speed and pressure derivations can feed structural member, bracket, cladding, and foundation checks.

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
