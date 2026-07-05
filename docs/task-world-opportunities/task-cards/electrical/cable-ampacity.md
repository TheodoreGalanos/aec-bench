# ABOUTME: First-pass task-world opportunity card for cable-ampacity.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# electrical / cable-sizing / cable-ampacity

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/electrical/cable_ampacity`
- Discipline: `electrical`
- Category: `cable-sizing`
- Tool mode: `with-tool`
- Standards: AS/NZS 3008.1.1; IEC 60287; IEC 60364-5-52
- Tags: electrical; cable-ampacity; derating; cable-sizing; deterministic

## Current Task Shape

Computes the derated current-carrying capacity of power cables by applying temperature and grouping correction factors to tabulated base ampacity values: I_derated = I_base * Ct * Cg, where Ct = sqrt((T_max - T_amb) / (T_max - T_ref)). Covers XLPE and PVC insulation across buried, tray, conduit, and air installations per AS/NZS 3008.1.1 and IEC 60287.

## Existing Deterministic Contract

- Parameters: `6`
- Outputs: `4`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `installation_method`, `insulation_type`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `conductor_size_mm2` | Cable conductor cross-sectional area | enum / mm² | values=1.5, 2.5, 4, 6, 10, 16, 25, 35, 50, 70, 95, 120, 150, 185, 240 |
| `insulation_type` | Cable insulation material | enum | values=XLPE, PVC; derivable_from=archetype |
| `installation_method` | Cable installation method | enum | values=buried, in-tray, in-conduit, in-air; derivable_from=archetype |
| `ambient_temp_c` | Ambient temperature at the cable location | float / °C | range=10..60 |
| `max_conductor_temp_c` | Maximum allowable conductor temperature for the insulation type | float / °C | range=60..90 |
| `grouping_circuits` | Number of circuits grouped together | int / circuits | range=1..12 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `base_ampacity_a` | Base current-carrying capacity from tables (A) |  | tolerance=0.03 |
| `temp_derating_factor` | Temperature derating factor Ct |  | tolerance=0.03 |
| `grouping_derating_factor` | Grouping derating factor Cg |  | tolerance=0.03 |
| `derated_ampacity_a` | Final derated cable ampacity (A) |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `residential_circuit` | Residential wiring circuit in temperate climate | sydney-suburban; melbourne-suburban; adelaide-suburban |
| `commercial_building` | Commercial building distribution circuit using XLPE cables on cable tray | sydney-cbd; melbourne-cbd; brisbane-cbd |
| `industrial_plant` | Industrial plant feeder cable in warm environment using PVC cables in underground conduit | hunter-valley-industrial; perth-industrial; gladstone-industrial |
| `underground_distribution` | Underground cable installation in direct-buried duct | darwin-tropical; cairns-tropical; townsville-coastal |

### Difficulty Notes

```text
easy: all_given | Single circuit with standard ambient temperature, all params given
medium: all_given | Multiple circuits with various installation methods, all params given
hard: partial | hidden=insulation_type, installation_method | Installation method and insulation type hidden; agent must infer from context
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
