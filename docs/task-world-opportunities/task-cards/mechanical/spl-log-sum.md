# ABOUTME: First-pass task-world opportunity card for spl-log-sum.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# mechanical / fundamental-calculations / spl-log-sum

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/mechanical/spl_log_sum`
- Discipline: `mechanical`
- Category: `fundamental-calculations`
- Tool mode: `with-tool`
- Standards: Acoustic Fundamentals
- Tags: mechanical; acoustics; spl; logarithmic-sum; deterministic

## Current Task Shape

Calculates combined sound pressure level from three independent source levels using logarithmic addition. The template converts each dB value to linear acoustic energy, sums the terms, and converts back to dB for deterministic acoustic fundamentals checks.

## Existing Deterministic Contract

- Parameters: `3`
- Outputs: `3`
- Archetypes: `2`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `source_1_spl_db` | Sound pressure level from source 1 | float / dB | range=20.0..130.0 |
| `source_2_spl_db` | Sound pressure level from source 2 | float / dB | range=20.0..130.0 |
| `source_3_spl_db` | Sound pressure level from source 3 | float / dB | range=20.0..130.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `total_linear_energy` | Sum of linear acoustic energy terms |  | tolerance=0.03 |
| `combined_spl_db` | Combined sound pressure level |  | tolerance=0.03 |
| `dominant_source_spl_db` | Highest individual source level |  | tolerance=0.01 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `plant_room_sources` | Three mechanical plant sources in a plant room | hospital-plant-room; commercial-rooftop-plant |
| `industrial_noise_sources` | Three industrial process noise sources | water-treatment-plant; industrial-process-building |

### Difficulty Notes

```text
easy: all_given | All parameters given for plant room sources
medium: all_given | All parameters given across plant and industrial noise sources
hard: all_given | All parameters given for higher-level industrial noise sources
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
