# ABOUTME: First-pass task-world opportunity card for egress-width.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# mechanical / egress-modeling / egress-width

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/mechanical/egress_width`
- Discipline: `mechanical`
- Category: `egress-modeling`
- Tool mode: `with-tool`
- Standards: IBC; NCC
- Tags: mechanical; life-safety; egress; width; deterministic

## Current Task Shape

Calculates required egress width from occupant load and an explicit width-per-occupant criterion, then compares it with provided width. The template reports required width, margin, utilisation, and a numeric pass flag.

## Existing Deterministic Contract

- Parameters: `3`
- Outputs: `4`
- Archetypes: `2`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `occupant_load` | Design occupant load | float / persons | range=1.0..100000.0 |
| `width_per_occupant_mm` | Required egress width per occupant | float / mm/person | range=1.0..50.0 |
| `provided_width_mm` | Provided aggregate egress width | float / mm | range=1.0..100000.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `required_width_mm` | Required aggregate egress width |  | tolerance=0.03 |
| `provided_margin_mm` | Provided width minus required width |  | tolerance=0.03 |
| `utilisation_ratio` | Required width divided by provided width |  | tolerance=0.03 |
| `width_satisfies` | Numeric flag where 1 means the provided width satisfies the requirement |  | tolerance=0.01 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `office_exit` | Office exit width check | office-exit; commercial-building |
| `station_concourse` | Station concourse egress width check | station-concourse; public-transport |

### Difficulty Notes

```text
easy: all_given | All parameters given for office exits
medium: all_given | All parameters given across egress settings
hard: all_given | All parameters given for high-occupancy concourses
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
