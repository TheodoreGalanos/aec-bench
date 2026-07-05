# ABOUTME: First-pass task-world opportunity card for exit-gradient.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / seepage-analysis / exit-gradient

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/exit_gradient`
- Discipline: `civil`
- Category: `seepage-analysis`
- Tool mode: `with-tool`
- Standards: USACE EM 1110-2-1901; FEMA P-1032
- Tags: civil; dams; seepage; piping; gradient; hydraulics

## Current Task Shape

Computes the exit hydraulic gradient at a dam or levee downstream toe using i_exit = delta_h / L_seepage, and the critical gradient for piping initiation from i_cr = (G_s - 1) / (1 + e), per USACE EM 1110-2-1901. Derives the factor of safety against piping and the saturated and buoyant unit weights of the foundation soil. Used in dam safety and geotechnical seepage analysis.

## Existing Deterministic Contract

- Parameters: `5`
- Outputs: `5`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `foundation_soil_type`, `specific_gravity`, `void_ratio`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `head_difference_m` | Head difference across the structure (upstream pool minus tailwater level) | float / m | range=0.5..40.0 |
| `seepage_path_length_m` | Total seepage path length through the foundation from upstream to downstream toe | float / m | range=5.0..300.0 |
| `specific_gravity` | Specific gravity of foundation soil solids G_s | float | range=2.55..2.8; derivable_from=archetype |
| `void_ratio` | Void ratio of the foundation soil e | float | range=0.25..1.1; derivable_from=archetype |
| `foundation_soil_type` | Foundation soil classification | enum | values=clean_sand, silty_sand, sandy_silt, clayey_silt, silty_clay; derivable_from=archetype |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `exit_gradient` | Exit gradient at the downstream toe i_exit (dimensionless) |  | tolerance=0.03 |
| `critical_gradient` | Critical hydraulic gradient for piping initiation i_cr (dimensionless) |  | tolerance=0.03 |
| `factor_of_safety` | Factor of safety against piping FoS = i_cr / i_exit (dimensionless) |  | tolerance=0.03 |
| `saturated_unit_weight_kn_m3` | Saturated unit weight of foundation soil gamma_sat (kN/m3) |  | tolerance=0.03 |
| `buoyant_unit_weight_kn_m3` | Buoyant (submerged) unit weight of foundation soil gamma_b (kN/m3) |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `earth_dam_sand` | Earth embankment dam on clean sand foundation with moderate head | darling-downs-farm-dam; hunter-valley-irrigation-dam |
| `concrete_gravity_dam` | Concrete gravity dam on silty sand foundation with high head | snowy-mountains-hydro-dam; tasmania-power-dam |
| `levee_alluvial` | Levee on alluvial soil foundation with low to moderate head | murray-river-levee; fitzroy-river-flood-levee |
| `sheet_pile_cofferdam` | Sheet pile cofferdam on sandy foundation with low head | sydney-harbour-cofferdam; brisbane-river-cofferdam |

### Difficulty Notes

```text
easy: all_given | Simple earth dam scenario, all parameters given including soil properties
medium: all_given | All parameters given, wider range of structure types and soil conditions
hard: partial | hidden=specific_gravity, void_ratio, foundation_soil_type | Specific gravity, void ratio, and soil type hidden; agent infers from site context
```

## Multimodal Expansion

Candidate modality families: `drawing-geometry`, `tabular-source`, `chart-curve`.

Use network schematics, long sections, asset schedules, rating curves, and source tables.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Pipe and channel outputs naturally feed pump station, detention, outfall, and flood-level checks.

First-pass composition tags: `shared-context`, `pipeline`, `evidence-assembly`.

## Meta-Harness Handles

Candidate operation handles: `parameters`, `outputs`, `difficulty`, `archetype`, `evidence_profile`, `hidden_parameter_policy`, `source_geometry`, `source_table`, `source_curve`.

Practical operations to consider:

- `projection`: isolate the arithmetic-only world, source-interpretation world, or evidence-review world.
- `difference`: remove visible parameters, calculator access, source labels, or intermediate hints.
- `subset`: restrict to one archetype, standard, modality, or difficulty tier.
- `product`: compose with a downstream or upstream task that consumes/produces compatible engineering quantities.

## Repair/Event Candidates

- Trigger `evidence_profile` repair if the model reaches the right number without citing or preserving the source artifact.
- Trigger `verifier` repair if final-output tolerances pass while intermediate units, assumptions, or handoff values are inconsistent.
- Trigger `world_schema` repair if a promising composition lacks explicit handoff fields or operation handles.
