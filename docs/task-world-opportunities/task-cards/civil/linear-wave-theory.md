# ABOUTME: First-pass task-world opportunity card for linear-wave-theory.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / wave-climate / linear-wave-theory

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/linear_wave_theory`
- Discipline: `civil`
- Category: `wave-climate`
- Tool mode: `both`
- Standards: USACE Coastal Engineering Manual (CEM)
- Tags: coastal; wave; dispersion; wavelength; celerity; group-velocity

## Current Task Shape

Solves the linear wave dispersion relation using Newton-Raphson iteration to compute wavelength, phase celerity, and group velocity for monochromatic waves. Also derives wave steepness and relative depth (d/L) for water depth classification. Follows the USACE Coastal Engineering Manual Part II Chapter 1 formulation applicable across deep, intermediate, and shallow water regimes.

## Existing Deterministic Contract

- Parameters: `3`
- Outputs: `5`
- Archetypes: `5`
- Visibility mix: all_given; partial
- Hidden parameters: `wave_period_s`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `wave_period_s` | Wave period T | float / s | range=3.0..18.0 |
| `water_depth_m` | Water depth d | float / m | range=0.5..100.0 |
| `wave_height_m` | Wave height H | float / m | range=0.1..10.0; derivable_from=archetype |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `wavelength_m` | Wavelength L (m) |  | tolerance=0.05 |
| `wave_celerity_m_per_s` | Wave phase celerity C = L / T (m/s) |  | tolerance=0.05 |
| `group_velocity_m_per_s` | Group velocity C_g = n * C (m/s) |  | tolerance=0.05 |
| `wave_steepness` | Wave steepness S = H / L (dimensionless) |  | tolerance=0.02 |
| `relative_depth` | Relative depth d/L (dimensionless); >0.5 deep, <0.05 shallow, else intermediate |  | tolerance=0.02 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `deep_ocean_swell` | Deep ocean swell with long period waves in open water | tasman-sea-offshore; great-australian-bight; coral-sea-deep |
| `continental_shelf` | Continental shelf with moderate depth and intermediate-period waves | gold-coast-shelf; sydney-offshore-buoy; perth-canyon-approach |
| `nearshore_approach` | Nearshore zone with waves approaching the coastline | bondi-beach-nearshore; manly-surf-zone; noosa-heads-approach |
| `shallow_estuary` | Shallow estuary or harbour entrance with short-period waves | moreton-bay-entrance; darwin-harbour-channel; port-phillip-heads |
| `reef_platform` | Shallow reef platform with long-period ocean swell | ningaloo-reef-flat; great-barrier-reef-lagoon; heron-island-platform |

### Difficulty Notes

```text
easy: all_given | Moderate period and depth — all parameters given, straightforward dispersion solve
medium: all_given | Extreme depth ratio conditions — all parameters given, deep or very shallow regime
hard: partial | hidden=wave_period_s | Wave period hidden — agent must estimate from wave height via empirical wind-wave relationships (T approx 3.5-5.5 * sqrt(H))
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
