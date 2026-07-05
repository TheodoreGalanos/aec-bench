# ABOUTME: First-pass task-world opportunity card for bess-sizing-basic.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# electrical / bess-design / bess-sizing-basic

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/electrical/bess_sizing_basic`
- Discipline: `electrical`
- Category: `bess-design`
- Tool mode: `with-tool`
- Standards: IEC 62933; IEEE 2030.2.1
- Tags: electrical; bess; storage; energy; capacity; deterministic

## Current Task Shape

Calculates a reduced battery energy storage sizing case from a required discharge duty. The template sizes usable energy, nominal energy capacity, and beginning-of-life capacity using explicit SOC window, efficiency, and end-of-life retention factors.

## Existing Deterministic Contract

- Parameters: `5`
- Outputs: `4`
- Archetypes: `2`
- Visibility mix: all_given; partial
- Hidden parameters: `end_of_life_capacity_retention_pct`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `required_discharge_power_mw` | Required AC discharge power | float / MW | range=0.1..500 |
| `required_discharge_duration_h` | Required discharge duration | float / h | range=0.25..12 |
| `usable_soc_range_pct` | Usable state-of-charge range | float / % | range=40..95 |
| `round_trip_efficiency_pct` | Round-trip efficiency used in reduced sizing | float / % | range=70..98 |
| `end_of_life_capacity_retention_pct` | End-of-life capacity retention allowance | float / % | range=60..95 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `nominal_power_rating_mw` | Nominal power rating |  | tolerance=0.03 |
| `usable_energy_mwh` | Required delivered usable energy |  | tolerance=0.03 |
| `nominal_energy_capacity_mwh` | Nominal energy capacity before EOL retention allowance |  | tolerance=0.03 |
| `beginning_of_life_capacity_mwh` | Beginning-of-life installed energy capacity |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `distribution_peak_shaving` | Distribution peak shaving BESS | distribution-network; peak-shaving |
| `grid_firming` | Grid firming BESS | renewable-firming; grid-storage |

### Difficulty Notes

```text
easy: all_given | Distribution BESS with all values visible
medium: all_given | Storage duty selected from distribution or grid firming cases
hard: partial | hidden=end_of_life_capacity_retention_pct | Grid firming BESS with EOL retention embedded in context
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
