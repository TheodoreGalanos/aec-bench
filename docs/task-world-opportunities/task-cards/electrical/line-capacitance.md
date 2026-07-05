# ABOUTME: First-pass task-world opportunity card for line-capacitance.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# electrical / electrical-parameters / line-capacitance

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/electrical/line_capacitance`
- Discipline: `electrical`
- Category: `electrical-parameters`
- Tool mode: `with-tool`
- Standards: IEC 60909
- Tags: electrical; line-capacitance; charging; surge-impedance; transmission-lines; deterministic

## Current Task Shape

Calculates per-phase overhead line capacitance from conductor radius and geometric mean phase spacing. The reduced transposed-line method also estimates three-phase charging Mvar per 100 km and surge impedance from an explicit inductance input.

## Existing Deterministic Contract

- Parameters: `7`
- Outputs: `4`
- Archetypes: `2`
- Visibility mix: all_given; partial
- Hidden parameters: `frequency_hz`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `conductor_radius_m` | Physical conductor radius | float / m | range=0.001..0.05 |
| `phase_spacing_ab_m` | Spacing between phase A and phase B | float / m | range=0.2..30 |
| `phase_spacing_bc_m` | Spacing between phase B and phase C | float / m | range=0.2..30 |
| `phase_spacing_ca_m` | Spacing between phase C and phase A | float / m | range=0.2..50 |
| `nominal_voltage_kv` | Line-to-line nominal voltage | float / kV | range=1..765 |
| `frequency_hz` | System frequency | float / Hz | range=16.7..60 |
| `inductance_mh_per_km` | Per-phase line inductance | float / mH/km | range=0.1..3.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `geometric_mean_distance_m` | Geometric mean distance between phases |  | tolerance=0.03 |
| `capacitance_nf_per_km` | Per-phase capacitance per kilometre |  | tolerance=0.03 |
| `charging_mvar_per_100km` | Three-phase charging reactive power per 100 km |  | tolerance=0.03 |
| `surge_impedance_ohm` | Surge impedance from L and C |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `distribution_line` | Medium-voltage distribution overhead line | rural-feeder; urban-distribution |
| `transmission_line` | High-voltage transmission overhead line | 132kv-overhead; 330kv-overhead |

### Difficulty Notes

```text
easy: all_given | Distribution line with all geometry visible
medium: all_given | Distribution or transmission capacitance calculation
hard: partial | hidden=frequency_hz | Frequency hidden in system context
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
