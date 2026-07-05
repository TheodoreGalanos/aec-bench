# ABOUTME: First-pass task-world opportunity card for lap-splice-length.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# structural / rebar-detailing / lap-splice-length

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/structural/lap_splice_length`
- Discipline: `structural`
- Category: `rebar-detailing`
- Tool mode: `with-tool`
- Standards: ACI 318; AS 3600
- Tags: structural; rebar; lap-splice; detailing; deterministic

## Current Task Shape

Calculates lap splice length from a provided development length and explicit splice, bar-location, and coating factors. The template rounds the required lap length up to the nearest 10 mm and compares it with a provided lap length.

## Existing Deterministic Contract

- Parameters: `5`
- Outputs: `4`
- Archetypes: `2`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `development_length_mm` | Base development length | float / mm | range=100.0..4000.0 |
| `splice_class_factor` | Explicit splice class factor | float / - | range=0.5..2.5 |
| `bar_location_factor` | Explicit bar location factor | float / - | range=0.5..2.0 |
| `coating_factor` | Explicit coating factor | float / - | range=0.5..2.0 |
| `provided_lap_length_mm` | Provided lap length to compare against the rounded requirement | float / mm | range=0.0..8000.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `calculated_lap_length_mm` | Calculated unrounded lap splice length |  | tolerance=0.03 |
| `rounded_lap_length_mm` | Required lap length rounded up to the nearest 10 mm |  | tolerance=0.01 |
| `provided_margin_mm` | Provided lap length minus rounded required lap length |  | tolerance=0.03 |
| `provided_lap_satisfies` | Numeric flag where 1 means the provided lap satisfies the requirement |  | tolerance=0.01 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `slab_rebar` | Slab reinforcement lap splice check | concrete-slab; reinforcement-detailing |
| `wall_rebar` | Wall reinforcement lap splice check | concrete-wall; vertical-reinforcement |

### Difficulty Notes

```text
easy: all_given | All parameters given for slab reinforcement
medium: all_given | All parameters given across reinforcement elements
hard: all_given | All parameters given for wall reinforcement
```

## Multimodal Expansion

Candidate modality families: `drawing-geometry`, `tabular-source`, `document-evidence`.

Use section sketches, reinforcement schedules, member tables, vessel data, and specification excerpts.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Structural outputs can feed load paths, connection checks, marine berth systems, and construction tolerance reviews.

First-pass composition tags: `shared-context`, `pipeline`, `evidence-assembly`.

## Meta-Harness Handles

Candidate operation handles: `parameters`, `outputs`, `difficulty`, `archetype`, `evidence_profile`, `source_geometry`, `source_table`.

Practical operations to consider:

- `projection`: isolate the arithmetic-only world, source-interpretation world, or evidence-review world.
- `difference`: remove visible parameters, calculator access, source labels, or intermediate hints.
- `subset`: restrict to one archetype, standard, modality, or difficulty tier.
- `product`: compose with a downstream or upstream task that consumes/produces compatible engineering quantities.

## Repair/Event Candidates

- Trigger `evidence_profile` repair if the model reaches the right number without citing or preserving the source artifact.
- Trigger `verifier` repair if final-output tolerances pass while intermediate units, assumptions, or handoff values are inconsistent.
- Trigger `world_schema` repair if a promising composition lacks explicit handoff fields or operation handles.
