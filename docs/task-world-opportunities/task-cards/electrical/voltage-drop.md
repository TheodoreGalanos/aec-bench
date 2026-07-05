# ABOUTME: First-pass task-world opportunity card for voltage-drop.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# electrical / cable-sizing / voltage-drop

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/electrical/voltage_drop`
- Discipline: `electrical`
- Category: `cable-sizing`
- Tool mode: `with-tool`
- Standards: AS/NZS 3008.1.1; AS/NZS 3000:2018; IEC 60364-5-52
- Tags: electrical; voltage-drop; cable-sizing; deterministic

## Current Task Shape

Calculates voltage drop along a cable run using tabulated mV/A/m values from AS/NZS 3008.1.1 for copper and aluminium multicore cables, adjusted for power factor and circuit type. Checks compliance against the AS/NZS 3000 five-percent limit to verify that voltage at the load stays within acceptable limits for equipment operation.

## Existing Deterministic Contract

- Parameters: `6`
- Outputs: `4`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `conductor_material`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `cable_size_mm2` | Cable conductor cross-sectional area | enum / mm² | values=1.5, 2.5, 4, 6, 10, 16, 25, 35, 50, 70, 95, 120, 150, 185, 240 |
| `length_m` | Cable route length (one way) | float / m | range=1..500 |
| `load_current_a` | Design load current | float / A | range=0.5..500 |
| `power_factor` | Load power factor | float | range=0.5..1.0 |
| `conductor_material` | Conductor material | enum | values=copper, aluminium; derivable_from=archetype |
| `circuit_type` | Circuit type | enum | values=single_phase, three_phase |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `vc_mv_per_a_m` | Effective voltage drop rate Vc (mV/A/m) |  | tolerance=0.03 |
| `voltage_drop_v` | Total voltage drop (V) |  | tolerance=0.03 |
| `voltage_drop_percent` | Voltage drop as percentage of supply voltage (%) |  | tolerance=0.03 |
| `compliant` | Compliance with 5% limit (1.0 = pass, 0.0 = fail) |  | tolerance=0.01 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `residential_lighting` | Residential lighting circuit | sydney-suburban; melbourne-suburban |
| `residential_power` | Residential power outlet circuit | sydney-suburban; brisbane-suburban |
| `commercial_submain` | Commercial building submain with copper conductors | sydney-cbd; melbourne-cbd |
| `industrial_feeder` | Industrial feeder cable with aluminium conductors | hunter-valley-industrial; perth-industrial |

### Difficulty Notes

```text
easy: all_given | Single phase copper, standard residential sizes, all params given
medium: all_given | Any circuit type and material, commercial/industrial sizes
hard: partial | hidden=conductor_material | Conductor material hidden, agent must infer from installation context
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
