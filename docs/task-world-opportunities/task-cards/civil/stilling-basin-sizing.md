# ABOUTME: First-pass task-world opportunity card for stilling-basin-sizing.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / spillway-hydraulics / stilling-basin-sizing

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/stilling_basin_sizing`
- Discipline: `civil`
- Category: `spillway-hydraulics`
- Tool mode: `with-tool`
- Standards: USBR Hydraulic Design of Stilling Basins; USACE EM 1110-2-1603
- Tags: civil; hydraulics; dams; spillway; stilling-basin; energy-dissipation

## Current Task Shape

Estimates the required stilling basin length for energy dissipation downstream of a spillway using USBR hydraulic design methods. Calculates the entry Froude number, derives the sequent (conjugate) depth from the Belanger equation d2 = (d1/2)*(sqrt(1+8*Fr^2)-1), then selects the appropriate USBR basin type (I, II, or III) and corresponding basin length factor.

## Existing Deterministic Contract

- Parameters: `3`
- Outputs: `4`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `tailwater_depth_m`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `unit_discharge_m3_s_m` | Unit discharge at the spillway toe q (discharge per metre width) | float / m³/s/m | range=0.5..80.0 |
| `drop_height_m` | Vertical drop height from reservoir level to basin floor ΔH | float / m | range=1.0..50.0 |
| `tailwater_depth_m` | Tailwater depth downstream of the basin d_tw | float / m | range=0.0..20.0; derivable_from=archetype |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `froude_number` | Froude number at basin entry Fr₁ |  | tolerance=0.03 |
| `sequent_depth_m` | Sequent (conjugate) depth from Belanger equation d₂ (m) |  | tolerance=0.03 |
| `basin_length_m` | Required stilling basin length L_basin (m) |  | tolerance=0.03 |
| `basin_type` | USBR basin type code (0.0 = none, 1.0 = Type I, 2.0 = Type II, 3.0 = Type III) |  | tolerance=0.01 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `low_weir` | Low overflow weir or small check dam with moderate unit discharge | victoria-farm-dam-weir; south-australia-creek-weir |
| `medium_dam` | Medium-height dam spillway with significant energy to dissipate | nsw-water-supply-dam; queensland-irrigation-dam |
| `high_dam` | High dam spillway with large energy head and high Froude number flow | snowy-mountains-major-dam; north-queensland-flood-dam |
| `overflow_structure` | Low-head overflow structure or diversion weir with small drop | western-australia-diversion-weir; tasmania-small-hydro-outlet |

### Difficulty Notes

```text
easy: all_given | Low weir with all parameters given, straightforward Froude calculation
medium: all_given | Medium to high dam, all parameters given, wider range of Froude numbers and basin types
hard: partial | hidden=tailwater_depth_m | Tailwater depth hidden; agent must infer from site context and typical downstream conditions
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
