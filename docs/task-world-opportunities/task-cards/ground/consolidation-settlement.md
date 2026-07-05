# ABOUTME: First-pass task-world opportunity card for consolidation-settlement.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# ground / shallow-foundations / consolidation-settlement

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/ground/consolidation_settlement`
- Discipline: `ground`
- Category: `shallow-foundations`
- Tool mode: `with-tool`
- Standards: Terzaghi 1D consolidation theory
- Tags: geotechnical; settlement; consolidation; clay; deterministic

## Current Task Shape

Estimates primary consolidation settlement of clay layers under applied loading using Terzaghi's one-dimensional theory. Handles normally consolidated, overconsolidated, and transitional cases via the compression index (Cc) and recompression index (Cr) on the e-log-p curve, with settlement governed by Sc = CcH/(1+e0) * log10(sigma_vf/sigma_v0) and its variants.

## Existing Deterministic Contract

- Parameters: `7`
- Outputs: `2`
- Archetypes: `3`
- Visibility mix: all_given; partial
- Hidden parameters: `compression_index_cc`, `initial_void_ratio_e0`, `recompression_index_cr`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `clay_thickness_m` | Clay layer thickness H | float / m | range=1.0..20.0 |
| `compression_index_cc` | Compression index Cc | float | range=0.1..1.5; derivable_from=archetype |
| `recompression_index_cr` | Recompression index Cr | float | range=0.01..0.15; derivable_from=archetype |
| `initial_void_ratio_e0` | Initial void ratio e0 | float | range=0.5..3.0; derivable_from=archetype |
| `preconsolidation_pressure_kpa` | Preconsolidation pressure sigma'p | float / kPa | range=30..500 |
| `initial_effective_stress_kpa` | Initial effective overburden stress sigma'v0 | float / kPa | range=20..300 |
| `final_effective_stress_kpa` | Final effective stress after loading sigma'vf | float / kPa | range=50..600 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `ocr` | Overconsolidation ratio OCR |  | tolerance=0.03 |
| `settlement_mm` | Primary consolidation settlement Sc (mm) |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `soft_nc_clay` | Soft normally consolidated marine clay | brisbane-alluvial; darwin-estuarine; gladstone-marine |
| `medium_oc_clay` | Medium overconsolidated clay | sydney-hawkesbury; melbourne-brighton; adelaide-stiff |
| `stiff_oc_clay` | Stiff heavily overconsolidated clay | melbourne-basalt; canberra-stiff; perth-spearwood |

### Difficulty Notes

```text
easy: all_given | NC clay, all parameters given, single-case settlement
medium: all_given | OC clay, all parameters given, two-case settlement possible
hard: partial | hidden=compression_index_cc, recompression_index_cr, initial_void_ratio_e0 | Soil properties hidden, agent must determine Cc, Cr, e0 from site description
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
