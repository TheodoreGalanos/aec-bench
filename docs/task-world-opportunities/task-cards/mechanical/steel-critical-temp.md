# ABOUTME: First-pass task-world opportunity card for steel-critical-temp.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# mechanical / structural-fire / steel-critical-temp

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/mechanical/steel_critical_temp`
- Discipline: `mechanical`
- Category: `structural-fire`
- Tool mode: `with-tool`
- Standards: Eurocode 3; AS 4100
- Tags: mechanical; structural-fire; steel-temperature; fire-resistance; deterministic

## Current Task Shape

Calculates steel critical temperature from an explicit fire design load ratio using the Eurocode-style relationship theta_cr = 39.19 ln(1/(0.9674 mu^3.833) - 1) + 482. The template reports the critical temperature, margin to a protection trigger, and a numeric protection requirement indicator.

## Existing Deterministic Contract

- Parameters: `2`
- Outputs: `3`
- Archetypes: `3`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `load_ratio` | Design load effect divided by ambient-temperature resistance | float | range=0.05..0.95 |
| `protection_trigger_c` | Critical temperature threshold below which fire protection is required | float / C | range=350.0..650.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `critical_temperature_c` | Critical steel temperature |  | tolerance=0.03 |
| `protection_margin_c` | Critical temperature minus protection trigger temperature |  | tolerance=0.03 |
| `protection_required` | Numeric fire protection requirement indicator: 0 no, 1 yes |  | tolerance=0.01 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `low_utilisation_member` | Low-utilisation steel member with reserve ambient capacity | secondary-floor-beam; light-industrial-platform |
| `moderate_utilisation_member` | Moderately utilised steel member in a fire-rated zone | commercial-frame-beam; plant-room-support-steel |
| `high_utilisation_member` | Highly utilised steel member with low reserve fire capacity | transfer-girder; heavily-loaded-column |

### Difficulty Notes

```text
easy: all_given | All parameters given for a low-utilisation member
medium: all_given | All parameters given across low and moderate utilisation members
hard: all_given | All parameters given for moderate and high utilisation members
```

## Multimodal Expansion

Candidate modality families: `drawing-geometry`, `tabular-source`, `document-evidence`.

Use building elevations, terrain/zone diagrams, load schedules, and standards extracts.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Wind-speed and pressure derivations can feed structural member, bracket, cladding, and foundation checks.

First-pass composition tags: `shared-context`, `pipeline`, `evidence-assembly`.

## Meta-Harness Handles

Candidate operation handles: `parameters`, `outputs`, `difficulty`, `archetype`, `evidence_profile`, `source_geometry`, `source_table`.

Practical operations to consider:

- `projection`: isolate the arithmetic-only world, source-interpretation world, or evidence-review world.
- `difference`: remove visible parameters, calculator access, source labels, or intermediate hints.
- `subset`: restrict to one archetype, standard, modality, or difficulty tier.
- `product`: compose with a downstream or upstream task that consumes/produces compatible engineering quantities.

## Repair/Event Candidates

- Trigger `evidence_profile` repair if the model reaches the right number without citing or preserving the source artifact.
- Trigger `verifier` repair if final-output tolerances pass while intermediate units, assumptions, or handoff values are inconsistent.
- Trigger `world_schema` repair if a promising composition lacks explicit handoff fields or operation handles.
