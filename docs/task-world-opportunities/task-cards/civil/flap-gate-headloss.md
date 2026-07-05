# ABOUTME: First-pass task-world opportunity card for flap-gate-headloss.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / outfall-hydraulics / flap-gate-headloss

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/flap_gate_headloss`
- Discipline: `civil`
- Category: `outfall-hydraulics`
- Tool mode: `both`
- Standards: Manufacturer data; Hydraulic references
- Tags: civil; outfall-hydraulics; flap-gate; headloss; drainage; deterministic

## Current Task Shape

Calculates energy loss through flap gates (tide gates / non-return valves) installed on stormwater outfalls using the orifice equation h = V^2/(2gCd^2). Determines the discharge coefficient from gate type, looks up unseating head from pipe diameter, and computes the effective capacity reduction compared to an open pipe. Used in drainage design to verify that outfall losses remain within acceptable limits for the catchment.

## Existing Deterministic Contract

- Parameters: `4`
- Outputs: `4`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `gate_type`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `pipe_diameter_mm` | Nominal pipe diameter at the outfall | enum / mm | values=150, 225, 300, 375, 450, 600, 750, 900, 1200 |
| `flow_velocity_m_per_s` | Mean flow velocity in the outfall pipe V | float / m/s | range=0.3..4.0 |
| `gate_type` | Flap gate hinge configuration | enum | values=side_hinged, top_hinged, duckbill; derivable_from=archetype |
| `upstream_head_m` | Upstream head driving flow through the gate | float / m | range=0.1..3.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `headloss_m` | Energy loss through the flap gate (m) |  | tolerance=0.05 |
| `unseating_head_m` | Minimum head to open the gate against its own weight (m) |  | tolerance=0.01 |
| `capacity_reduction_percent` | Effective capacity reduction compared to open pipe (%) |  | tolerance=0.03 |
| `discharge_coefficient` | Discharge coefficient Cd for the gate type |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `suburban_stormwater` | Suburban stormwater outfall with side-hinged flap gate | sydney-suburban-outfall; brisbane-creek-outfall |
| `tidal_outfall` | Tidal outfall with top-hinged flap gate to prevent saltwater intrusion | melbourne-tidal-creek; gold-coast-canal-outfall |
| `small_lot_drainage` | Small lot or car park drainage outfall with duckbill elastomeric valve | perth-carpark-outfall; adelaide-lot-drain |
| `trunk_drainage` | Trunk stormwater outfall with heavy-duty top-hinged flap gate | darwin-trunk-outfall; cairns-coastal-outfall |

### Difficulty Notes

```text
easy: all_given | All parameters given, common suburban gate and pipe size
medium: all_given | All parameters given, any gate type and pipe size
hard: partial | hidden=gate_type | Gate type hidden, agent must infer from site description
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
