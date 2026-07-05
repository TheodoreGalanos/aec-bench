# ABOUTME: First-pass task-world opportunity card for ac-resistance-temperature.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# electrical / electrical-parameters / ac-resistance-temperature

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/electrical/ac_resistance_temperature`
- Discipline: `electrical`
- Category: `electrical-parameters`
- Tool mode: `with-tool`
- Standards: IEC 60287-1-1; IEEE 738
- Tags: electrical; ac-resistance; skin-effect; temperature; transmission-lines; deterministic

## Current Task Shape

Computes the AC resistance of a power cable conductor at operating temperature by first correcting DC resistance from 20 deg C using R'(T) = R_20 * [1 + alpha_20 * (T - 20)], then applying the IEC 60287-1-1 skin effect factor ys to obtain R_ac = R_dc(T) * (1 + ys). Essential for cable thermal rating and power loss calculations in transmission and distribution systems.

## Existing Deterministic Contract

- Parameters: `4`
- Outputs: `3`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `conductor_material`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `dc_resistance_20c_ohm_per_km` | DC resistance of conductor at 20 deg C | float / ohm/km | range=0.01..5.0 |
| `conductor_material` | Conductor material | enum | values=copper, aluminium; derivable_from=archetype |
| `operating_temp_c` | Operating temperature of the conductor | float / deg C | range=20..200 |
| `frequency_hz` | System frequency | float / Hz | range=16.7..60 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `dc_resistance_at_temp_ohm_per_km` | DC resistance at operating temperature (ohm/km) |  | tolerance=0.03 |
| `skin_effect_factor` | Skin effect factor ys (dimensionless) |  | tolerance=0.05 |
| `ac_resistance_ohm_per_km` | AC resistance at operating temperature (ohm/km) |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `distribution_copper` | Copper distribution cable at moderate temperature | sydney-urban; melbourne-urban |
| `distribution_aluminium` | Aluminium distribution cable at moderate temperature | brisbane-suburban; perth-suburban |
| `transmission_copper` | Copper transmission conductor at elevated temperature | hunter-valley-transmission; latrobe-valley-transmission |
| `transmission_aluminium` | Aluminium transmission conductor at high temperature | queensland-overhead; south-australia-overhead |

### Difficulty Notes

```text
easy: all_given | Standard 50 Hz copper, moderate temperature, all params given
medium: all_given | Any material and frequency, transmission-level conductors
hard: partial | hidden=conductor_material | Conductor material hidden, agent must infer from context and resistance value
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
