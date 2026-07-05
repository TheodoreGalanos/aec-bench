# ABOUTME: First-pass task-world opportunity card for carbon-equivalent-calc.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# structural / steel-specification / carbon-equivalent-calc

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/structural/carbon_equivalent_calc`
- Discipline: `structural`
- Category: `steel-specification`
- Tool mode: `with-tool`
- Standards: IIW formula; AS/NZS 1554; AWS D1.1
- Tags: structural; steel; weldability; carbon-equivalent; deterministic

## Current Task Shape

Calculates the International Institute of Welding carbon equivalent from steel chemistry using CE = C + Mn/6 + (Cr + Mo + V)/5 + (Ni + Cu)/15. The template reports numeric margins to weldability thresholds and a deterministic preheat indicator for first-pass steel specification checks.

## Existing Deterministic Contract

- Parameters: `9`
- Outputs: `5`
- Archetypes: `3`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `carbon_pct` | Carbon content C | float / % | range=0.02..0.35 |
| `manganese_pct` | Manganese content Mn | float / % | range=0.2..1.8 |
| `chromium_pct` | Chromium content Cr | float / % | range=0.0..1.5 |
| `molybdenum_pct` | Molybdenum content Mo | float / % | range=0.0..0.6 |
| `vanadium_pct` | Vanadium content V | float / % | range=0.0..0.25 |
| `nickel_pct` | Nickel content Ni | float / % | range=0.0..2.0 |
| `copper_pct` | Copper content Cu | float / % | range=0.0..0.8 |
| `caution_threshold_pct` | Carbon equivalent threshold where preheat review is indicated | float / % | range=0.3..0.5 |
| `high_risk_threshold_pct` | Carbon equivalent threshold for high weldability risk | float / % | range=0.45..0.7 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `carbon_equivalent_pct` | IIW carbon equivalent CE |  | tolerance=0.03 |
| `caution_margin_pct` | Margin above the caution threshold |  | tolerance=0.03 |
| `high_risk_margin_pct` | Margin above the high-risk threshold |  | tolerance=0.03 |
| `weldability_risk_index` | Numeric weldability risk class: 0 low, 1 caution, 2 high |  | tolerance=0.01 |
| `preheat_indicated` | Numeric preheat indication: 0 no, 1 yes |  | tolerance=0.01 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `low_carbon_plate` | Low-carbon structural plate with low alloy content | building-frame-steel; bridge-secondary-steel |
| `hsla_plate` | High-strength low-alloy plate with moderate alloy content | crane-runway-girder; heavy-industrial-platform |
| `repair_welding_unknown_origin` | Repair welding material with elevated alloy content | brownfield-plant-repair; marine-structure-repair |

### Difficulty Notes

```text
easy: all_given | All chemistry and thresholds given for low-carbon steel
medium: all_given | All chemistry and thresholds given across common structural steels
hard: all_given | All chemistry and thresholds given for higher-risk repair welding cases
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
