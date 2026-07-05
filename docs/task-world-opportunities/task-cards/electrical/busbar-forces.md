# ABOUTME: First-pass task-world opportunity card for busbar-forces.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# electrical / busbar-design / busbar-forces

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/electrical/busbar_forces`
- Discipline: `electrical`
- Category: `busbar-design`
- Tool mode: `with-tool`
- Standards: IEEE 605-2008; IEC 60865-1:2011
- Tags: electrical; busbar; short-circuit; electromagnetic-force; substation

## Current Task Shape

Calculates the electromagnetic force per unit length on the centre phase of a three-phase flat busbar arrangement during a symmetrical short circuit using Fm = (mu_0 / 2pi) * (sqrt(3)/2) * ip^2 / a, then derives peak span force and bending stress. Used to verify busbar mechanical adequacy in switchgear and substation design per IEEE 605 and IEC 60865-1.

## Existing Deterministic Contract

- Parameters: `7`
- Outputs: `3`
- Archetypes: `3`
- Visibility mix: all_given; partial
- Hidden parameters: `busbar_material`, `support_condition`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `peak_short_circuit_current_ka` | Peak (asymmetrical) short-circuit current ip | float / kA | range=5..200 |
| `phase_spacing_mm` | Centre-to-centre spacing between adjacent busbar phases | float / mm | range=50..1000 |
| `span_length_m` | Span length between busbar supports | float / m | range=0.3..3.0 |
| `busbar_width_mm` | Width of rectangular busbar cross-section | float / mm | range=20..200 |
| `busbar_thickness_mm` | Thickness of rectangular busbar cross-section (bending direction) | float / mm | range=3..20 |
| `support_condition` | End support condition for the busbar span | enum | values=simply_supported, fixed_both_ends; derivable_from=archetype |
| `busbar_material` | Busbar conductor material | enum | values=copper, aluminium; derivable_from=archetype |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `force_per_m_n` | Electromagnetic force per unit length on centre phase (N/m) |  | tolerance=0.03 |
| `peak_force_n` | Total peak force over one busbar span (N) |  | tolerance=0.03 |
| `busbar_stress_mpa` | Maximum bending stress in the busbar (MPa) |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `lv_switchboard` | Low-voltage switchboard busbar (400-480 V) | commercial-switchroom; industrial-mcc-room |
| `mv_switchgear` | Medium-voltage metal-clad switchgear busbar (11-33 kV) | zone-substation-switchroom; industrial-hv-room |
| `outdoor_substation` | Outdoor air-insulated substation rigid bus (66-132 kV) | transmission-substation; bulk-supply-substation |

### Difficulty Notes

```text
easy: all_given | LV switchboard, short span, all parameters given including support condition and material
medium: all_given | Any voltage level and archetype, all parameters given
hard: partial | hidden=support_condition, busbar_material | Support condition and material hidden, agent must infer from installation context
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
