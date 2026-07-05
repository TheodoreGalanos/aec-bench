# ABOUTME: First-pass task-world opportunity card for effective-wind-area.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# structural / wind-load-analysis / effective-wind-area

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/structural/effective_wind_area`
- Discipline: `structural`
- Category: `wind-load-analysis`
- Tool mode: `with-tool`
- Standards: ASCE 7; AS/NZS 1170.2
- Tags: structural; facades; wind-load; effective-area; deterministic

## Current Task Shape

Calculates effective wind area for cladding or supporting-member pressure checks from panel dimensions, support span, tributary width, and an explicit minimum area. The template reports panel area, member tributary area, governing effective area, and the ratio to the minimum pressure area.

## Existing Deterministic Contract

- Parameters: `5`
- Outputs: `4`
- Archetypes: `2`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `panel_width_m` | Cladding panel width | float / m | range=0.2..6.0 |
| `panel_height_m` | Cladding panel height | float / m | range=0.2..6.0 |
| `supporting_member_span_m` | Span of supporting member | float / m | range=0.5..12.0 |
| `tributary_width_m` | Tributary width to supporting member | float / m | range=0.2..6.0 |
| `minimum_effective_area_m2` | Minimum effective area used for pressure coefficient selection | float / m2 | range=0.1..10.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `panel_area_m2` | Cladding panel area |  | tolerance=0.03 |
| `member_tributary_area_m2` | Supporting member tributary area |  | tolerance=0.03 |
| `effective_wind_area_m2` | Effective wind area for pressure coefficient selection |  | tolerance=0.03 |
| `area_averaging_ratio` | Effective area divided by minimum effective area |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `small_cladding_panel` | Small facade cladding panel on closely spaced supports | commercial-facade; station-glazing |
| `large_curtain_wall_bay` | Large curtain wall bay with long support spans | high-rise-curtain-wall; airport-terminal-facade |

### Difficulty Notes

```text
easy: all_given | All parameters given for a small cladding panel
medium: all_given | All parameters given across small and large facade areas
hard: all_given | All parameters given for large facade support areas
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
