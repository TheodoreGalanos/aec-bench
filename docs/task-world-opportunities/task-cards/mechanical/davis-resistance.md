# ABOUTME: First-pass task-world opportunity card for davis-resistance.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# mechanical / train-resistance-dynamics / davis-resistance

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/mechanical/davis_resistance`
- Discipline: `mechanical`
- Category: `train-resistance-dynamics`
- Tool mode: `with-tool`
- Standards: Davis equation
- Tags: mechanical; rail; train-resistance; tractive-power; deterministic

## Current Task Shape

Calculates train running resistance using the Davis equation with constant, speed-linear, and speed-squared coefficients. The template reports resistance per tonne, total resistance, converted speed, and the tractive power needed to overcome that resistance.

## Existing Deterministic Contract

- Parameters: `5`
- Outputs: `4`
- Archetypes: `2`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `train_mass_t` | Train mass | float / t | range=1.0..50000.0 |
| `speed_km_h` | Train speed | float / km/h | range=0.0..300.0 |
| `coefficient_a_n_t` | Davis constant resistance coefficient | float / N/t | range=0.0..100.0 |
| `coefficient_b_n_t_km_h` | Davis speed-linear resistance coefficient | float / N/t per km/h | range=0.0..5.0 |
| `coefficient_c_n_t_km_h2` | Davis speed-squared resistance coefficient | float / N/t per (km/h)^2 | range=0.0..0.2 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `speed_m_s` | Train speed in metres per second |  | tolerance=0.03 |
| `resistance_n_per_t` | Running resistance per tonne |  | tolerance=0.03 |
| `total_resistance_kn` | Total running resistance |  | tolerance=0.03 |
| `tractive_power_kw` | Tractive power to overcome running resistance |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `passenger_train` | Passenger train Davis resistance check | passenger-rail-corridor; interurban-service |
| `freight_train` | Freight train Davis resistance check | freight-rail-corridor; heavy-haul-service |

### Difficulty Notes

```text
easy: all_given | All parameters given for a passenger train
medium: all_given | All parameters given across train types
hard: all_given | All parameters given for freight train resistance
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

Candidate operation handles: `parameters`, `outputs`, `difficulty`, `archetype`, `evidence_profile`, `source_geometry`, `source_table`, `source_timeseries`.

Practical operations to consider:

- `projection`: isolate the arithmetic-only world, source-interpretation world, or evidence-review world.
- `difference`: remove visible parameters, calculator access, source labels, or intermediate hints.
- `subset`: restrict to one archetype, standard, modality, or difficulty tier.
- `product`: compose with a downstream or upstream task that consumes/produces compatible engineering quantities.

## Repair/Event Candidates

- Trigger `evidence_profile` repair if the model reaches the right number without citing or preserving the source artifact.
- Trigger `verifier` repair if final-output tolerances pass while intermediate units, assumptions, or handoff values are inconsistent.
- Trigger `world_schema` repair if a promising composition lacks explicit handoff fields or operation handles.
