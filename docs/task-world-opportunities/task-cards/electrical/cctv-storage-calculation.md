# ABOUTME: First-pass task-world opportunity card for cctv-storage-calculation.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# electrical / cctv-design / cctv-storage-calculation

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/electrical/cctv_storage_calculation`
- Discipline: `electrical`
- Category: `cctv-design`
- Tool mode: `with-tool`
- Standards: IEC 62676-4
- Tags: electrical; cctv; storage; video; security; deterministic

## Current Task Shape

Calculates surveillance video storage from camera count, average bitrate, recording hours, retention period, and storage overhead. The template converts Mbps to daily gigabytes per camera, then reports usable retained storage and raw storage including overhead.

## Existing Deterministic Contract

- Parameters: `5`
- Outputs: `3`
- Archetypes: `2`
- Visibility mix: all_given; partial
- Hidden parameters: `retention_days`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `camera_count` | Number of cameras | float | range=1..1000 |
| `average_bitrate_mbps` | Average video bitrate per camera | float / Mbps | range=0.1..50 |
| `recording_hours_per_day` | Recording hours per day | float / h/day | range=1..24 |
| `retention_days` | Required retention period | float / days | range=1..365 |
| `storage_overhead_pct` | Storage overhead for RAID, filesystem, or spare capacity | float / % | range=0..100 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `daily_storage_per_camera_gb` | Daily storage per camera |  | tolerance=0.03 |
| `usable_storage_required_tb` | Usable retained storage required |  | tolerance=0.03 |
| `raw_storage_with_overhead_tb` | Raw storage after overhead allowance |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `small_site` | Small CCTV site with continuous or business-hours recording | building-security; car-park |
| `large_precinct` | Large surveillance precinct with many IP cameras | transport-hub; campus-security |

### Difficulty Notes

```text
easy: all_given | Small site storage calculation
medium: all_given | Small or large CCTV storage calculation
hard: partial | hidden=retention_days | Retention hidden in the site security context
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
