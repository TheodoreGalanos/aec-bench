# ABOUTME: First-pass task-world opportunity card for mooring-line-capacity.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# structural / marine-mooring / mooring-line-capacity

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/structural/mooring_line_capacity`
- Discipline: `structural`
- Category: `marine-mooring`
- Tool mode: `with-tool`
- Standards: AS 4997; BS 6349-4; PIANC WG153
- Tags: structural; marine; mooring; capacity; deterministic

## Current Task Shape

Calculates design line tension from explicit mooring line tension, dynamic factor, and consequence factor, then compares the result with minimum breaking load. The template reports capacity margin, reserve capacity, utilisation, and a numeric pass flag.

## Existing Deterministic Contract

- Parameters: `4`
- Outputs: `5`
- Archetypes: `2`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `line_tension_kn` | Characteristic mooring line tension | float / kN | range=10.0..5000.0 |
| `dynamic_factor` | Dynamic amplification factor applied to line tension | float / - | range=1.0..2.5 |
| `consequence_factor` | Consequence factor applied to design tension | float / - | range=1.0..2.0 |
| `mbl_kn` | Minimum breaking load of the mooring line | float / kN | range=100.0..20000.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `design_tension_kn` | Design mooring line tension |  | tolerance=0.03 |
| `capacity_margin_ratio` | Ratio of minimum breaking load to design tension |  | tolerance=0.03 |
| `reserve_capacity_kn` | Minimum breaking load minus design tension |  | tolerance=0.03 |
| `utilisation_ratio` | Ratio of design tension to minimum breaking load |  | tolerance=0.03 |
| `passes_capacity_check` | Numeric pass flag: 1 if design tension is within capacity, otherwise 0 |  | tolerance=0.01 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `service_berth_line` | Service berth mooring line capacity check | service-wharf; ferry-terminal |
| `bulk_berth_line` | Bulk berth mooring line capacity check | bulk-export-berth; industrial-port-wharf |

### Difficulty Notes

```text
easy: all_given | All parameters given for a service berth mooring line
medium: all_given | All parameters given across service and bulk berth lines
hard: all_given | All parameters given for a bulk berth mooring line
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
