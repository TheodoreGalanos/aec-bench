# ABOUTME: First-pass task-world opportunity card for single-span-sag-tension.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# electrical / catenary-design / single-span-sag-tension

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/electrical/single_span_sag_tension`
- Discipline: `electrical`
- Category: `catenary-design`
- Tool mode: `with-tool`
- Standards: EN 50119; EN 50367
- Tags: electrical; catenary; sag-tension; overhead-wire; deterministic

## Current Task Shape

Computes mid-span sag, wire length, and catenary constant for a single level span of overhead contact wire used in rail electrification. Applies both the parabolic approximation (S = wL^2/8T) and exact catenary equations per EN 50119, enabling comparison of the two methods across light rail, mainline, and high-speed catenary scenarios.

## Existing Deterministic Contract

- Parameters: `4`
- Outputs: `4`
- Archetypes: `3`
- Visibility mix: all_given; partial
- Hidden parameters: `wire_weight_per_m_n`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `span_length_m` | Horizontal span length between supports | float / m | range=20.0..120.0 |
| `wire_weight_per_m_n` | Wire weight per unit length (gravitational force per metre) | float / N/m | range=3.0..30.0; derivable_from=archetype |
| `horizontal_tension_n` | Horizontal component of wire tension at mid-span | float / N | range=5000.0..30000.0 |
| `wire_diameter_mm` | Outer diameter of the contact wire | float / mm | range=8.0..16.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `sag_m` | Mid-span sag using parabolic approximation (m) |  | tolerance=0.03 |
| `sag_catenary_m` | Mid-span sag using exact catenary equation (m) |  | tolerance=0.03 |
| `wire_length_m` | Total wire length in the span using catenary equation (m) |  | tolerance=0.03 |
| `catenary_constant_m` | Catenary constant C = T / w (m) |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `light_rail_copper` | Light rail copper contact wire (Cu AC-100) | sydney-light-rail; melbourne-tram-network |
| `mainline_catenary` | Mainline rail catenary with CuAg AC-120 contact wire (nominal 10.8-12.5 N/m) | brisbane-cross-river-rail; sydney-metro-northwest |
| `high_speed_catenary` | High-speed rail catenary with CuAg AC-150 contact wire (nominal 14.5-16.0 N/m) | melbourne-geelong-fast-rail; sydney-newcastle-corridor |

### Difficulty Notes

```text
easy: all_given | Short spans, all params given, light rail scenarios
medium: all_given | Any span length and wire type, all params given
hard: partial | hidden=wire_weight_per_m_n | Wire weight hidden, agent must infer from wire diameter and material context
```

## Multimodal Expansion

Candidate modality families: `drawing-geometry`, `tabular-source`, `time-series`.

Use single-line diagrams, layouts, device schedules, demand profiles, and equipment datasheets.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Compose with tasks that share the same site context, source artifact, or downstream output obligation.

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
