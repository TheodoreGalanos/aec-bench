# ABOUTME: First-pass task-world opportunity card for ice-load-calculation.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# electrical / structural-loading / ice-load-calculation

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/electrical/ice_load_calculation`
- Discipline: `electrical`
- Category: `structural-loading`
- Tool mode: `with-tool`
- Standards: IEC 60826; AS/NZS 7000
- Tags: electrical; transmission-line; ice-load; wind-load; conductor; deterministic

## Current Task Shape

Calculates a reduced iced-conductor loading case using annular ice area, ice density, wind-on-ice pressure, and span length. The template reports vertical ice weight and combined vector loading for overhead line structural checks.

## Existing Deterministic Contract

- Parameters: `5`
- Outputs: `6`
- Archetypes: `2`
- Visibility mix: all_given; partial
- Hidden parameters: `ice_density_kg_m3`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `conductor_diameter_mm` | Bare conductor outside diameter | float / mm | range=5..80 |
| `ice_thickness_mm` | Radial ice accretion thickness | float / mm | range=0..50 |
| `ice_density_kg_m3` | Ice density | float / kg/m3 | range=400..950 |
| `wind_on_ice_pressure_pa` | Wind pressure applied to the iced conductor diameter | float / Pa | range=0..2500 |
| `span_length_m` | Conductor span length | float / m | range=20..800 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `iced_conductor_diameter_mm` | Diameter of conductor plus radial ice |  | tolerance=0.03 |
| `ice_weight_n_per_m` | Vertical ice weight per metre |  | tolerance=0.03 |
| `total_vertical_load_n_per_m` | Total vertical load per metre in the reduced case |  | tolerance=0.03 |
| `wind_on_ice_load_n_per_m` | Transverse wind-on-ice load per metre |  | tolerance=0.03 |
| `combined_ice_wind_load_n_per_m` | Vector combined ice and wind load per metre |  | tolerance=0.03 |
| `span_combined_load_n` | Combined load integrated over the span |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `light_ice_distribution` | Distribution line with light ice accretion | distribution-line; icing-condition |
| `heavy_ice_transmission` | Transmission line with heavier ice accretion | transmission-line; icing-condition |

### Difficulty Notes

```text
easy: all_given | Distribution line with all values visible
medium: all_given | Iced line selected from distribution or transmission cases
hard: partial | hidden=ice_density_kg_m3 | Transmission line with ice density embedded in context
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
