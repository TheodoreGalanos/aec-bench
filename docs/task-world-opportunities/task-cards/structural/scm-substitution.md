# ABOUTME: First-pass task-world opportunity card for scm-substitution.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# structural / concrete-mix-design / scm-substitution

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/structural/scm_substitution`
- Discipline: `structural`
- Category: `concrete-mix-design`
- Tool mode: `with-tool`
- Standards: ACI 211.1; AS 1379
- Tags: structural; concrete; scm; binder; deterministic

## Current Task Shape

Calculates cement content, SCM content, cement reduction, and water-binder ratio from total binder content, SCM replacement percentage, and water content. The template is a deterministic binder mass-balance calculation.

## Existing Deterministic Contract

- Parameters: `3`
- Outputs: `4`
- Archetypes: `2`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `total_binder_kg_m3` | Total binder content | float / kg/m3 | range=100.0..800.0 |
| `scm_replacement_pct` | Percentage of total binder replaced by SCM | float / % | range=0.0..80.0 |
| `water_content_kg_m3` | Mix water content | float / kg/m3 | range=0.0..400.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `cement_content_kg_m3` | Cement content after SCM replacement |  | tolerance=0.03 |
| `scm_content_kg_m3` | SCM content |  | tolerance=0.03 |
| `cement_reduction_kg_m3` | Reduction in cement content relative to all-cement binder |  | tolerance=0.03 |
| `water_binder_ratio` | Water-binder ratio |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `fly_ash_mix` | Concrete mix with fly ash binder replacement | building-concrete; fly-ash-mix |
| `slag_mix` | Concrete mix with slag binder replacement | marine-concrete; slag-mix |

### Difficulty Notes

```text
easy: all_given | All parameters given for a fly ash mix
medium: all_given | All parameters given across SCM mixes
hard: all_given | All parameters given for higher replacement slag mixes
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
