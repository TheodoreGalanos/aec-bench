# ABOUTME: First-pass task-world opportunity card for yellow-interval-calculation.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# electrical / signal-timing / yellow-interval-calculation

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/electrical/yellow_interval_calculation`
- Discipline: `electrical`
- Category: `signal-timing`
- Tool mode: `with-tool`
- Standards: ITE Yellow Interval Equation; MUTCD; AS 1742.14
- Tags: electrical; traffic-signals; yellow-interval; signal-timing; kinematics; deterministic

## Current Task Shape

Calculates the yellow change interval for a traffic signal approach using the metric ITE kinematic equation. The template converts approach speed to m/s, applies perception-reaction time, deceleration rate, and road grade, then reports both raw and one-decimal rounded yellow interval.

## Existing Deterministic Contract

- Parameters: `4`
- Outputs: `4`
- Archetypes: `3`
- Visibility mix: all_given; partial
- Hidden parameters: `road_grade_pct`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `approach_speed_kmh` | Approach speed | float / km/h | range=10..120 |
| `perception_reaction_time_s` | Driver perception-reaction time | float / s | range=0.5..2.5 |
| `deceleration_rate_m_s2` | Comfortable deceleration rate | float / m/s2 | range=1.5..5.0 |
| `road_grade_pct` | Approach grade, positive for upgrade and negative for downgrade | float / % | range=-10..10 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `approach_speed_m_s` | Approach speed converted to metres per second |  | tolerance=0.01 |
| `grade_adjusted_denominator` | Denominator in the metric ITE stopping term |  | tolerance=0.03 |
| `yellow_interval_s` | Calculated yellow interval |  | tolerance=0.03 |
| `yellow_interval_rounded_s` | Yellow interval rounded to one decimal place |  | tolerance=0.01 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `urban_arterial` | Urban arterial signal approach | urban-intersection; arterial-road |
| `high_speed_approach` | High-speed signalised approach | rural-highway; outer-urban-arterial |
| `steep_grade_approach` | Signal approach with material grade effect | hilly-arterial; bridge-approach |

### Difficulty Notes

```text
easy: all_given | Urban approach with all kinematic inputs given
medium: all_given | Mixed speed approaches and grade effects
hard: partial | hidden=road_grade_pct | Grade value hidden in the site context
```

## Multimodal Expansion

Candidate modality families: `drawing-geometry`, `tabular-source`, `spatial-map`.

Use layout plans, device schedules, coverage diagrams, timing tables, and network topology artifacts.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Communications and ITS tasks combine through shared layouts, device counts, coverage, storage, and power constraints.

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
