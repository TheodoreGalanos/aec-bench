# ABOUTME: First-pass task-world opportunity card for sabine-rt60.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# mechanical / fundamental-calculations / sabine-rt60

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/mechanical/sabine_rt60`
- Discipline: `mechanical`
- Category: `fundamental-calculations`
- Tool mode: `with-tool`
- Standards: ISO 3382
- Tags: mechanical; acoustics; rt60; sabine; deterministic

## Current Task Shape

Calculates room reverberation time using the Sabine formula RT60 = 0.161 V / A, where A is the equivalent absorption area. The template uses explicit floor, wall, and ceiling areas and absorption coefficients for a deterministic room acoustics calculation.

## Existing Deterministic Contract

- Parameters: `7`
- Outputs: `3`
- Archetypes: `2`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `room_volume_m3` | Room volume | float / m3 | range=10.0..100000.0 |
| `floor_area_m2` | Floor surface area | float / m2 | range=5.0..10000.0 |
| `floor_absorption` | Floor absorption coefficient | float | range=0.01..1.0 |
| `wall_area_m2` | Total wall surface area | float / m2 | range=5.0..30000.0 |
| `wall_absorption` | Wall absorption coefficient | float | range=0.01..1.0 |
| `ceiling_area_m2` | Ceiling surface area | float / m2 | range=5.0..10000.0 |
| `ceiling_absorption` | Ceiling absorption coefficient | float | range=0.01..1.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `equivalent_absorption_area_m2` | Equivalent absorption area |  | tolerance=0.03 |
| `average_absorption_coefficient` | Area-weighted average absorption coefficient |  | tolerance=0.03 |
| `rt60_s` | Sabine reverberation time |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `small_meeting_room` | Small meeting room with moderate finishes | office-meeting-room; clinical-consult-room |
| `large_hall` | Large hall or concourse acoustic volume | station-concourse; school-assembly-hall |

### Difficulty Notes

```text
easy: all_given | All parameters given for a small room
medium: all_given | All parameters given across small and large acoustic rooms
hard: all_given | All parameters given for large-volume reverberation checks
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
