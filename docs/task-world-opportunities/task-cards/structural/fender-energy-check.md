# ABOUTME: First-pass task-world opportunity card for fender-energy-check.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# structural / fender-design / fender-energy-check

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/structural/fender_energy_check`
- Discipline: `structural`
- Category: `fender-design`
- Tool mode: `with-tool`
- Standards: PIANC WG211; BS 6349-4
- Tags: structural; marine; fender; energy-capacity; deterministic

## Current Task Shape

Calculates corrected fender energy absorption capacity from rated energy and explicit temperature, velocity, angular, and manufacturing tolerance factors. The template reports corrected capacity, utilisation ratio, and capacity margin against the supplied design berthing energy.

## Existing Deterministic Contract

- Parameters: `6`
- Outputs: `4`
- Archetypes: `2`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `design_berthing_energy_knm` | Design berthing energy ED | float / kNm | range=5.0..20000.0 |
| `fender_rated_energy_knm` | Manufacturer rated fender energy ER | float / kNm | range=10.0..50000.0 |
| `temperature_factor` | Temperature correction factor | float | range=0.6..1.3 |
| `velocity_factor` | Velocity correction factor | float | range=0.7..1.3 |
| `angular_factor` | Angular compression correction factor | float | range=0.5..1.1 |
| `manufacturing_tolerance_factor` | Manufacturing tolerance correction factor | float | range=0.8..1.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `correction_factor` | Total fender energy correction factor |  | tolerance=0.03 |
| `corrected_capacity_knm` | Corrected fender energy capacity |  | tolerance=0.03 |
| `energy_utilisation_ratio` | Design energy divided by corrected capacity |  | tolerance=0.03 |
| `capacity_margin_knm` | Corrected capacity minus design berthing energy |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `rubber_cell_fender` | Rubber cell fender under near-normal vessel approach | ferry-terminal; general-cargo-berth |
| `large_cone_fender` | Large cone fender for high-energy industrial berth | bulk-export-berth; container-terminal |

### Difficulty Notes

```text
easy: all_given | All parameters given for a rubber cell fender
medium: all_given | All parameters given across common fender systems
hard: all_given | All parameters given for high-energy berth fender systems
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
