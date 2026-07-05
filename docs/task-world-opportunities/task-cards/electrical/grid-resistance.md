# ABOUTME: First-pass task-world opportunity card for grid-resistance.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# electrical / grounding-design / grid-resistance

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/electrical/grid_resistance`
- Discipline: `electrical`
- Category: `grounding-design`
- Tool mode: `with-tool`
- Standards: IEEE 80-2013
- Tags: electrical; grounding; earthing; substation; grid-resistance; deterministic

## Current Task Shape

Computes the resistance of a substation grounding grid and the resulting ground potential rise (GPR = Ig * Rg) using the simplified Schwarz equation from IEEE 80-2013. Accounts for soil resistivity, grid area, total buried conductor length, and burial depth to assess whether step and touch voltage safety limits are met during ground faults.

## Existing Deterministic Contract

- Parameters: `6`
- Outputs: `4`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `soil_resistivity_ohm_m`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `soil_resistivity_ohm_m` | Apparent soil resistivity | float / ohm-m | range=10..3000; derivable_from=archetype |
| `grid_length_m` | Grid length (longer dimension) | float / m | range=10..300 |
| `grid_width_m` | Grid width (shorter dimension) | float / m | range=10..300 |
| `total_conductor_length_m` | Total buried conductor length including ground rods | float / m | range=50..10000 |
| `burial_depth_m` | Grid burial depth below grade | float / m | range=0.3..2.0 |
| `grid_current_ka` | Maximum grid current (symmetrical fault current fraction) | float / kA | range=0.5..40 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `grid_area_m2` | Grid area (m²) |  | tolerance=0.01 |
| `equivalent_radius_m` | Equivalent circular radius of the grid (m) |  | tolerance=0.03 |
| `grid_resistance_ohm` | Grid resistance Rg (ohm) |  | tolerance=0.03 |
| `ground_potential_rise_v` | Ground potential rise GPR (V) |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `distribution_sandy` | Distribution substation on sandy soil | brisbane-suburban; perth-coastal |
| `distribution_clay` | Distribution substation on clay soil | sydney-alluvial; melbourne-basalt |
| `zone_substation` | Zone substation on sandy loam soil (moderately resistive) | hunter-valley-substation; latrobe-valley-substation |
| `transmission_substation` | Transmission substation on rocky ground with high resistivity | pilbara-remote; north-qld-transmission |

### Difficulty Notes

```text
easy: all_given | Small distribution grid, low resistivity, all parameters given
medium: all_given | Any substation type and soil condition, all parameters given
hard: partial | hidden=soil_resistivity_ohm_m | Soil resistivity hidden, agent must infer from site description
```

## Multimodal Expansion

Candidate modality families: `tabular-source`, `time-series`, `drawing-geometry`.

Use single-line diagrams, load schedules, demand profiles, equipment datasheets, and cable schedules.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Electrical sizing tasks can compose with renewable generation, storage, protection, and backup-power worlds.

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
