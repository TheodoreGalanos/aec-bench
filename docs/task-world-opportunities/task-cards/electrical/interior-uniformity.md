# ABOUTME: First-pass task-world opportunity card for interior-uniformity.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# electrical / interior-lighting / interior-uniformity

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/electrical/interior_uniformity`
- Discipline: `electrical`
- Category: `interior-lighting`
- Tool mode: `with-tool`
- Standards: EN 12464-1; AS/NZS 1680
- Tags: electrical; lighting; interior-lighting; uniformity; deterministic

## Current Task Shape

Calculates task-area illuminance uniformity and adjacent-area illuminance ratios for interior workplace lighting checks.

## Existing Deterministic Contract

- Parameters: `4`
- Outputs: `3`
- Archetypes: `2`
- Visibility mix: all_given; partial
- Hidden parameters: `background_average_illuminance_lux`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `task_min_illuminance_lux` | Minimum illuminance within the task area | float / lux | range=0..2000 |
| `task_average_illuminance_lux` | Average illuminance within the task area | float / lux | range=50..3000 |
| `surround_average_illuminance_lux` | Average illuminance in the immediate surround area | float / lux | range=0..2000 |
| `background_average_illuminance_lux` | Average illuminance in the background area | float / lux | range=0..1000 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `task_uniformity_uo` | Task-area illuminance uniformity ratio |  | tolerance=0.03 |
| `surround_to_task_ratio` | Immediate surround illuminance divided by task average illuminance |  | tolerance=0.03 |
| `background_to_task_ratio` | Background illuminance divided by task average illuminance |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `office_work_area` | Office task area with surrounding circulation | office-workplace; task-lighting |
| `industrial_work_area` | Industrial task area with adjacent general lighting | industrial-workplace; task-lighting |

### Difficulty Notes

```text
easy: all_given | Office task area with all values visible
medium: all_given | Interior task area selected from office or industrial cases
hard: partial | hidden=background_average_illuminance_lux | Industrial task area with background illuminance embedded in context
```

## Multimodal Expansion

Candidate modality families: `drawing-geometry`, `tabular-source`, `spatial-map`.

Use layout plans, device schedules, coverage diagrams, timing tables, and network topology artifacts.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Communications and ITS tasks combine through shared layouts, device counts, coverage, storage, and power constraints.

First-pass composition tags: `shared-context`, `pipeline`, `evidence-assembly`.

## Meta-Harness Handles

Candidate operation handles: `parameters`, `outputs`, `difficulty`, `archetype`, `evidence_profile`, `hidden_parameter_policy`, `source_geometry`, `source_table`.

Practical operations to consider:

- `projection`: isolate the arithmetic-only world, source-interpretation world, or evidence-review world.
- `difference`: remove visible parameters, calculator access, source labels, or intermediate hints.
- `subset`: restrict to one archetype, standard, modality, or difficulty tier.
- `product`: compose with a downstream or upstream task that consumes/produces compatible engineering quantities.

## Repair/Event Candidates

- Trigger `evidence_profile` repair if the model reaches the right number without citing or preserving the source artifact.
- Trigger `verifier` repair if final-output tolerances pass while intermediate units, assumptions, or handoff values are inconsistent.
- Trigger `world_schema` repair if a promising composition lacks explicit handoff fields or operation handles.
