# ABOUTME: First-pass task-world opportunity card for fos-steady-state.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / slope-stability / fos-steady-state

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/fos_steady_state`
- Discipline: `civil`
- Category: `slope-stability`
- Tool mode: `with-tool`
- Standards: USACE EM 1110-2-1902; ANCOLD Guidelines on Design Criteria
- Tags: civil; dams; slope-stability; seepage; embankment; deterministic

## Current Task Shape

Computes the factor of safety against shallow translational failure on an embankment dam slope under steady-state seepage using the infinite slope method. The pore pressure ratio (ru) represents the phreatic surface location, and the balance of driving shear stress against Mohr-Coulomb resisting strength along the failure plane determines stability. Applicable to preliminary dam safety assessments per USACE EM 1110-2-1902 and ANCOLD guidelines.

## Existing Deterministic Contract

- Parameters: `6`
- Outputs: `3`
- Archetypes: `6`
- Visibility mix: all_given; partial
- Hidden parameters: `cohesion_kpa`, `friction_angle_deg`, `saturated_unit_weight_kn_m3`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `slope_angle_deg` | Embankment slope angle beta measured from horizontal | float / degrees | range=5.0..45.0 |
| `failure_depth_m` | Depth from slope surface to the failure plane z | float / m | range=0.5..10.0 |
| `cohesion_kpa` | Effective cohesion of embankment fill c' | float / kPa | range=0.0..50.0; derivable_from=archetype |
| `friction_angle_deg` | Effective friction angle of embankment fill phi' | float / degrees | range=10.0..45.0; derivable_from=archetype |
| `saturated_unit_weight_kn_m3` | Saturated unit weight of embankment fill gamma_sat | float / kN/m³ | range=17.0..23.0; derivable_from=archetype |
| `pore_pressure_ratio` | Pore pressure ratio ru = u / (gamma_sat * z) representing steady-state phreatic surface | float | range=0.0..0.6 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `fos` | Factor of safety against slope failure FoS (dimensionless) |  | tolerance=0.03 |
| `driving_stress_kpa` | Driving shear stress along the failure plane tau_d (kPa) |  | tolerance=0.03 |
| `resisting_stress_kpa` | Resisting shear stress along the failure plane tau_r (kPa) |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `compacted_clay_core` | Compacted clay core zone of a zoned earth dam | warragamba-dam-nsw; hume-dam-nsw-vic; dartmouth-dam-vic |
| `compacted_sandy_gravel_shell` | Compacted sandy gravel shell zone of a zoned earth dam | eildon-dam-vic; burdekin-falls-dam-qld; cotter-dam-act |
| `homogeneous_earth_fill` | Homogeneous earth fill embankment of a small to medium farm dam | darling-downs-farm-dam-qld; goulburn-valley-irrigation-dam-vic; hunter-valley-farm-dam-nsw |
| `laterite_residual` | Laterite residual soil fill used in tropical dam embankments | ross-river-dam-qld; tinaroo-falls-dam-qld |
| `weathered_rock_fill` | Weathered rock fill placed in the outer shell of a dam embankment | thomson-dam-vic; copeton-dam-nsw; hinze-dam-qld |
| `silty_sand_fill` | Silty sand fill used in homogeneous tailings dam embankments | bowen-basin-tailings-dam-qld; hunter-valley-tailings-dam-nsw |

### Difficulty Notes

```text
easy: all_given | Dry slope (ru=0), granular fill with no cohesion — simplest formula variant
medium: all_given | Seepage present (ru > 0) with cohesive fill — full formula with all parameters given
hard: partial | hidden=cohesion_kpa, friction_angle_deg, saturated_unit_weight_kn_m3 | Seepage present, soil properties hidden — agent must infer from site context and fill description
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
