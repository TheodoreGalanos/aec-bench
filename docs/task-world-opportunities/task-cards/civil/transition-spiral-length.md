# ABOUTME: First-pass task-world opportunity card for transition-spiral-length.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / track-geometry / transition-spiral-length

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/transition_spiral_length`
- Discipline: `civil`
- Category: `track-geometry`
- Tool mode: `with-tool`
- Standards: ARTC ETS-05-00; AREMA MRE Chapter 5; EN 13803
- Tags: civil; rail; track-geometry; spiral; transition; cant; deterministic

## Current Task Shape

Determines the governing minimum transition spiral length at rail curve entries by evaluating three independent criteria: cant runoff rate, cant deficiency rate of change, and twist limit. The maximum of L_cant, L_cd, and L_twist governs, ensuring passenger comfort and track stability per ARTC ETS-05-00 and AREMA Chapter 5.

## Existing Deterministic Contract

- Parameters: `6`
- Outputs: `4`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `min_twist_ratio`, `rate_of_change_cant_mm_s`, `rate_of_change_cd_mm_s`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `actual_cant_mm` | Applied (actual) cant E_a | float / mm | range=0..150 |
| `cant_deficiency_mm` | Cant deficiency C_d at design speed | float / mm | range=0..110 |
| `max_speed_km_h` | Maximum operating speed V_max | float / km/h | range=20..250 |
| `rate_of_change_cant_mm_s` | Maximum rate of change of cant D_cant | float / mm/s | range=25..55; derivable_from=archetype |
| `rate_of_change_cd_mm_s` | Maximum rate of change of cant deficiency D_cd | float / mm/s | range=25..55; derivable_from=archetype |
| `min_twist_ratio` | Minimum twist ratio (e.g. 400 means 1 mm cant per 400 mm length) | float / - | range=400..800; derivable_from=archetype |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `spiral_length_cant_m` | Minimum spiral length from cant runoff criterion (m) |  | tolerance=0.03 |
| `spiral_length_cd_m` | Minimum spiral length from cant deficiency rate criterion (m) |  | tolerance=0.03 |
| `spiral_length_twist_m` | Minimum spiral length from twist rate criterion (m) |  | tolerance=0.03 |
| `governing_spiral_length_m` | Governing (maximum) minimum spiral length (m) |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `urban_metro` | Urban metro or light rail line with tight curves and frequent stops | sydney-metro-northwest; melbourne-metro-tunnel; brisbane-cross-river-rail |
| `mainline_freight` | Mainline freight corridor with gentle curves and heavy axle loads | artc-hunter-valley-coal; artc-north-south-corridor; pilbara-iron-ore-wa |
| `high_speed_passenger` | High-speed passenger rail corridor with sweeping curves | sydney-melbourne-hsr; brisbane-gold-coast-fast-rail; perth-bunbury-fast-rail |
| `branch_line` | Regional branch line with moderate curves and mixed traffic | nsw-north-coast-line; vic-geelong-warrnambool; qld-western-line |

### Difficulty Notes

```text
easy: all_given | All parameters given, gentle curves on mainline or branch line
medium: all_given | All parameters given, any corridor type including tight metro curves and high speed
hard: partial | hidden=rate_of_change_cant_mm_s, rate_of_change_cd_mm_s, min_twist_ratio | Rate-of-change limits and twist ratio hidden — agent must infer from corridor type and operating context
```

## Multimodal Expansion

Candidate modality families: `spatial-map`, `tabular-source`, `time-series`.

Use catchment plans, rainfall tables, hyetographs, and drainage schedules as source artifacts.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Connect rainfall/runoff outputs to detention, pipe, HGL, outlet, and water-quality checks.

First-pass composition tags: `shared-context`, `pipeline`, `evidence-assembly`.

## Meta-Harness Handles

Candidate operation handles: `parameters`, `outputs`, `difficulty`, `archetype`, `evidence_profile`, `hidden_parameter_policy`, `source_geometry`, `source_table`, `source_timeseries`.

Practical operations to consider:

- `projection`: isolate the arithmetic-only world, source-interpretation world, or evidence-review world.
- `difference`: remove visible parameters, calculator access, source labels, or intermediate hints.
- `subset`: restrict to one archetype, standard, modality, or difficulty tier.
- `product`: compose with a downstream or upstream task that consumes/produces compatible engineering quantities.

## Repair/Event Candidates

- Trigger `evidence_profile` repair if the model reaches the right number without citing or preserving the source artifact.
- Trigger `verifier` repair if final-output tolerances pass while intermediate units, assumptions, or handoff values are inconsistent.
- Trigger `world_schema` repair if a promising composition lacks explicit handoff fields or operation handles.
