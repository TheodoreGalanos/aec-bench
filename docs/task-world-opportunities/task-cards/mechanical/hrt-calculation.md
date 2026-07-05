# ABOUTME: First-pass task-world opportunity card for hrt-calculation.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# mechanical / fundamental-calculations / hrt-calculation

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/mechanical/hrt_calculation`
- Discipline: `mechanical`
- Category: `fundamental-calculations`
- Tool mode: `with-tool`
- Standards: WEF MOP 8
- Tags: mechanical; water-treatment; wastewater; hrt; deterministic

## Current Task Shape

Calculates hydraulic retention time from treatment volume and flow rate using HRT = V/Q. The template reports retention time in days and hours plus the hourly flow rate, providing a deterministic first-pass wastewater and water treatment sizing calculation.

## Existing Deterministic Contract

- Parameters: `2`
- Outputs: `3`
- Archetypes: `2`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `reactor_volume_m3` | Treatment reactor or tank volume | float / m3 | range=1.0..200000.0 |
| `flow_rate_m3_d` | Average flow rate through the treatment unit | float / m3/d | range=1.0..1000000.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `hrt_days` | Hydraulic retention time in days |  | tolerance=0.03 |
| `hrt_hours` | Hydraulic retention time in hours |  | tolerance=0.03 |
| `flow_rate_m3_h` | Flow rate in cubic metres per hour |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `package_treatment_unit` | Small package treatment unit | remote-community-wwtp; industrial-package-plant |
| `municipal_basin` | Municipal treatment basin | regional-wwtp; water-treatment-clarifier |

### Difficulty Notes

```text
easy: all_given | All parameters given for a small treatment unit
medium: all_given | All parameters given across package and municipal units
hard: all_given | All parameters given for larger treatment basins
```

## Multimodal Expansion

Candidate modality families: `drawing-geometry`, `tabular-source`, `chart-curve`.

Use network schematics, long sections, asset schedules, rating curves, and source tables.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Pipe and channel outputs naturally feed pump station, detention, outfall, and flood-level checks.

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
