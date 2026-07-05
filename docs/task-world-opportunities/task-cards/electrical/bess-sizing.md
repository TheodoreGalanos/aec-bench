# ABOUTME: First-pass task-world opportunity card for bess-sizing.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# electrical / bess-design / bess-sizing

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/electrical/bess_sizing`
- Discipline: `electrical`
- Category: `bess-design`
- Tool mode: `with-tool`
- Standards: IEC 62933; IEEE 2030.2.1
- Tags: electrical; bess; battery; energy-storage; sizing; capacity

## Current Task Shape

Determines the beginning-of-life installed capacity for a battery energy storage system using E_bol = (P * t) / (DoD * eta_rt * (1 - degradation)), accounting for depth of discharge, round-trip efficiency, and end-of-life degradation. Supports grid-scale peaking, renewable firming, and microgrid applications per IEC 62933 methodology.

## Existing Deterministic Contract

- Parameters: `5`
- Outputs: `4`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `depth_of_discharge_pct`, `round_trip_efficiency_pct`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `power_requirement_mw` | Required discharge power (peak demand to be served) | float / MW | range=0.5..500 |
| `discharge_duration_hours` | Required discharge duration at rated power | float / h | range=0.5..12 |
| `depth_of_discharge_pct` | Allowable depth of discharge (usable SOC range) | float / % | range=50..95; derivable_from=archetype |
| `round_trip_efficiency_pct` | AC-to-AC round-trip efficiency of the BESS | float / % | range=80..96; derivable_from=archetype |
| `degradation_allowance_pct` | End-of-life capacity degradation allowance | float / % | range=5..30 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `nominal_power_mw` | Nominal power rating of the BESS (MW) |  | tolerance=0.01 |
| `required_energy_mwh` | Required energy capacity (MWh) |  | tolerance=0.03 |
| `bol_capacity_mwh` | Beginning-of-life installed capacity (MWh) |  | tolerance=0.03 |
| `usable_energy_mwh` | Usable energy at BOL after DoD and efficiency (MWh) |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `grid_peaking` | Grid-scale peaking and load-shifting BESS | hunter-valley-grid; latrobe-valley-grid; pilbara-grid |
| `renewable_firming` | Renewable energy firming and smoothing BESS | north-queensland-solar-farm; south-australia-wind-farm; western-nsw-solar-farm |
| `commercial_demand` | Commercial behind-the-meter demand management BESS | sydney-cbd-commercial; melbourne-cbd-commercial; brisbane-commercial |
| `microgrid_island` | Remote microgrid or island BESS for energy autonomy | torres-strait-island; coober-pedy-microgrid; king-island-microgrid |

### Difficulty Notes

```text
easy: all_given | Commercial scale, all parameters given, moderate DoD and efficiency
medium: all_given | Any application scale, all parameters given, full parameter ranges
hard: partial | hidden=depth_of_discharge_pct, round_trip_efficiency_pct | DoD and efficiency hidden, agent must infer from battery chemistry and application context
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
