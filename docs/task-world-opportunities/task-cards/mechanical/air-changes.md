# ABOUTME: First-pass task-world opportunity card for air-changes.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# mechanical / ventilation / air-changes

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/mechanical/air_changes`
- Discipline: `mechanical`
- Category: `ventilation`
- Tool mode: `with-tool`
- Standards: ASHRAE 62.1
- Tags: mechanical; ventilation; air-changes; ach; deterministic

## Current Task Shape

Calculates room air changes per hour from supplied ventilation airflow and room volume. The template provides a deterministic closed-form ventilation rate check using ACH = supply airflow / room volume.

## Existing Deterministic Contract

- Parameters: `2`
- Outputs: `1`
- Archetypes: `2`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `supply_airflow_m3_h` | Supply ventilation airflow rate | float / m3/h | range=10.0..200000.0 |
| `room_volume_m3` | Room air volume | float / m3 | range=5.0..100000.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `air_changes_per_h` | Air changes per hour |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `small_plant_room` | Small mechanical or electrical plant room ventilation check | mechanical-plant-room; electrical-switchroom |
| `large_process_space` | Large process or utility space with dilution ventilation | water-treatment-process-hall; industrial-utility-building |

### Difficulty Notes

```text
easy: all_given | All parameters given for a small ventilated room
medium: all_given | All parameters given across small and large ventilated spaces
hard: all_given | All parameters given for larger process ventilation checks
```

## Multimodal Expansion

Candidate modality families: `drawing-geometry`, `time-series`, `document-evidence`.

Use floor plans, zone schedules, smoke/temperature traces, occupant profiles, and scenario briefs.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Fire scenarios can combine egress, tenability, ventilation, sprinkler, and hydrant-flow worlds.

First-pass composition tags: `shared-context`, `pipeline`, `evidence-assembly`.

## Meta-Harness Handles

Candidate operation handles: `parameters`, `outputs`, `difficulty`, `archetype`, `evidence_profile`, `source_geometry`, `source_timeseries`.

Practical operations to consider:

- `projection`: isolate the arithmetic-only world, source-interpretation world, or evidence-review world.
- `difference`: remove visible parameters, calculator access, source labels, or intermediate hints.
- `subset`: restrict to one archetype, standard, modality, or difficulty tier.
- `product`: compose with a downstream or upstream task that consumes/produces compatible engineering quantities.

## Repair/Event Candidates

- Trigger `evidence_profile` repair if the model reaches the right number without citing or preserving the source artifact.
- Trigger `verifier` repair if final-output tolerances pass while intermediate units, assumptions, or handoff values are inconsistent.
- Trigger `world_schema` repair if a promising composition lacks explicit handoff fields or operation handles.
