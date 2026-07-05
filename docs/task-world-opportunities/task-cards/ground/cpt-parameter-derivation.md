# ABOUTME: First-pass task-world opportunity card for cpt-parameter-derivation.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# ground / soil-interpretation / cpt-parameter-derivation

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/ground/cpt_parameter_derivation`
- Discipline: `ground`
- Category: `soil-interpretation`
- Tool mode: `with-tool`
- Standards: Robertson (1990); Lunne et al. (1997); Robertson and Campanella (1983)
- Tags: geotechnical; cpt; soil-classification; deterministic

## Current Task Shape

Derives geotechnical design parameters from cone penetration test (CPTu) data using the Robertson (1990) classification framework. Computes corrected cone resistance qt, normalized parameters Qt and Fr, soil behavior type index Ic, and estimates undrained shear strength (via Nkt) for clay-like soils or friction angle for sand-like soils based on the Ic = 2.6 boundary.

## Existing Deterministic Contract

- Parameters: `7`
- Outputs: `7`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `net_area_ratio`, `total_unit_weight_kn_m3`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `qc_mpa` | Measured cone resistance | float / MPa | range=0.2..40.0 |
| `fs_kpa` | Measured sleeve friction | float / kPa | range=1.0..500.0 |
| `u2_kpa` | Measured pore water pressure at cone shoulder | float / kPa | range=-50.0..1500.0 |
| `depth_m` | Test depth below ground surface | float / m | range=1.0..40.0 |
| `total_unit_weight_kn_m3` | Total unit weight of soil | float / kN/m³ | range=14.0..22.0; derivable_from=archetype |
| `water_table_depth_m` | Depth to water table below ground surface | float / m | range=0.0..50.0 |
| `net_area_ratio` | Net area ratio of the cone (a) | float / - | range=0.55..0.85 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `qt_mpa` | Corrected cone resistance qt (MPa) |  | tolerance=0.03 |
| `friction_ratio_pct` | Friction ratio Rf (%) |  | tolerance=0.05 |
| `qt_norm` | Normalized cone resistance Qt |  | tolerance=0.05 |
| `fr_norm` | Normalized friction ratio Fr (%) |  | tolerance=0.05 |
| `ic` | Soil behavior type index Ic (Robertson 1990) |  | tolerance=0.05 |
| `su_kpa` | Estimated undrained shear strength Su (kPa), 0 if sand-like |  | tolerance=0.05 |
| `phi_deg` | Estimated friction angle phi' (degrees), 0 if clay-like |  | tolerance=0.05 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `soft_clay` | Soft normally consolidated clay with high pore pressure | brisbane-alluvial; darwin-estuarine; cairns-coastal |
| `stiff_clay` | Stiff overconsolidated clay | sydney-shale; melbourne-basalt; adelaide-stiff |
| `medium_sand` | Medium dense clean sand | perth-coastal; gold-coast-dune; newcastle-sand |
| `dense_sand` | Dense to very dense sand or gravel | hunter-valley-alluvial; perth-limestone; sydney-hawkesbury |

### Difficulty Notes

```text
easy: all_given | All parameters given, soft clay or medium sand archetypes
medium: all_given | All parameters given, any soil archetype
hard: partial | hidden=total_unit_weight_kn_m3, net_area_ratio | Unit weight and net area ratio hidden, agent infers from context
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
