# ABOUTME: First-pass task-world opportunity card for a-weighting.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# mechanical / fundamental-calculations / a-weighting

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/mechanical/a_weighting`
- Discipline: `mechanical`
- Category: `fundamental-calculations`
- Tool mode: `with-tool`
- Standards: IEC 61672
- Tags: mechanical; acoustics; a-weighting; log-sum; deterministic

## Current Task Shape

Calculates total unweighted and A-weighted sound pressure level from eight octave-band levels using fixed A-weighting corrections. The template makes the band corrections explicit so the task remains a deterministic logarithmic summation rather than a standards lookup exercise.

## Existing Deterministic Contract

- Parameters: `8`
- Outputs: `3`
- Archetypes: `2`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `level_31_5_hz_db` | 31.5 Hz octave-band level | float / dB | range=0.0..140.0 |
| `level_63_hz_db` | 63 Hz octave-band level | float / dB | range=0.0..140.0 |
| `level_125_hz_db` | 125 Hz octave-band level | float / dB | range=0.0..140.0 |
| `level_250_hz_db` | 250 Hz octave-band level | float / dB | range=0.0..140.0 |
| `level_500_hz_db` | 500 Hz octave-band level | float / dB | range=0.0..140.0 |
| `level_1000_hz_db` | 1000 Hz octave-band level | float / dB | range=0.0..140.0 |
| `level_2000_hz_db` | 2000 Hz octave-band level | float / dB | range=0.0..140.0 |
| `level_4000_hz_db` | 4000 Hz octave-band level | float / dB | range=0.0..140.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `total_linear_level_db` | Logarithmic sum of unweighted octave-band levels |  | tolerance=0.03 |
| `a_weighted_total_dba` | Logarithmic sum after A-weighting corrections |  | tolerance=0.03 |
| `a_weighting_adjustment_db` | Difference between A-weighted and unweighted total levels |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `plant_room_noise` | Plant room octave-band noise spectrum | plant-room; mechanical-services-noise |
| `environmental_noise` | Environmental octave-band noise spectrum | environmental-noise; boundary-noise-assessment |

### Difficulty Notes

```text
easy: all_given | All octave bands given for plant-room noise
medium: all_given | All octave bands given across acoustic contexts
hard: all_given | All octave bands given for environmental noise
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
