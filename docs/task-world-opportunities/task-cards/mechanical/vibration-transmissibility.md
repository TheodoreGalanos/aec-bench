# ABOUTME: First-pass task-world opportunity card for vibration-transmissibility.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# mechanical / vibration / vibration-transmissibility

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/mechanical/vibration_transmissibility`
- Discipline: `mechanical`
- Category: `vibration`
- Tool mode: `with-tool`
- Standards: ISO 20816
- Tags: mechanical; vibration; isolation; transmissibility; deterministic

## Current Task Shape

Calculates force transmissibility for a damped single-degree vibration isolation system from forcing frequency, natural frequency, and damping ratio. The template reports frequency ratio, transmissibility, and isolation efficiency.

## Existing Deterministic Contract

- Parameters: `3`
- Outputs: `3`
- Archetypes: `2`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `forcing_frequency_hz` | Excitation or forcing frequency | float / Hz | range=0.1..200.0 |
| `natural_frequency_hz` | Isolator natural frequency | float / Hz | range=0.1..100.0 |
| `damping_ratio` | Viscous damping ratio | float / - | range=0.0..1.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `frequency_ratio` | Ratio of forcing frequency to natural frequency |  | tolerance=0.03 |
| `transmissibility` | Damped force transmissibility |  | tolerance=0.03 |
| `isolation_efficiency_pct` | Isolation efficiency |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `pump_isolator` | Pump or fan vibration isolator | plant-room-pump; fan-isolator |
| `precision_equipment` | Precision equipment vibration isolation | laboratory-equipment; precision-machine-base |

### Difficulty Notes

```text
easy: all_given | All parameters given for a pump isolator
medium: all_given | All parameters given across isolation systems
hard: all_given | All parameters given for precision equipment isolation
```

## Multimodal Expansion

Candidate modality families: `chart-curve`, `drawing-geometry`, `tabular-source`.

Use schematics, equipment curves, schedules, commissioning tables, and source datasheets.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Compose with tasks that share the same site context, source artifact, or downstream output obligation.

First-pass composition tags: `shared-context`, `pipeline`, `evidence-assembly`.

## Meta-Harness Handles

Candidate operation handles: `parameters`, `outputs`, `difficulty`, `archetype`, `evidence_profile`, `source_geometry`, `source_table`, `source_curve`.

Practical operations to consider:

- `projection`: isolate the arithmetic-only world, source-interpretation world, or evidence-review world.
- `difference`: remove visible parameters, calculator access, source labels, or intermediate hints.
- `subset`: restrict to one archetype, standard, modality, or difficulty tier.
- `product`: compose with a downstream or upstream task that consumes/produces compatible engineering quantities.

## Repair/Event Candidates

- Trigger `evidence_profile` repair if the model reaches the right number without citing or preserving the source artifact.
- Trigger `verifier` repair if final-output tolerances pass while intermediate units, assumptions, or handoff values are inconsistent.
- Trigger `world_schema` repair if a promising composition lacks explicit handoff fields or operation handles.
