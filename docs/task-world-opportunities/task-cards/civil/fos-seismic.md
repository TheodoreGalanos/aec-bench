# ABOUTME: First-pass task-world opportunity card for fos-seismic.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / slope-stability / fos-seismic

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/fos_seismic`
- Discipline: `civil`
- Category: `slope-stability`
- Tool mode: `with-tool`
- Standards: USACE EM 1110-2-1902; ICOLD Bulletin 148
- Tags: civil; dams; slope-stability; seismic; pseudo-static; geotechnical

## Current Task Shape

Computes the factor of safety for embankment or natural slopes subjected to earthquake inertia forces using the pseudo-static infinite slope method per USACE EM 1110-2-1902 and ICOLD Bulletin 148. Applies horizontal and vertical seismic coefficients to the sliding mass, accounts for pore water pressure via the pore pressure ratio ru, and derives the yield acceleration ky at which FoS reaches unity.

## Existing Deterministic Contract

- Parameters: `8`
- Outputs: `3`
- Archetypes: `6`
- Visibility mix: all_given; partial
- Hidden parameters: `cohesion_kpa`, `friction_angle_deg`, `unit_weight_kn_m3`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `slope_angle_deg` | Slope angle beta measured from horizontal | float / degrees | range=5..45 |
| `slip_depth_m` | Depth to the slip surface measured vertically from the slope face | float / m | range=1.0..20.0 |
| `cohesion_kpa` | Effective cohesion c' of the embankment material | float / kPa | range=0..80; derivable_from=archetype |
| `friction_angle_deg` | Effective friction angle phi' of the embankment material | float / degrees | range=0..45; derivable_from=archetype |
| `unit_weight_kn_m3` | Bulk unit weight of the embankment material gamma | float / kN/m³ | range=16..22; derivable_from=archetype |
| `pore_pressure_ratio` | Pore pressure ratio ru = u / (gamma * z * cos²β) | float | range=0.0..0.5 |
| `kh` | Horizontal seismic coefficient (fraction of g) | float | range=0.05..0.4 |
| `kv` | Vertical seismic coefficient (fraction of g, acts upward for conservative case) | float | range=0.0..0.2 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `fos` | Factor of safety under pseudo-static seismic loading (dimensionless) |  | tolerance=0.03 |
| `yield_acceleration_ky` | Yield (critical) horizontal acceleration at which FoS = 1.0 (fraction of g) |  | tolerance=0.03 |
| `yield_ratio` | Yield acceleration ratio ky / kh (dimensionless) |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `homogeneous_earth_dam` | Homogeneous earth dam with compacted clay core | snowy-mountains-dam; wivenhoe-spillway; warragamba-embankment |
| `zoned_rockfill_dam` | Zoned rockfill dam with gravel shell | thomson-dam-gippsland; hinze-dam-gold-coast; cotter-dam-act |
| `tailings_dam` | Tailings storage facility embankment with mine waste fill | bowen-basin-tsf; kalgoorlie-tailings; hunter-valley-tsf |
| `road_embankment_seismic` | Road embankment in a moderate seismic zone | newcastle-road-embankment; adelaide-hills-embankment; launceston-highway |
| `natural_slope_seismic` | Natural hillside slope in a seismically active region | blue-mountains-escarpment; cairns-range-hillside; otway-ranges-slope |
| `levee_seismic` | River levee under earthquake loading | murray-river-levee; fitzroy-river-levee; hawkesbury-river-levee |

### Difficulty Notes

```text
easy: all_given | Dry cohesionless slope with no vertical seismic coefficient — simplest case
medium: all_given | Embankment with pore pressure and cohesion, all parameters given
hard: partial | hidden=cohesion_kpa, friction_angle_deg, unit_weight_kn_m3 | Material properties hidden; agent infers from embankment description and site context
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
