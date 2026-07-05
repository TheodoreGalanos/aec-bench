# ABOUTME: First-pass task-world opportunity card for wave-breaking.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / wave-climate / wave-breaking

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/wave_breaking`
- Discipline: `civil`
- Category: `wave-climate`
- Tool mode: `both`
- Standards: USACE Coastal Engineering Manual (CEM); Weggel 1972
- Tags: coastal; wave; breaking; iribarren; surf

## Current Task Shape

Evaluates wave breaking conditions using the Weggel (1972) breaker depth index gamma_b to compute depth-limited breaking wave height H_b = gamma_b * d, then classifies breaker type (spilling, plunging, or surging) via the Iribarren surf similarity parameter. Used in coastal structure design and nearshore hazard assessment per the USACE Coastal Engineering Manual.

## Existing Deterministic Contract

- Parameters: `4`
- Outputs: `4`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `bottom_slope`, `wave_period_s`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `wave_height_m` | Incident (deep-water) wave height H_0 | float / m | range=0.3..8.0 |
| `wave_period_s` | Wave period T | float / s | range=3.0..18.0; derivable_from=archetype |
| `water_depth_m` | Water depth at location of interest d | float / m | range=0.3..15.0 |
| `bottom_slope` | Bottom slope m (rise/run ratio, dimensionless) | float / - | range=0.005..0.2 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `breaking_wave_height_m` | Depth-limited breaking wave height H_b (m) |  | tolerance=0.03 |
| `breaking_depth_m` | Breaking depth d_b (m) |  | tolerance=0.03 |
| `breaker_type` | Breaker type: 1.0 = spilling, 2.0 = plunging, 3.0 = surging |  | tolerance=0.01 |
| `iribarren_number` | Iribarren number (surf similarity parameter) xi |  | tolerance=0.05 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `gentle_sandy_beach` | Gentle sandy beach with long flat approach | gold-coast-open-beach; byron-bay-sandy-shore; glenelg-beach-sa |
| `moderate_beach` | Moderate-slope beach with mixed sand and gravel | manly-beach-nsw; cottesloe-beach-wa; torquay-surf-coast |
| `steep_reef` | Steep reef or rocky platform with abrupt depth transition | ningaloo-reef-wa; great-barrier-reef-outer; norfolk-island-reef |
| `harbour_breakwater` | Harbour breakwater toe with constructed slope | fremantle-port-breakwater; townsville-harbour-arm; darwin-east-arm-wharf |

### Difficulty Notes

```text
easy: all_given | Moderate wave and slope — all parameters given, straightforward calculation
medium: all_given | Larger waves or steeper slopes — all parameters given, more extreme conditions
hard: partial | hidden=wave_period_s, bottom_slope | Wave period and bottom slope hidden — agent must infer from site description
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
