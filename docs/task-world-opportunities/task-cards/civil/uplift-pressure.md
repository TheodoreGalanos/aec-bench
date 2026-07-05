# ABOUTME: First-pass task-world opportunity card for uplift-pressure.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / seepage-analysis / uplift-pressure

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/uplift_pressure`
- Discipline: `civil`
- Category: `seepage-analysis`
- Tool mode: `with-tool`
- Standards: USACE EM 1110-2-2200; USBR Design Standard No. 13
- Tags: civil; dams; uplift; pressure; seepage; stability; hydraulics

## Current Task Shape

Calculates the bilinear uplift pressure distribution beneath a concrete gravity dam using the simplified method from USACE EM 1110-2-2200. Computes pressures at the upstream face, drainage gallery, and downstream face, then integrates the trapezoidal distribution to obtain total uplift force per unit length for sliding and overturning stability checks.

## Existing Deterministic Contract

- Parameters: `5`
- Outputs: `4`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `drain_efficiency_pct`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `headwater_depth_m` | Headwater depth (hydraulic head) upstream of the dam | float / m | range=1.0..80.0 |
| `tailwater_depth_m` | Tailwater depth (hydraulic head) downstream of the dam | float / m | range=0.0..20.0 |
| `base_width_m` | Total base width of the dam from upstream to downstream face | float / m | range=3.0..80.0 |
| `drain_distance_m` | Distance from the upstream face to the drainage gallery line | float / m | range=1.0..25.0 |
| `drain_efficiency_pct` | Drainage gallery efficiency as a percentage (0 = no drain, 100 = full relief) | float / % | range=0.0..100.0; derivable_from=archetype |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `upstream_pressure_kpa` | Uplift pressure at the upstream face P_upstream (kPa) |  | tolerance=0.03 |
| `drain_pressure_kpa` | Uplift pressure at the drain line P_drain (kPa) |  | tolerance=0.03 |
| `downstream_pressure_kpa` | Uplift pressure at the downstream face P_downstream (kPa) |  | tolerance=0.03 |
| `total_uplift_force_kn_m` | Total uplift force per unit length of dam U (kN/m) |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `small_weir` | Small weir or low-head diversion structure on alluvial foundation | rural-irrigation-weir; creek-crossing-diversion |
| `medium_gravity_dam` | Medium-height concrete gravity dam with foundation drainage gallery | regional-water-supply-dam; hydropower-gravity-dam |
| `large_flood_dam` | Large concrete gravity dam designed for flood control and water storage | major-flood-control-dam; multi-purpose-reservoir-dam |
| `run_of_river_barrage` | Run-of-river barrage with low head differential and gated spillway | river-barrage-navigation; tidal-barrage-estuary |

### Difficulty Notes

```text
easy: all_given | Small weir scenario, all parameters given including drain efficiency
medium: all_given | All parameters given, wider range of dam types and operating conditions
hard: partial | hidden=drain_efficiency_pct | Drain efficiency hidden; agent must estimate from structure type and site context
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
