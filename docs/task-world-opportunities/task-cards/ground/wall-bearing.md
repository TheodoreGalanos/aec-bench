# ABOUTME: First-pass task-world opportunity card for wall-bearing.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# ground / retaining-walls / wall-bearing

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/ground/wall_bearing`
- Discipline: `ground`
- Category: `retaining-walls`
- Tool mode: `with-tool`
- Standards: AS 4678; Meyerhof (1963)
- Tags: geotechnical; retaining-wall; bearing-capacity; eccentricity

## Current Task Shape

Checks bearing pressure adequacy beneath a retaining wall base by computing the eccentricity of the resultant vertical load and applying Meyerhof's effective width method (B' = B - 2e). Compares the maximum bearing pressure on the reduced contact area against the allowable bearing capacity, using Meyerhof bearing capacity factors with depth corrections per AS 4678.

## Existing Deterministic Contract

- Parameters: `8`
- Outputs: `5`
- Archetypes: `5`
- Visibility mix: all_given; partial
- Hidden parameters: `soil_cohesion_kpa`, `soil_friction_angle_deg`, `soil_unit_weight_kn_m3`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `base_width_m` | Base width of the retaining wall footing B | float / m | range=1.0..6.0 |
| `total_vertical_load_kn_per_m` | Total vertical load on wall base per metre run V | float / kN/m | range=20..500 |
| `net_moment_knm_per_m` | Net moment about base toe per metre run M | float / kN.m/m | range=10..800 |
| `soil_cohesion_kpa` | Foundation soil effective cohesion c' | float / kPa | range=0..150; derivable_from=archetype |
| `soil_friction_angle_deg` | Foundation soil effective friction angle phi' | float / degrees | range=0..50; derivable_from=archetype |
| `soil_unit_weight_kn_m3` | Foundation soil unit weight gamma | float / kN/m³ | range=14..23; derivable_from=archetype |
| `embedment_depth_m` | Embedment depth of wall base below ground surface Df | float / m | range=0.3..3.0 |
| `allowable_bearing_capacity_kpa` | Allowable bearing capacity of the foundation soil q_all | float / kPa | range=50..600 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `eccentricity_m` | Eccentricity of resultant from base centre e (m) |  | tolerance=0.03 |
| `effective_width_m` | Meyerhof effective base width B' (m) |  | tolerance=0.03 |
| `max_bearing_pressure_kpa` | Maximum bearing pressure q_max (kPa) |  | tolerance=0.03 |
| `ultimate_bearing_capacity_kpa` | Ultimate bearing capacity q_ult (kPa) |  | tolerance=0.05 |
| `factor_of_safety` | Factor of safety against bearing failure FoS |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `soft_nc_clay` | Soft normally consolidated clay | brisbane-alluvial; darwin-estuarine |
| `medium_dense_sand` | Medium dense sand | perth-coastal; hunter-valley-alluvial |
| `stiff_oc_clay` | Stiff overconsolidated clay | sydney-hawkesbury; adelaide-stiff; melbourne-basalt |
| `dense_sand` | Dense sand | perth-coastal; cairns-coral |
| `firm_clay` | Firm clay | brisbane-alluvial; melbourne-basalt |

### Difficulty Notes

```text
easy: all_given | All parameters given, stiff soil, low eccentricity expected
medium: all_given | All parameters given, any soil type including soft clay
hard: partial | hidden=soil_cohesion_kpa, soil_friction_angle_deg, soil_unit_weight_kn_m3 | Soil parameters hidden, agent must infer from site description
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
