# ABOUTME: First-pass task-world opportunity card for slr-calculation.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# mechanical / clarifier-design / slr-calculation

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/mechanical/slr_calculation`
- Discipline: `mechanical`
- Category: `clarifier-design`
- Tool mode: `with-tool`
- Standards: Ten States Standards; WEF MOP 8
- Tags: mechanical; wastewater; clarifier; solids-loading-rate; deterministic

## Current Task Shape

Calculates secondary clarifier solids loading rate from total clarifier flow, MLSS concentration, and surface area, then compares the result with an explicit maximum criterion. The template reports solids mass flow, area-normalised loading, utilisation, margin, and a numeric criterion flag.

## Existing Deterministic Contract

- Parameters: `4`
- Outputs: `5`
- Archetypes: `2`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `total_flow_m3_d` | Total flow to the clarifier including return activated sludge | float / m3/d | range=1.0..1500000.0 |
| `mlss_concentration_mg_l` | Mixed liquor suspended solids concentration | float / mg/L | range=500.0..8000.0 |
| `clarifier_surface_area_m2` | Clarifier plan surface area | float / m2 | range=1.0..100000.0 |
| `maximum_slr_kg_m2_h` | Maximum allowable solids loading rate criterion | float / kg/m2.h | range=1.0..20.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `solids_mass_flow_kg_d` | Clarifier solids mass flow |  | tolerance=0.03 |
| `solids_loading_rate_kg_m2_h` | Calculated solids loading rate |  | tolerance=0.03 |
| `utilisation_ratio` | Ratio of calculated SLR to maximum criterion |  | tolerance=0.03 |
| `compliance_margin_kg_m2_h` | Positive margin below the maximum criterion |  | tolerance=0.03 |
| `criterion_satisfied` | Numeric flag where 1 means the criterion is satisfied |  | tolerance=0.01 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `secondary_clarifier` | Secondary clarifier solids loading check | municipal-wwtp; secondary-clarifier |
| `high_rate_clarifier` | High-rate secondary clarifier solids loading check | large-wwtp; peak-wet-weather |

### Difficulty Notes

```text
easy: all_given | All parameters given for a secondary clarifier
medium: all_given | All parameters given across secondary clarifier archetypes
hard: all_given | All parameters given for a high-rate clarifier
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
