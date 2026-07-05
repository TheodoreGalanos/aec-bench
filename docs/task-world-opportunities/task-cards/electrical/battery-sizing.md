# ABOUTME: First-pass task-world opportunity card for battery-sizing.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# electrical / power-supply / battery-sizing

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/electrical/battery_sizing`
- Discipline: `electrical`
- Category: `power-supply`
- Tool mode: `with-tool`
- Standards: EN 50125; IEEE 485
- Tags: electrical; battery; ups; backup-power; autonomy; deterministic

## Current Task Shape

Calculates battery energy, required amp-hour capacity, UPS apparent power, and block count for a critical load autonomy requirement. The reduced method explicitly applies system voltage, depth of discharge, temperature derating, inverter efficiency, load power factor, and block voltage.

## Existing Deterministic Contract

- Parameters: `8`
- Outputs: `4`
- Archetypes: `2`
- Visibility mix: all_given; partial
- Hidden parameters: `temperature_derating_factor`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `critical_load_w` | Critical load power | float / W | range=1..100000 |
| `required_autonomy_h` | Required autonomy duration | float / h | range=0.1..168 |
| `system_voltage_v` | Nominal DC system voltage | float / V | range=12..1000 |
| `depth_of_discharge_pct` | Allowed depth of discharge | float / % | range=10..100 |
| `temperature_derating_factor` | Capacity derating factor for temperature | float | range=0.3..1.0 |
| `inverter_efficiency_pct` | Inverter or UPS efficiency | float / % | range=50..100 |
| `load_power_factor` | Load power factor for UPS VA sizing | float | range=0.5..1.0 |
| `battery_block_voltage_v` | Nominal voltage of each battery block | float / V | range=1.2..48 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `required_energy_kwh` | Critical load energy over autonomy duration |  | tolerance=0.03 |
| `required_battery_capacity_ah` | Required battery amp-hour capacity |  | tolerance=0.03 |
| `ups_rating_va` | Required UPS apparent power rating |  | tolerance=0.03 |
| `battery_block_count` | Minimum number of battery blocks in series |  | tolerance=0.01 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `signalling_backup` | Rail signalling backup battery set | signal-location; level-crossing-cabinet |
| `comms_backup` | Communications or control cabinet UPS battery set | comms-room; roadside-cabinet |

### Difficulty Notes

```text
easy: all_given | Cabinet backup battery with all factors visible
medium: all_given | Comms or signalling backup battery
hard: partial | hidden=temperature_derating_factor | Temperature derating hidden in site context
```

## Multimodal Expansion

Candidate modality families: `tabular-source`, `time-series`, `drawing-geometry`.

Use single-line diagrams, load schedules, demand profiles, equipment datasheets, and cable schedules.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Electrical sizing tasks can compose with renewable generation, storage, protection, and backup-power worlds.

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
