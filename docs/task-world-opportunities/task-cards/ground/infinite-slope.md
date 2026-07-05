# ABOUTME: First-pass task-world opportunity card for infinite-slope.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# ground / slope-stability / infinite-slope

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/ground/infinite_slope`
- Discipline: `ground`
- Category: `slope-stability`
- Tool mode: `with-tool`
- Standards: Standard geotechnical texts
- Tags: geotechnical; slope-stability; deterministic

## Current Task Shape

Computes the factor of safety against shallow planar failure on long uniform slopes using the infinite slope equation with Mohr-Coulomb shear strength. Accounts for pore water pressure from a water table parallel to the slope surface, balancing the driving shear stress (gamma*z*sin(beta)*cos(beta)) against the resisting cohesion and frictional strength along the failure plane.

## Existing Deterministic Contract

- Parameters: `6`
- Outputs: `4`
- Archetypes: `8`
- Visibility mix: all_given; partial
- Hidden parameters: `cohesion_kpa`, `friction_angle_deg`, `unit_weight_kn_m3`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `slope_angle_deg` | Slope angle beta | float / degrees | range=5..45 |
| `friction_angle_deg` | Effective friction angle phi' | float / degrees | range=0..45; derivable_from=archetype |
| `cohesion_kpa` | Effective cohesion c' | float / kPa | range=0..150; derivable_from=archetype |
| `unit_weight_kn_m3` | Soil unit weight gamma | float / kN/m³ | range=14..23; derivable_from=archetype |
| `failure_depth_m` | Depth to failure surface z | float / m | range=0.5..10.0 |
| `water_table_depth_m` | Depth to water table from ground surface | float / m | range=0..100.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `pore_pressure_kpa` | Pore water pressure at failure surface u (kPa) |  | tolerance=0.03 |
| `driving_stress_kpa` | Driving shear stress (kPa) |  | tolerance=0.03 |
| `resisting_stress_kpa` | Resisting shear stress (kPa) |  | tolerance=0.03 |
| `factor_of_safety` | Factor of safety FoS |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `soft_nc_clay` | Soft normally consolidated clay | brisbane-alluvial; darwin-estuarine |
| `firm_clay` | Firm clay | brisbane-alluvial; melbourne-basalt |
| `stiff_oc_clay` | Stiff overconsolidated clay | sydney-hawkesbury; adelaide-stiff; melbourne-basalt |
| `loose_sand` | Loose sand | hunter-valley-alluvial |
| `medium_dense_sand` | Medium dense sand | perth-coastal; hunter-valley-alluvial |
| `dense_sand` | Dense sand | perth-coastal; cairns-coral |
| `silty_sand` | Silty sand | hunter-valley-alluvial |
| `residual_weathered_rock` | Residual/weathered rock | sydney-hawkesbury |

### Difficulty Notes

```text
easy: all_given | Dry cohesionless slope — simplest formula
medium: all_given | Dry slope with cohesion — adds c' term
hard: partial | hidden=cohesion_kpa, friction_angle_deg, unit_weight_kn_m3 | Water table present, soil parameters hidden
```

## Multimodal Expansion

Candidate modality families: `drawing-geometry`, `tabular-source`, `document-evidence`.

Use borehole logs, lab tables, slope sections, retaining-wall sketches, and geotechnical notes.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Ground parameters can feed retaining-wall, foundation, slope-stability, and structural load checks.

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
