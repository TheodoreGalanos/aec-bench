# ABOUTME: First-pass task-world opportunity card for nitrification-srt.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# mechanical / nutrient-removal / nitrification-srt

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/mechanical/nitrification_srt`
- Discipline: `mechanical`
- Category: `nutrient-removal`
- Tool mode: `with-tool`
- Standards: Metcalf and Eddy Wastewater Engineering
- Tags: mechanical; wastewater; nitrification; srt; deterministic

## Current Task Shape

Calculates required solids retention time for nitrification using temperature-corrected nitrifier growth with ammonia and dissolved oxygen limitation factors. The template reports growth factors, net growth rate, and the design SRT implied by a selected safety factor.

## Existing Deterministic Contract

- Parameters: `9`
- Outputs: `5`
- Archetypes: `2`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `max_specific_growth_d` | Maximum specific nitrifier growth rate at 20 C | float / 1/d | range=0.1..2.0 |
| `theta` | Temperature correction coefficient | float | range=1.01..1.15 |
| `wastewater_temperature_c` | Wastewater temperature | float / deg C | range=5.0..35.0 |
| `ammonia_n_mg_l` | Ammonia nitrogen concentration | float / mg/L | range=0.1..80.0 |
| `half_saturation_n_mg_l` | Ammonia half-saturation coefficient | float / mg/L | range=0.05..5.0 |
| `dissolved_oxygen_mg_l` | Dissolved oxygen concentration | float / mg/L | range=0.1..8.0 |
| `oxygen_half_saturation_mg_l` | Oxygen half-saturation coefficient | float / mg/L | range=0.05..2.0 |
| `decay_rate_d` | Nitrifier decay rate | float / 1/d | range=0.0..0.2 |
| `safety_factor` | SRT safety factor | float | range=1.0..4.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `temperature_corrected_growth_d` | Temperature-corrected maximum growth rate |  | tolerance=0.03 |
| `substrate_factor` | Ammonia substrate limitation factor |  | tolerance=0.03 |
| `oxygen_factor` | Dissolved oxygen limitation factor |  | tolerance=0.03 |
| `net_growth_d` | Net nitrifier growth rate |  | tolerance=0.03 |
| `required_srt_days` | Required solids retention time |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `municipal_plant` | Municipal wastewater nitrification SRT check | municipal-activated-sludge; secondary-treatment |
| `cool_weather_upgrade` | Cool-weather nitrification upgrade check | winter-nitrification; plant-upgrade |

### Difficulty Notes

```text
easy: all_given | All parameters given for a municipal plant
medium: all_given | All parameters given across nitrification checks
hard: all_given | All parameters given for cool-weather nitrification
```

## Multimodal Expansion

Candidate modality families: `chart-curve`, `drawing-geometry`, `tabular-source`.

Use schematics, equipment curves, schedules, commissioning tables, and source datasheets.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Compose with tasks that share the same site context, source artifact, or downstream output obligation.

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
