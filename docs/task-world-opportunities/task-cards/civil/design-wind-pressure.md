# ABOUTME: First-pass task-world opportunity card for design-wind-pressure.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / wind-load-derivation / design-wind-pressure

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/design_wind_pressure`
- Discipline: `civil`
- Category: `wind-load-derivation`
- Tool mode: `with-tool`
- Standards: AS/NZS 1170.2
- Tags: civil; wind; pressure; aerodynamic; wind-load; structural-actions; deterministic

## Current Task Shape

Computes design wind pressure on a building surface using the AS/NZS 1170.2 Section 2.4 formula p = 0.5 * rho_air * V_des^2 * C_fig * C_dyn. Determines the basic dynamic pressure from wind speed, applies aerodynamic shape and dynamic response factors, and calculates the total wind force on a tributary area for structural design.

## Existing Deterministic Contract

- Parameters: `5`
- Outputs: `3`
- Archetypes: `6`
- Visibility mix: all_given; partial
- Hidden parameters: `air_density_kg_per_m3`, `cdyn`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `design_wind_speed_m_per_s` | Design wind speed V_des,theta for the chosen cardinal direction | float / m/s | range=20.0..80.0 |
| `cfig` | Aerodynamic shape factor C_fig (positive = pressure, negative = suction) | float / dimensionless | range=-2.0..2.0 |
| `cdyn` | Dynamic response factor C_dyn (1.0 for most low-rise structures) | float / dimensionless | range=0.8..1.2; derivable_from=archetype |
| `air_density_kg_per_m3` | Air density rho_air (standard value 1.2 kg/m3) | float / kg/m3 | range=1.0..1.4; derivable_from=archetype |
| `tributary_area_m2` | Tributary area of the surface being loaded | float / m2 | range=1.0..200.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `dynamic_pressure_kpa` | Basic dynamic wind pressure q = 0.5 * rho * V^2 (kPa) |  | tolerance=0.03 |
| `design_pressure_kpa` | Design wind pressure p = q * C_fig * C_dyn (kPa) |  | tolerance=0.03 |
| `total_force_kn` | Total wind force on the tributary area F = p * A (kN) |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `low_rise_windward_wall` | Windward wall of a low-rise building in suburban terrain | suburban-residential-house; small-commercial-warehouse |
| `low_rise_roof_suction` | Roof surface under suction on a low-rise building in open terrain | rural-farm-shed-roof; coastal-industrial-roof |
| `mid_rise_facade` | Facade panel on a mid-rise office building in city fringe terrain | city-fringe-office-block; university-campus-building |
| `high_rise_cladding` | Cladding panel on a tall building in urban terrain with dynamic amplification | cbd-high-rise-tower; waterfront-residential-tower |
| `industrial_large_opening` | Large wall opening on an industrial building in open terrain | port-warehouse-roller-door; regional-aircraft-hangar |
| `cyclonic_coastal` | Coastal structure in a cyclonic wind region with high design wind speeds | north-qld-cyclonic-house; darwin-commercial-building |

### Difficulty Notes

```text
easy: all_given | All parameters given, low-rise buildings with C_dyn = 1.0 and standard air density
medium: all_given | All parameters given, wider range of building types including mid-rise and industrial
hard: partial | hidden=cdyn, air_density_kg_per_m3 | C_dyn and air density hidden; agent must adopt standard values from engineering knowledge
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
