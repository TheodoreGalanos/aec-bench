# ABOUTME: First-pass task-world opportunity card for load-combinations.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# structural / load-analysis / load-combinations

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/structural/load_combinations`
- Discipline: `structural`
- Category: `load-analysis`
- Tool mode: `with-tool`
- Standards: AASHTO LRFD 3.4; EN 1990
- Tags: structural; load-combinations; factored-actions; deterministic

## Current Task Shape

Applies explicit dead, live, wind, and seismic load factors to three reduced load combinations. The template reports each factored moment, the governing moment, the associated governing shear, and a numeric governing-combination index.

## Existing Deterministic Contract

- Parameters: `14`
- Outputs: `6`
- Archetypes: `2`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `dead_moment_knm` | Unfactored dead-load moment | float / kNm | range=0.0..100000.0 |
| `live_moment_knm` | Unfactored live-load moment | float / kNm | range=0.0..100000.0 |
| `wind_moment_knm` | Unfactored wind-load moment | float / kNm | range=0.0..100000.0 |
| `seismic_moment_knm` | Unfactored seismic-load moment | float / kNm | range=0.0..100000.0 |
| `dead_shear_kn` | Unfactored dead-load shear | float / kN | range=0.0..50000.0 |
| `live_shear_kn` | Unfactored live-load shear | float / kN | range=0.0..50000.0 |
| `wind_shear_kn` | Unfactored wind-load shear | float / kN | range=0.0..50000.0 |
| `seismic_shear_kn` | Unfactored seismic-load shear | float / kN | range=0.0..50000.0 |
| `combo_1_dead_factor` | Dead-load factor for combination 1 | float / - | range=0.0..2.0 |
| `combo_1_live_factor` | Live-load factor for combination 1 | float / - | range=0.0..2.0 |
| `combo_2_dead_factor` | Dead-load factor for combination 2 | float / - | range=0.0..2.0 |
| `combo_2_wind_factor` | Wind-load factor for combination 2 | float / - | range=0.0..2.0 |
| `combo_3_dead_factor` | Dead-load factor for combination 3 | float / - | range=0.0..2.0 |
| `combo_3_seismic_factor` | Seismic-load factor for combination 3 | float / - | range=0.0..2.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `combo_1_moment_knm` | Factored moment for combination 1 |  | tolerance=0.03 |
| `combo_2_moment_knm` | Factored moment for combination 2 |  | tolerance=0.03 |
| `combo_3_moment_knm` | Factored moment for combination 3 |  | tolerance=0.03 |
| `governing_moment_knm` | Maximum factored moment |  | tolerance=0.03 |
| `governing_shear_kn` | Factored shear associated with the governing moment combination |  | tolerance=0.03 |
| `governing_combination_index` | Numeric index of the governing moment combination |  | tolerance=0.01 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `bridge_member` | Bridge member factored action check | bridge-superstructure; bridge-substructure |
| `building_member` | Building member factored action check | building-frame; industrial-structure |

### Difficulty Notes

```text
easy: all_given | All parameters given for a building member
medium: all_given | All parameters given across building and bridge members
hard: all_given | All parameters given for a bridge member
```

## Multimodal Expansion

Candidate modality families: `drawing-geometry`, `tabular-source`, `document-evidence`.

Use building elevations, terrain/zone diagrams, load schedules, and standards extracts.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Wind-speed and pressure derivations can feed structural member, bracket, cladding, and foundation checks.

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
