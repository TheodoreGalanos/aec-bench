# ABOUTME: First-pass task-world opportunity card for spt-corrections.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# ground / soil-interpretation / spt-corrections

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/ground/spt_corrections`
- Discipline: `ground`
- Category: `soil-interpretation`
- Tool mode: `with-tool`
- Standards: Liao and Whitman (1986); ASTM D1586
- Tags: geotechnical; spt; deterministic

## Current Task Shape

Applies standard corrections to raw SPT blow counts following the Liao and Whitman (1986) procedure per ASTM D1586 practice. Applies energy (CE), borehole diameter (CB), sampler (CS), and rod length (CR) corrections to obtain N60, then normalizes to a reference overburden pressure of 100 kPa using CN = sqrt(Pa/sigma'v) to produce the corrected (N1)60 value for liquefaction and strength correlations.

## Existing Deterministic Contract

- Parameters: `6`
- Outputs: `7`
- Archetypes: `3`
- Visibility mix: all_given; partial
- Hidden parameters: `borehole_diameter_mm`, `hammer_type`, `sampler_type`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `raw_n_value` | Raw field-measured SPT blow count | int | range=5..60 |
| `effective_overburden_kpa` | Effective overburden stress at test depth | float / kPa | range=10..400 |
| `hammer_type` | SPT hammer type | enum | values=auto, safety, donut |
| `borehole_diameter_mm` | Borehole diameter | enum | values=65, 115, 150, 200 |
| `sampler_type` | Sampler liner configuration | enum | values=with_liner, without_liner |
| `rod_length_m` | Total rod length from surface to sampler | float / m | range=3..30 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `ce` | Energy correction factor CE |  | tolerance=0.01 |
| `cb` | Borehole diameter correction factor CB |  | tolerance=0.01 |
| `cs` | Sampler correction factor CS |  | tolerance=0.01 |
| `cr` | Rod length correction factor CR |  | tolerance=0.01 |
| `n60` | Energy-corrected N-value N60 |  | tolerance=0.03 |
| `cn` | Overburden correction factor CN |  | tolerance=0.03 |
| `n1_60` | Normalised corrected N-value (N1)60 |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `shallow_loose` | Shallow test in loose material | brisbane-alluvial; darwin-estuarine |
| `medium_depth` | Typical mid-depth test | sydney-hawkesbury; melbourne-basalt; hunter-valley-alluvial |
| `deep_dense` | Deep test in dense stratum | perth-coastal; adelaide-stiff; cairns-coral |

### Difficulty Notes

```text
easy: all_given | Standard auto hammer, standard borehole, all params given
medium: all_given | Any equipment combination, all params given
hard: partial | hidden=hammer_type, sampler_type, borehole_diameter_mm | Equipment parameters hidden, agent infers from context
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
