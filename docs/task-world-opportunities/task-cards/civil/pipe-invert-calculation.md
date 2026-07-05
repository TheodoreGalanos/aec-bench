# ABOUTME: First-pass task-world opportunity card for pipe-invert-calculation.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / stormwater-piped / pipe-invert-calculation

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/pipe_invert_calculation`
- Discipline: `civil`
- Category: `stormwater-piped`
- Tool mode: `with-tool`
- Standards: AS/NZS 3500.3; QUDM Section 7
- Tags: civil; stormwater; invert-level; drainage; cover-depth; deterministic

## Current Task Shape

Calculates the downstream invert level, obvert (crown) level, cover depth, and grade fall for a stormwater drainage pipe given upstream invert, length, grade, diameter, and downstream surface level. Checks cover adequacy against minimum requirements for the installation context per Australian local-authority stormwater drainage standards.

## Existing Deterministic Contract

- Parameters: `6`
- Outputs: `5`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `minimum_cover_mm`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `upstream_invert_m` | Upstream invert level IL_us | float / m AHD | range=0.0..500.0 |
| `pipe_length_m` | Pipe length between pits L | float / m | range=1.0..200.0 |
| `pipe_grade_percent` | Pipe longitudinal grade as a percentage | float / % | range=0.1..10.0 |
| `pipe_diameter_mm` | Nominal pipe internal diameter D | enum / mm | values=225, 300, 375, 450, 600, 750, 900 |
| `surface_level_ds_m` | Surface level at downstream pit | float / m AHD | range=0.0..500.0 |
| `minimum_cover_mm` | Minimum required cover depth over pipe crown | float / mm | range=150..1200; derivable_from=archetype |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `downstream_invert_m` | Downstream invert level IL_ds (m AHD) |  | tolerance=0.03 |
| `obvert_level_m` | Obvert (crown) level at downstream end OL_ds (m AHD) |  | tolerance=0.03 |
| `cover_depth_mm` | Cover depth at downstream end (mm) |  | tolerance=5.0 |
| `grade_fall_m` | Total fall over pipe length (m) |  | tolerance=0.03 |
| `cover_adequate` | Cover adequacy (1.0 = adequate, 0.0 = insufficient) |  | tolerance=0.01 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `suburban_road_drainage` | PVC stormwater pipe under suburban road pavement | brisbane-suburban-road-drainage; sydney-residential-road-stormwater |
| `verge_and_footpath` | PVC stormwater pipe under grass verge or footpath | perth-verge-drainage; adelaide-footpath-stormwater |
| `trunk_stormwater` | Reinforced concrete trunk stormwater main under road reserve | melbourne-trunk-stormwater; gold-coast-catchment-drainage |
| `steep_hillside` | HDPE or PVC stormwater pipe on steep hillside terrain | cairns-hillside-subdivision; hobart-steep-terrain-drainage |

### Difficulty Notes

```text
easy: all_given | Small pipe under footpath, all parameters given, generous cover
medium: all_given | Any pipe size and archetype, all parameters given
hard: partial | hidden=minimum_cover_mm | Minimum cover hidden, agent must infer from installation context
```

## Multimodal Expansion

Candidate modality families: `spatial-map`, `tabular-source`, `time-series`.

Use catchment plans, rainfall tables, hyetographs, and drainage schedules as source artifacts.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Connect rainfall/runoff outputs to detention, pipe, HGL, outlet, and water-quality checks.

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
