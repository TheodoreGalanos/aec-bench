# ABOUTME: First-pass task-world opportunity card for occupant-load.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# mechanical / prescriptive-compliance / occupant-load

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/mechanical/occupant_load`
- Discipline: `mechanical`
- Category: `prescriptive-compliance`
- Tool mode: `with-tool`
- Standards: IBC; NCC
- Tags: mechanical; life-safety; occupant-load; deterministic

## Current Task Shape

Calculates occupant load from floor area and an explicit area-per-occupant criterion. The template reports unrounded occupants, design occupants rounded up to a whole person, and occupant density.

## Existing Deterministic Contract

- Parameters: `2`
- Outputs: `3`
- Archetypes: `2`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `floor_area_m2` | Floor area being assessed | float / m2 | range=1.0..20000.0 |
| `area_per_occupant_m2` | Explicit area allowed per occupant | float / m2/person | range=0.5..100.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `calculated_occupants` | Unrounded occupant count |  | tolerance=0.03 |
| `design_occupants` | Occupant count rounded up to a whole person |  | tolerance=0.01 |
| `occupant_density_person_m2` | Design occupant density |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `office_floor` | Office floor occupant load check | office-floor; commercial-building |
| `assembly_space` | Assembly area occupant load check | assembly-space; station-concourse |

### Difficulty Notes

```text
easy: all_given | All parameters given for an office floor
medium: all_given | All parameters given across occupancy types
hard: all_given | All parameters given for assembly occupancy
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
