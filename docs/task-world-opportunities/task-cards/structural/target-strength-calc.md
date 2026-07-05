# ABOUTME: First-pass task-world opportunity card for target-strength-calc.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# structural / concrete-mix-design / target-strength-calc

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/structural/target_strength_calc`
- Discipline: `structural`
- Category: `concrete-mix-design`
- Tool mode: `with-tool`
- Standards: ACI 318; ACI 301; AS 1379
- Tags: structural; concrete; mix-design; target-strength; deterministic

## Current Task Shape

Calculates the required average compressive strength for concrete mix design from the specified strength, historical standard deviation, and an explicit reliability factor. The template uses fcr = fc + max(k s, minimum margin), keeping code selection assumptions visible through numeric inputs rather than hidden standard lookup.

## Existing Deterministic Contract

- Parameters: `4`
- Outputs: `4`
- Archetypes: `3`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `specified_strength_mpa` | Specified compressive strength f'c | float / MPa | range=20.0..100.0 |
| `standard_deviation_mpa` | Historical standard deviation s | float / MPa | range=0.0..15.0 |
| `k_factor` | Reliability multiplier applied to the standard deviation | float | range=1.0..2.5 |
| `minimum_margin_mpa` | Minimum margin above specified strength | float / MPa | range=0.0..12.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `statistical_margin_mpa` | Statistical margin k times standard deviation |  | tolerance=0.03 |
| `governing_margin_mpa` | Governing margin after minimum margin check |  | tolerance=0.03 |
| `target_mean_strength_mpa` | Required average compressive strength f'cr |  | tolerance=0.03 |
| `margin_above_specified_mpa` | Margin above specified compressive strength |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `normal_strength_good_records` | Normal-strength concrete with good historical production records | commercial-building-slab; water-retaining-structure |
| `normal_strength_limited_records` | Normal-strength concrete with limited or variable production records | regional-precast-yard; remote-project-batch-plant |
| `high_strength_concrete` | High-strength concrete mix requiring a higher control margin | high-rise-core; bridge-precast-girder |

### Difficulty Notes

```text
easy: all_given | All parameters given for normal-strength concrete with good records
medium: all_given | All parameters given for normal-strength mixes with varied production records
hard: all_given | All parameters given for high-strength or less certain production scenarios
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
