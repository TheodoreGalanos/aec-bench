# ABOUTME: First-pass task-world opportunity card for thermal-movement-calc.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# structural / movement-tolerance / thermal-movement-calc

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/structural/thermal_movement_calc`
- Discipline: `structural`
- Category: `movement-tolerance`
- Tool mode: `with-tool`
- Standards: First principles; Material data
- Tags: structural; facades; thermal-movement; movement-joints; deterministic

## Current Task Shape

Calculates the expected thermal movement of a facade or structural member from its length, temperature range, and coefficient of thermal expansion. The template uses the first-principles relationship delta L = alpha L delta T and applies an explicit allowance factor to size movement accommodation.

## Existing Deterministic Contract

- Parameters: `4`
- Outputs: `4`
- Archetypes: `3`
- Visibility mix: all_given; partial
- Hidden parameters: `coefficient_thermal_expansion_microstrain_c`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `member_length_mm` | Member length L | float / mm | range=500.0..60000.0 |
| `temperature_range_c` | Total design temperature range delta T | float / C | range=10.0..90.0 |
| `coefficient_thermal_expansion_microstrain_c` | Coefficient of thermal expansion alpha | float / microstrain/C | range=4.0..30.0; derivable_from=archetype |
| `joint_safety_factor` | Allowance factor applied to calculated movement | float | range=1.0..2.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `thermal_movement_mm` | Total thermal movement over the design temperature range |  | tolerance=0.03 |
| `expansion_movement_mm` | Expansion movement from the neutral temperature |  | tolerance=0.03 |
| `contraction_movement_mm` | Contraction movement from the neutral temperature |  | tolerance=0.03 |
| `accommodation_required_mm` | Movement accommodation required after applying allowance factor |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `aluminium_facade_member` | Aluminium facade mullion or rail | commercial-facade; transport-station-facade |
| `steel_frame_member` | Exposed steel frame member | industrial-platform; roof-framing |
| `glass_panel_edge` | Glass panel edge allowance check | curtain-wall-panel; atrium-glazing |

### Difficulty Notes

```text
easy: all_given | All parameters given for aluminium facade members
medium: all_given | All parameters given across common facade and frame materials
hard: partial | hidden=coefficient_thermal_expansion_microstrain_c | Material coefficient hidden but inferable from component description
```

## Multimodal Expansion

Candidate modality families: `drawing-geometry`, `tabular-source`, `document-evidence`.

Use member sketches, details, load schedules, material tables, and standards/specification extracts.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Compose with tasks that share the same site context, source artifact, or downstream output obligation.

First-pass composition tags: `shared-context`, `pipeline`, `evidence-assembly`.

## Meta-Harness Handles

Candidate operation handles: `parameters`, `outputs`, `difficulty`, `archetype`, `evidence_profile`, `hidden_parameter_policy`, `source_geometry`, `source_table`.

Practical operations to consider:

- `projection`: isolate the arithmetic-only world, source-interpretation world, or evidence-review world.
- `difference`: remove visible parameters, calculator access, source labels, or intermediate hints.
- `subset`: restrict to one archetype, standard, modality, or difficulty tier.
- `product`: compose with a downstream or upstream task that consumes/produces compatible engineering quantities.

## Repair/Event Candidates

- Trigger `evidence_profile` repair if the model reaches the right number without citing or preserving the source artifact.
- Trigger `verifier` repair if final-output tolerances pass while intermediate units, assumptions, or handoff values are inconsistent.
- Trigger `world_schema` repair if a promising composition lacks explicit handoff fields or operation handles.
