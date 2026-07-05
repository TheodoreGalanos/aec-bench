# ABOUTME: First-pass task-world opportunity card for wave-shoaling.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / wave-climate / wave-shoaling

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/wave_shoaling`
- Discipline: `civil`
- Category: `wave-climate`
- Tool mode: `both`
- Standards: USACE Coastal Engineering Manual (CEM); Fenton & McKee 1990
- Tags: coastal; wave; shoaling; refraction; nearshore

## Current Task Shape

Transforms deep-water wave height to nearshore conditions by computing shoaling coefficient K_s and refraction coefficient K_r, yielding H = H_0 * K_s * K_r. Uses the Fenton and McKee (1990) explicit dispersion relation approximation to avoid iterative wavelength solutions, and applies Snell's law for wave angle refraction per the USACE Coastal Engineering Manual.

## Existing Deterministic Contract

- Parameters: `4`
- Outputs: `3`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `deep_water_wave_angle_deg`, `wave_period_s`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `deep_water_wave_height_m` | Deep-water significant wave height H_0 | float / m | range=0.3..8.0 |
| `wave_period_s` | Wave period T | float / s | range=3.0..18.0; derivable_from=archetype |
| `nearshore_depth_m` | Water depth at the nearshore location d | float / m | range=0.5..30.0 |
| `deep_water_wave_angle_deg` | Deep-water wave crest angle to bottom contour theta_0 | float / degrees | range=0..80; derivable_from=archetype |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `shoaling_coefficient` | Shoaling coefficient K_s (dimensionless) |  | tolerance=0.03 |
| `refraction_coefficient` | Refraction coefficient K_r (dimensionless) |  | tolerance=0.03 |
| `nearshore_wave_height_m` | Nearshore wave height H (m) |  | tolerance=0.05 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `open_coast_normal` | Open coast with waves arriving nearly perpendicular to shoreline | gold-coast-open-beach; bondi-beach-nsw; cottesloe-beach-wa |
| `oblique_approach` | Coast with waves arriving at a significant oblique angle | byron-bay-headland; noosa-heads-refraction; port-stephens-oblique |
| `sheltered_bay` | Semi-enclosed bay with reduced wave energy and moderate refraction | jervis-bay-nsw; moreton-bay-qld; princess-royal-harbour-wa |
| `reef_shelf` | Shallow reef platform with rapid depth transition and strong refraction | ningaloo-reef-wa; great-barrier-reef-outer; heron-island-reef |

### Difficulty Notes

```text
easy: all_given | Normal incidence with moderate depth — all parameters given, straightforward calculation
medium: all_given | Oblique approach or reef shelf — all parameters given, refraction effects significant
hard: partial | hidden=wave_period_s, deep_water_wave_angle_deg | Wave period and approach angle hidden — agent must infer from site description
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
