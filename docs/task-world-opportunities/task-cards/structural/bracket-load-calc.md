# ABOUTME: First-pass task-world opportunity card for bracket-load-calc.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# structural / bracket-connection / bracket-load-calc

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/structural/bracket_load_calc`
- Discipline: `structural`
- Category: `bracket-connection`
- Tool mode: `with-tool`
- Standards: AS 4100; AISC 360
- Tags: structural; bracket; load; resultant; deterministic

## Current Task Shape

Calculates service vertical load, factored vertical load, factored lateral load, and resultant bracket action using explicit load effects and factors. The template is a reduced deterministic load calculation, not a full bracket capacity design.

## Existing Deterministic Contract

- Parameters: `6`
- Outputs: `4`
- Archetypes: `2`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `dead_load_kn` | Unfactored dead load on the bracket | float / kN | range=0.0..1000.0 |
| `live_load_kn` | Unfactored live load on the bracket | float / kN | range=0.0..1000.0 |
| `wind_load_kn` | Unfactored lateral wind load on the bracket | float / kN | range=0.0..1000.0 |
| `dead_load_factor` | Dead load factor | float / - | range=0.0..2.0 |
| `live_load_factor` | Live load factor | float / - | range=0.0..2.0 |
| `wind_load_factor` | Wind load factor | float / - | range=0.0..2.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `service_vertical_load_kn` | Service vertical bracket load |  | tolerance=0.03 |
| `factored_vertical_load_kn` | Factored vertical bracket load |  | tolerance=0.03 |
| `factored_lateral_load_kn` | Factored lateral bracket load |  | tolerance=0.03 |
| `factored_resultant_load_kn` | Factored resultant bracket load |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `facade_bracket` | Facade or cladding support bracket | facade-support; cladding-bracket |
| `equipment_bracket` | Plant or equipment support bracket | plant-platform; equipment-support |

### Difficulty Notes

```text
easy: all_given | All parameters given for a facade bracket
medium: all_given | All parameters given across bracket types
hard: all_given | All parameters given for equipment brackets
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
