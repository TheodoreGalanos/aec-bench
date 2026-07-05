# ABOUTME: First-pass task-world opportunity card for three-phase-fault-current.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# electrical / short-circuit / three-phase-fault-current

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/electrical/three_phase_fault_current`
- Discipline: `electrical`
- Category: `short-circuit`
- Tool mode: `with-tool`
- Standards: IEC 60909-0:2016; AS 3851
- Tags: electrical; short-circuit; fault-current; iec-60909; deterministic

## Current Task Shape

Computes initial symmetrical (Ik'') and peak (ip) short-circuit currents for a radial network using the IEC 60909-0 simplified method. Sums source, transformer, and cable impedances in series referred to the system voltage level, then applies the voltage factor c and peak factor kappa to determine fault currents for switchgear rating and protection coordination.

## Existing Deterministic Contract

- Parameters: `8`
- Outputs: `6`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `voltage_factor_c`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `system_voltage_kv` | Nominal system voltage at the fault location | float / kV | range=0.4..33.0 |
| `source_fault_level_mva` | Upstream source fault level (short-circuit power) | float / MVA | range=50..2000 |
| `transformer_rated_power_mva` | Transformer rated apparent power | float / MVA | range=0.1..100 |
| `transformer_impedance_percent` | Transformer short-circuit impedance (uk%) | float / % | range=4.0..12.0 |
| `cable_resistance_ohm_per_km` | Cable resistance per unit length | float / ohm/km | range=0.05..1.5 |
| `cable_reactance_ohm_per_km` | Cable reactance per unit length | float / ohm/km | range=0.06..0.15 |
| `cable_length_m` | Cable route length from transformer to fault point | float / m | range=5..500 |
| `voltage_factor_c` | IEC 60909 voltage factor c for maximum fault current | float | range=1.0..1.1; derivable_from=archetype |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `source_impedance_ohm` | Source impedance referred to system voltage (ohm) |  | tolerance=0.03 |
| `transformer_impedance_ohm` | Transformer impedance referred to system voltage (ohm) |  | tolerance=0.03 |
| `cable_impedance_ohm` | Cable impedance magnitude (ohm) |  | tolerance=0.03 |
| `total_impedance_ohm` | Total short-circuit impedance at fault point (ohm) |  | tolerance=0.03 |
| `initial_symmetrical_current_ka` | Initial symmetrical short-circuit current Ik'' (kA) |  | tolerance=0.03 |
| `peak_current_ka` | Peak short-circuit current ip (kA) |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `lv_commercial` | Low-voltage commercial distribution board | sydney-commercial; melbourne-commercial |
| `lv_industrial` | Low-voltage industrial motor control centre | hunter-valley-industrial; gladstone-industrial |
| `mv_distribution` | Medium-voltage distribution switchboard | perth-substation; brisbane-substation |
| `mv_heavy_industrial` | Medium-voltage heavy industrial switchgear | pilbara-mining; bowen-basin-mining |

### Difficulty Notes

```text
easy: all_given | LV system, short cable, all parameters given including voltage factor
medium: all_given | Any voltage level and archetype, all parameters given
hard: partial | hidden=voltage_factor_c | Voltage factor hidden, agent must determine c from IEC 60909 Table 1
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
