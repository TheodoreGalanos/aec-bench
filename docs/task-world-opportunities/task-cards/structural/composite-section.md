# ABOUTME: First-pass task-world opportunity card for composite-section.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# structural / superstructure-design / composite-section

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/structural/composite_section`
- Discipline: `structural`
- Category: `superstructure-design`
- Tool mode: `with-tool`
- Standards: AASHTO LRFD 6.10; AS/NZS 5100.6
- Tags: structural; bridge; composite-section; section-properties; deterministic

## Current Task Shape

Calculates transformed section properties for a simplified steel I-girder with concrete slab and haunch using the modular ratio method. The template reports transformed area, neutral axis, second moment of area, and top and bottom section moduli.

## Existing Deterministic Contract

- Parameters: `11`
- Outputs: `5`
- Archetypes: `2`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `top_flange_width_mm` | Steel top flange width | float / mm | range=50.0..2000.0 |
| `top_flange_thickness_mm` | Steel top flange thickness | float / mm | range=5.0..150.0 |
| `web_depth_mm` | Clear steel web depth between flanges | float / mm | range=100.0..5000.0 |
| `web_thickness_mm` | Steel web thickness | float / mm | range=5.0..100.0 |
| `bottom_flange_width_mm` | Steel bottom flange width | float / mm | range=50.0..2000.0 |
| `bottom_flange_thickness_mm` | Steel bottom flange thickness | float / mm | range=5.0..150.0 |
| `slab_width_mm` | Effective concrete slab width | float / mm | range=100.0..10000.0 |
| `slab_thickness_mm` | Concrete slab thickness | float / mm | range=50.0..500.0 |
| `haunch_width_mm` | Concrete haunch width | float / mm | range=50.0..3000.0 |
| `haunch_thickness_mm` | Concrete haunch thickness | float / mm | range=10.0..500.0 |
| `modular_ratio` | Steel-to-concrete modular ratio | float | range=1.0..20.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `transformed_area_mm2` | Transformed composite section area |  | tolerance=0.03 |
| `neutral_axis_from_bottom_mm` | Neutral axis from bottom of steel section |  | tolerance=0.03 |
| `transformed_inertia_mm4` | Transformed second moment of area |  | tolerance=0.03 |
| `bottom_section_modulus_mm3` | Bottom section modulus |  | tolerance=0.03 |
| `top_section_modulus_mm3` | Top section modulus |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `plate_girder` | Bridge plate-girder composite section | bridge-plate-girder; composite-road-bridge |
| `rolled_girder` | Rolled-girder composite section | rolled-girder-bridge; short-span-composite-deck |

### Difficulty Notes

```text
easy: all_given | All parameters given for a rolled girder
medium: all_given | All parameters given across composite girder types
hard: all_given | All parameters given for a bridge plate girder
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
