# ABOUTME: First-pass task-world opportunity card for berthing-energy-calc.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# structural / berthing-energy / berthing-energy-calc

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/structural/berthing_energy_calc`
- Discipline: `structural`
- Category: `berthing-energy`
- Tool mode: `with-tool`
- Standards: BS 6349-4; PIANC WG211; AS 4997
- Tags: structural; marine; berthing-energy; ports; deterministic

## Current Task Shape

Calculates characteristic and design berthing energy for a vessel from displacement, approach velocity, hydrodynamic and berth coefficients, and an explicit safety factor. The template applies the kinetic energy relationship E = 0.5 M V^2 and multiplies by the provided marine design coefficients.

## Existing Deterministic Contract

- Parameters: `7`
- Outputs: `4`
- Archetypes: `2`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `vessel_displacement_t` | Vessel displacement mass | float / t | range=100.0..250000.0 |
| `approach_velocity_m_s` | Vessel approach velocity normal to berth | float / m/s | range=0.02..0.5 |
| `added_mass_coefficient` | Added mass coefficient CM | float | range=1.0..2.2 |
| `eccentricity_coefficient` | Eccentricity coefficient CE | float | range=0.3..1.0 |
| `berth_configuration_coefficient` | Berth configuration coefficient CC | float | range=0.8..1.2 |
| `softness_coefficient` | Berth and fender softness coefficient CS | float | range=0.8..1.1 |
| `safety_factor` | Design safety factor applied to characteristic energy | float | range=1.0..2.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `kinetic_energy_knm` | Unmodified vessel kinetic energy |  | tolerance=0.03 |
| `characteristic_energy_knm` | Characteristic berthing energy after coefficient product |  | tolerance=0.03 |
| `design_energy_knm` | Design berthing energy |  | tolerance=0.03 |
| `coefficient_product` | Product of berthing energy coefficients |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `small_service_vessel` | Small service vessel berthing at a sheltered wharf | service-wharf; ferry-terminal |
| `bulk_carrier_berth` | Bulk carrier berthing at an open industrial wharf | bulk-export-berth; industrial-port-wharf |

### Difficulty Notes

```text
easy: all_given | All parameters given for a small sheltered vessel
medium: all_given | All parameters given across small and bulk vessels
hard: all_given | All parameters given for larger industrial berth cases
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
