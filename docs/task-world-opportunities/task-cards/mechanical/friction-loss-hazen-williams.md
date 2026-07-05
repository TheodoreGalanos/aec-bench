# ABOUTME: First-pass task-world opportunity card for friction-loss-hazen-williams.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# mechanical / sprinkler-hydraulics / friction-loss-hazen-williams

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/mechanical/friction_loss_hazen_williams`
- Discipline: `mechanical`
- Category: `sprinkler-hydraulics`
- Tool mode: `with-tool`
- Standards: NFPA 13; AS 2118
- Tags: mechanical; fire-services; sprinkler; hazen-williams; deterministic

## Current Task Shape

Calculates sprinkler pipe friction loss using the imperial Hazen-Williams equation with flow in gpm, length in feet, and diameter in inches. The template includes fitting equivalent length and reports pipe-only and total pressure loss in psi.

## Existing Deterministic Contract

- Parameters: `5`
- Outputs: `4`
- Archetypes: `2`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `flow_rate_gpm` | Sprinkler pipe flow rate | float / gpm | range=1.0..5000.0 |
| `pipe_length_ft` | Straight pipe length | float / ft | range=0.1..2000.0 |
| `pipe_internal_diameter_in` | Internal pipe diameter | float / in | range=0.25..24.0 |
| `hazen_williams_c` | Hazen-Williams C factor | float | range=40.0..160.0 |
| `fitting_equivalent_length_ft` | Equivalent length for fittings | float / ft | range=0.0..1000.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `friction_loss_per_ft_psi` | Friction loss per foot |  | tolerance=0.03 |
| `equivalent_length_ft` | Total equivalent pipe length |  | tolerance=0.03 |
| `pipe_friction_loss_psi` | Straight-pipe friction loss |  | tolerance=0.03 |
| `total_pressure_loss_psi` | Total pressure loss including fittings |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `branch_line` | Sprinkler branch line friction-loss calculation | sprinkler-branch-line; fire-protection-zone |
| `feed_main` | Sprinkler feed main friction-loss calculation | sprinkler-feed-main; fire-main |

### Difficulty Notes

```text
easy: all_given | All parameters given for a sprinkler branch line
medium: all_given | All parameters given across sprinkler pipe contexts
hard: all_given | All parameters given for a sprinkler feed main
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
