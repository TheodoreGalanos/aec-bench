# ABOUTME: First-pass task-world opportunity card for wave-runup.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / wave-overtopping / wave-runup

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/wave_runup`
- Discipline: `civil`
- Category: `wave-overtopping`
- Tool mode: `both`
- Standards: EurOtop (2018); TAW Guidelines
- Tags: coastal; wave; runup; overtopping; breakwater; dike

## Current Task Shape

Calculates the 2% exceedance wave runup height Ru2% on sloped coastal structures using the EurOtop (2018) TAW formula, which evaluates both breaking and surging runup expressions and takes the governing (minimum) value. Accounts for structure slope, surface roughness, and berm geometry to determine freeboard requirements for dikes, seawalls, and breakwaters.

## Existing Deterministic Contract

- Parameters: `5`
- Outputs: `3`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `berm_factor`, `roughness_factor`, `wave_period_s`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `wave_height_m` | Significant spectral wave height H_m0 | float / m | range=0.3..6.0 |
| `wave_period_s` | Spectral wave period T_m-1,0 | float / s | range=3.0..16.0; derivable_from=archetype |
| `structure_slope` | Structure slope tan(alpha), e.g. 0.33 for 1:3 slope | float / - | range=0.1..0.75 |
| `roughness_factor` | Roughness reduction factor gamma_f (1.0 = smooth, lower = rougher) | float / - | range=0.35..1.0; derivable_from=archetype |
| `berm_factor` | Berm reduction factor gamma_b (1.0 = no berm, lower = larger berm) | float / - | range=0.6..1.0; derivable_from=archetype |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `breaker_parameter` | Breaker parameter (Iribarren number) xi_m-1,0 |  | tolerance=0.05 |
| `runup_height_m` | 2% exceedance wave runup height Ru2% (m) |  | tolerance=0.05 |
| `regime` | Wave regime: 1.0 = breaking/plunging, 2.0 = surging/non-breaking |  | tolerance=0.01 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `smooth_dike` | Smooth concrete or asphalt dike with gentle seaward slope | dutch-north-sea-dike; thames-estuary-embankment; brisbane-river-levee |
| `rock_armour_revetment` | Double-layer rock armour revetment on steep slope | gold-coast-revetment; newcastle-foreshore-armour; darwin-seawall |
| `concrete_seawall` | Stepped or smooth concrete seawall with moderate roughness | sydney-harbour-seawall; adelaide-glenelg-wall; cairns-esplanade-wall |
| `rubble_mound_breakwater` | Rubble mound breakwater with rough two-layer armor | fremantle-outer-breakwater; townsville-port-breakwater; portland-harbour-arm |

### Difficulty Notes

```text
easy: all_given | Moderate waves on smooth structure — all parameters given, straightforward calculation
medium: all_given | Larger waves on rough structures — all parameters given, more complex conditions
hard: partial | hidden=roughness_factor, berm_factor, wave_period_s | Roughness and berm factors hidden — agent must infer from site description
```

## Multimodal Expansion

Candidate modality families: `spatial-map`, `chart-curve`, `tabular-source`.

Use beach profiles, tide/wave tables, shoreline maps, spectra, and coastal cross-sections.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Boundary-condition tasks can feed coastal drainage, outfall, armor, runup, and overtopping worlds.

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
