# ABOUTME: First-pass task-world opportunity card for vms-legibility-distance.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# electrical / vms-design / vms-legibility-distance

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/electrical/vms_legibility_distance`
- Discipline: `electrical`
- Category: `vms-design`
- Tool mode: `with-tool`
- Standards: MUTCD; NYSDOT VMS Guidelines
- Tags: electrical; vms; signage; legibility; its; deterministic

## Current Task Shape

Calculates variable message sign legibility distance from character height using a reduced 40 ft per inch rule of thumb. It converts design speed to ft/s, estimates reading time available, and reports message character capacity from an explicit reading rate.

## Existing Deterministic Contract

- Parameters: `3`
- Outputs: `4`
- Archetypes: `2`
- Visibility mix: all_given; partial
- Hidden parameters: `reading_rate_chars_s`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `character_height_in` | VMS character height | float / in | range=4..30 |
| `design_speed_mph` | Approach design speed | float / mph | range=10..85 |
| `reading_rate_chars_s` | Assumed driver reading rate | float / chars/s | range=1..6 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `minimum_legibility_distance_ft` | Minimum legibility distance |  | tolerance=0.03 |
| `design_speed_ft_s` | Design speed converted to feet per second |  | tolerance=0.01 |
| `reading_time_available_s` | Reading time available over the legibility distance |  | tolerance=0.03 |
| `message_length_limit_chars` | Message length supported by available reading time |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `urban_vms` | Urban variable message sign on a lower-speed road | urban-arterial; tunnel-approach |
| `freeway_vms` | Freeway variable message sign on a high-speed road | motorway-mainline; managed-freeway |

### Difficulty Notes

```text
easy: all_given | Urban VMS with all readability inputs visible
medium: all_given | Urban or freeway VMS
hard: partial | hidden=reading_rate_chars_s | Reading rate hidden in driver-readability context
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
