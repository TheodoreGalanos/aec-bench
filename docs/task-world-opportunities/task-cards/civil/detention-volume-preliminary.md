# ABOUTME: First-pass task-world opportunity card for detention-volume-preliminary.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / detention-design / detention-volume-preliminary

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/detention_volume_preliminary`
- Discipline: `civil`
- Category: `detention-design`
- Tool mode: `with-tool`
- Standards: TR-55; Local requirements
- Tags: civil; detention; stormwater; hydrology; storage; drainage; deterministic

## Current Task Shape

Estimates the required stormwater detention storage volume using a simplified triangular inflow hydrograph with constant outflow, as commonly applied in preliminary site drainage design per TR-55 and local council requirements. Computes the volume difference between post-development peak inflow and the allowable release rate over the storm duration, and derives an approximate basin surface area from a nominated design depth.

## Existing Deterministic Contract

- Parameters: `4`
- Outputs: `2`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `allowable_release_rate_m3_s`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `post_dev_peak_flow_m3_s` | Post-development peak flow rate Q_post | float / m³/s | range=0.05..15.0 |
| `allowable_release_rate_m3_s` | Allowable (pre-development or regulated) release rate Q_allow | float / m³/s | range=0.01..10.0; derivable_from=archetype |
| `storm_duration_hr` | Design storm duration t_storm | float / hr | range=0.5..24.0 |
| `design_depth_m` | Design water depth of the detention basin | float / m | range=0.5..2.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `required_storage_volume_m3` | Required detention storage volume (m³) |  | tolerance=0.03 |
| `approximate_surface_area_m2` | Approximate basin surface area at design depth (m²) |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `small_residential_subdivision` | Small residential subdivision on gentle terrain with local council detention requirements | sydney-northwest-growth-area; melbourne-casey-corridor; brisbane-north-lakes |
| `commercial_development` | Commercial or mixed-use development with high impervious coverage and moderate catchment | parramatta-cbd-redevelopment; gold-coast-robina-town-centre; adelaide-tonsley-innovation |
| `industrial_estate` | Industrial estate with large hardstand areas and concentrated runoff | western-sydney-aerotropolis; geelong-northern-industrial; townsville-port-expansion |
| `large_greenfield` | Large greenfield development converting rural land to mixed residential with significant flow increase | wollondilly-growth-area; greater-springfield-qld; armstrong-creek-vic |

### Difficulty Notes

```text
easy: all_given | All parameters given — straightforward volume calculation with clear Q_post > Q_allow
medium: all_given | All parameters given but larger flows and longer storms — agent must apply correct case logic
hard: partial | hidden=allowable_release_rate_m3_s | Allowable release rate hidden — agent must infer from site description and local requirements
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
