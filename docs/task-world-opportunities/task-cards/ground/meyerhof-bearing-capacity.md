# ABOUTME: First-pass task-world opportunity card for meyerhof-bearing-capacity.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# ground / shallow-foundations / meyerhof-bearing-capacity

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/ground/meyerhof_bearing_capacity`
- Discipline: `ground`
- Category: `shallow-foundations`
- Tool mode: `with-tool`
- Standards: Meyerhof (1963)
- Tags: geotechnical; bearing-capacity; shallow-foundations; deterministic

## Current Task Shape

Computes ultimate and allowable bearing capacity of shallow foundations using Meyerhof's (1963) general bearing capacity equation: qu = c*Nc*sc*dc*ic + q*Nq*sq*dq*iq + 0.5*gamma*B*Ngamma*sgamma*dgamma*igamma. Applies shape, depth, and inclination correction factors for strip, rectangular, square, and circular footings under vertical or inclined loading conditions.

## Existing Deterministic Contract

- Parameters: `9`
- Outputs: `14`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `cohesion_kpa`, `friction_angle_deg`, `unit_weight_kn_m3`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `cohesion_kpa` | Effective cohesion c' | float / kPa | range=0..150; derivable_from=archetype |
| `friction_angle_deg` | Effective friction angle phi' | float / degrees | range=0..50; derivable_from=archetype |
| `unit_weight_kn_m3` | Soil unit weight gamma | float / kN/m³ | range=14..23; derivable_from=archetype |
| `footing_width_m` | Footing width B (shorter dimension) | float / m | range=0.5..10.0 |
| `footing_length_m` | Footing length L (longer dimension, L >= B) | float / m | range=0.5..30.0 |
| `embedment_depth_m` | Foundation embedment depth Df | float / m | range=0.3..5.0 |
| `footing_shape` | Footing shape | enum | values=strip, rectangular, square, circular |
| `load_inclination_deg` | Load inclination angle from vertical | float / degrees | range=0..20 |
| `factor_of_safety` | Factor of safety for allowable capacity | float | range=2.0..4.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `nc` | Bearing capacity factor Nc |  | tolerance=0.03 |
| `nq` | Bearing capacity factor Nq |  | tolerance=0.03 |
| `ngamma` | Bearing capacity factor Ngamma |  | tolerance=0.03 |
| `sc` | Shape factor sc |  | tolerance=0.03 |
| `sq` | Shape factor sq |  | tolerance=0.03 |
| `sgamma` | Shape factor sgamma |  | tolerance=0.03 |
| `dc` | Depth factor dc |  | tolerance=0.03 |
| `dq` | Depth factor dq |  | tolerance=0.03 |
| `dgamma` | Depth factor dgamma |  | tolerance=0.03 |
| `ic` | Inclination factor ic |  | tolerance=0.03 |
| `iq` | Inclination factor iq |  | tolerance=0.03 |
| `igamma` | Inclination factor igamma |  | tolerance=0.05 |
| `ultimate_bearing_capacity_kpa` | Ultimate bearing capacity qu (kPa) |  | tolerance=0.03 |
| `allowable_bearing_capacity_kpa` | Allowable bearing capacity qa (kPa) |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `soft_nc_clay` | Soft normally consolidated clay | brisbane-alluvial; darwin-estuarine |
| `medium_dense_sand` | Medium dense sand | perth-coastal; hunter-valley-alluvial |
| `stiff_oc_clay` | Stiff overconsolidated clay | sydney-hawkesbury; adelaide-stiff; melbourne-basalt |
| `dense_sand_gravel` | Dense sand and gravel | cairns-coral; newcastle-fill |

### Difficulty Notes

```text
easy: all_given | Vertical load, square footing, all parameters given
medium: all_given | Vertical or inclined load, any shape, all parameters given
hard: partial | hidden=cohesion_kpa, friction_angle_deg, unit_weight_kn_m3 | Some soil parameters hidden, inclined loading
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
