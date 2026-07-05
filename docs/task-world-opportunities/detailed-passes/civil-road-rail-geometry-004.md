# ABOUTME: Detailed task-world review for civil road, rail, and alignment geometry tasks.
# ABOUTME: Records multimodal, composition, and meta-harness opportunities for the fourth civil slice.

# Civil Road And Rail Geometry Pass 004

Review date: 2026-06-28

Reviewed task cards:

- `civil/horizontal-geometry/curve-elements`
- `civil/horizontal-geometry/min-curve-radius`
- `civil/horizontal-geometry/superelevation-rate`
- `civil/sight-distance/intersection-sight-distance`
- `civil/sight-distance/ssd-on-grade`
- `civil/driveway-access/driveway-gradient-check`
- `civil/track-geometry/cant-calculation`
- `civil/track-geometry/transition-spiral-length`
- `civil/track-geometry/vertical-curve-design`
- `civil/rail-stress/thermal-stress-calculation`

Source files read for this pass:

- `src/aec_bench/templates/builtin/civil/curve_elements/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/civil/min_curve_radius/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/civil/superelevation_rate/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/civil/intersection_sight_distance/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/civil/ssd_on_grade/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/civil/driveway_gradient_check/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/civil/cant_calculation/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/civil/transition_spiral_length/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/civil/vertical_curve_design/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/civil/thermal_stress_calculation/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/generation/instruction_renderer.py`

## Slice Read

This slice is a route geometry package: horizontal alignment, sight distance, driveway access, railway cant/transition/vertical curves, and rail thermal stress. Compared with the hydraulic slices, the interesting task-world surface is less about material flow and more about route evidence:

- chainage and curve geometry from alignment tables or plans;
- design speed, side friction, reaction time, vehicle type, and setback from standards tables or design briefs;
- sight triangles, grades, and driveway levels from drawings;
- rail radius, cant, deficiency, comfort, twist, and temperature assumptions from track geometry records and corridor class.

The current templates already contain several useful regime/compliance hooks: clamped superelevation, speed-dependent friction lookup, gap-time corrections, driveway pass/fail, maximum speed from cant/deficiency, governing spiral length, vertical acceleration comfort limit, and compression/tension stress state.

One contract wrinkle found during this pass: `curve-elements` hard mode hides `ip_chainage_m` and its replacement text references `pc_chainage_m`, but the current instruction renderer only exposes visible sampled parameters. A future explicit task-world sidecar should materialize derived handoff values such as PC chainage instead of relying on hidden-context interpolation.

## Task 1: Curve Elements

Current world:

- Computes tangent length, arc length, external distance, mid-ordinate, and PC/PT chainages.
- Inputs are curve radius, deflection angle, and IP chainage.
- Hard mode hides IP chainage and intends the model to back-calculate from PC chainage and tangent length.
- The engine derives `PC = IP - T` and `PT = PC + arc length`.

Multimodal expansion:

- Best first modality: horizontal alignment plan or alignment schedule.
- A plan can expose IP, tangents, radius, deflection angle, PC, and PT; a schedule can expose chainage rows.
- A richer task can require the model to reconcile plan geometry and schedule values.

Requirements:

- Alignment schedule artifact with IP/PC/PT chainages, radius, deflection angle, and tangent labels.
- Optional plan-view drawing with curve labels and chainage ticks.
- Explicit derived-value sidecar for hard mode if PC chainage is used to infer hidden IP chainage.
- Chainage consistency record: `PC + arc = PT` and `IP - tangent = PC`.

Harness opportunities:

- Add construction gates for tangent length, arc length, and chainage closure.
- Add contradiction event if geometry outputs are correct but chainage identities disagree.
- Add schema repair target for hidden-mode derived values like `pc_chainage_m`.

Natural products:

- `curve-elements -> superelevation-rate` using curve radius.
- `curve-elements -> min-curve-radius` for design-speed compliance comparison.
- `curve-elements -> sight-distance` when route geometry and sight constraints share an alignment plan.

Meta-harness handles:

- `projection`: plan geometry, alignment schedule, curve arithmetic, chainage closure.
- `difference`: remove IP chainage and require back-calculation from PC/PT evidence.
- `product`: alignment plan product with superelevation and sight-distance checks.

## Task 2: Minimum Curve Radius

Current world:

- Computes absolute and desirable minimum horizontal curve radius from speed, maximum superelevation, and side friction.
- Hard mode hides side friction factor and expects inference from AGRD Table 7.5.
- The desirable minimum radius uses reduced friction, `0.7 * f`.

Multimodal expansion:

- Best first modality: design brief plus standards table.
- Design-speed signs, road-class notes, or alignment design criteria can provide speed and superelevation policy.
- The friction factor should come from an embedded standards table, not a general knowledge guess.

Requirements:

- Standards-table source for speed to side-friction factor.
- Road design-criteria sheet with design speed and maximum superelevation.
- Evidence record for selected `f`, reduced desirable `f`, and both radii.
- Optional comparison gate against proposed curve radius from a plan.

Harness opportunities:

- Add source-authority gate for side-friction lookup.
- Add compliance gate: proposed radius must exceed absolute or desirable minimum depending on selected policy.
- Add event trigger if the model uses percent superelevation as a fraction incorrectly.

Natural products:

- `min-curve-radius -> curve-elements` as a design/check pair.
- `min-curve-radius -> superelevation-rate` through shared speed, radius, and friction.
- Road alignment portfolio tasks comparing alternative curve radii.

Meta-harness handles:

- `projection`: design criteria, standards lookup, radius arithmetic, compliance decision.
- `difference`: remove side friction or design-speed source labels.
- `product`: horizontal alignment compliance package.

## Task 3: Superelevation Rate

Current world:

- Computes required road superelevation and development length.
- Inputs are design speed, curve radius, side friction, lane width, and rotation rate.
- Hard mode hides side friction factor.
- The engine clamps negative computed superelevation to zero.

Multimodal expansion:

- Best first modality: road cross-section plus alignment curve table plus design-criteria sheet.
- A cross-section can expose lane width and rotation axis; a criteria sheet can expose rotation rate.
- A standards table can supply side-friction factor.

Requirements:

- Source artifacts for radius, design speed, side friction, lane width, and rotation rate.
- Construction gate for clamp decision: whether computed `e` is negative before clamping.
- Development-length evidence tied to a plan or chainage interval.

Harness opportunities:

- Add event trigger for missing clamp logic.
- Add source-authority gate for side friction and rotation rate.
- Add product-world gate that development length fits between adjacent geometric constraints.

Natural products:

- `curve-elements -> superelevation-rate` through `curve_radius_m`.
- `min-curve-radius -> superelevation-rate` as feasibility then detailed design.
- `superelevation-rate -> driveway/intersection` in shared road corridor contexts where crossfall affects access.

Meta-harness handles:

- `projection`: standards lookup, cross-section extraction, clamp/regime decision, runoff arithmetic.
- `difference`: remove side friction and rotation-rate labels.
- `product`: horizontal curve design package.

## Task 4: Intersection Sight Distance

Current world:

- Computes gap time, required ISD, and sight-triangle major/minor legs.
- Inputs include design speed, control type, approach grade, lanes to cross, vehicle type, and setback distance.
- Hard mode hides vehicle type and setback distance.
- The engine applies base gap times, upgrade-grade correction, and extra-lane correction.

Multimodal expansion:

- Best first modality: intersection plan plus traffic/design-vehicle note.
- The plan can expose setback, lanes to cross, control type, and sight triangle obstruction geometry.
- A road/industrial context brief can imply design vehicle.

Requirements:

- Intersection plan with lane count, control, setback, approach grade, and obstruction/sight-line geometry.
- Design-vehicle source note or traffic composition table.
- Standards table for base gap times and lane/grade corrections.
- Evidence record for `t_base`, grade correction, lane correction, total gap, and sight triangle.

Harness opportunities:

- Add source geometry gate for setback and lane count.
- Add source-authority gate for vehicle type.
- Add contradiction event if `gap_time_s` does not equal the sum of base, grade, and lane corrections.

Natural products:

- `intersection-sight-distance -> driveway-gradient-check` for property access reviews.
- `ssd-on-grade -> intersection-sight-distance` through shared design speed and grade context.
- Product world: access/intersection safety check from a single road-access plan.

Meta-harness handles:

- `projection`: plan geometry, vehicle/source selection, standards-table lookup, gap-time arithmetic.
- `difference`: hide vehicle type, setback, or lane-count labels.
- `product`: road access safety package.

## Task 5: Stopping Sight Distance On Grade

Current world:

- Computes reaction distance, braking distance, and total stopping sight distance.
- Inputs are design speed, longitudinal grade, and reaction time.
- Hard mode hides reaction time.
- The engine looks up speed-dependent friction from an internal table and uses grade sign convention: uphill assists braking, downhill hinders braking.

Multimodal expansion:

- Best first modality: vertical alignment profile plus design-speed/driver-alertness brief.
- A grade profile supplies longitudinal grade; a route-class note supplies reaction time.
- A sight-line profile can compare available sight distance against required SSD if added.

Requirements:

- Vertical profile artifact with grade sign and direction of travel.
- Standards table for speed to friction coefficient and route class to reaction time.
- Construction gate for friction lookup/interpolation and grade sign.
- Optional compliance output: available sight distance versus required SSD.

Harness opportunities:

- Add event trigger for grade sign reversal.
- Add source-authority gate for reaction time.
- Add product-world handoff from vertical-curve design or route profile to sight-distance check.

Natural products:

- `vertical-curve-design -> ssd-on-grade` for road/rail profile comfort and sight packages.
- `ssd-on-grade -> intersection-sight-distance` through common speed/grade criteria.
- `ssd-on-grade -> curve-elements` for route segment safety portfolios.

Meta-harness handles:

- `projection`: profile grade extraction, friction lookup, reaction-time source, braking arithmetic.
- `difference`: remove reaction time and/or direction-of-travel labels.
- `product`: road safety sight-distance package.

## Task 6: Driveway Gradient Check

Current world:

- Computes driveway gradient, maximum allowable gradient, and compliance.
- Inputs are start level, end level, horizontal length, and location type.
- Hard mode hides location type.
- The engine uses a location-type maximum-gradient table and binary compliance.

Multimodal expansion:

- Best first modality: driveway long section or levels sketch plus access-context note.
- The drawing supplies levels and horizontal length; the context or plan supplies transition/ramp/location type.
- A richer variant can require segmentation into multiple driveway grades and transition zones.

Requirements:

- Long-section artifact with start/end levels and horizontal distance.
- Source table for location type to maximum allowable gradient.
- Evidence record for absolute level difference, gradient, selected limit, and compliance.
- Optional artifact-production: noncompliance mark-up or redesign suggestion.

Harness opportunities:

- Add contradiction gate: compliance must match gradient and selected limit.
- Add source geometry gate for levels and length.
- Add product-world gate with intersection sight distance where access location affects safety.

Natural products:

- `driveway-gradient-check -> intersection-sight-distance` for access approval.
- `driveway-gradient-check -> stormwater/roadway-spread` if driveway grades affect drainage paths.
- Multi-step access-compliance package from one site plan.

Meta-harness handles:

- `projection`: level extraction, location classification, compliance decision.
- `difference`: hide location type or split levels across a drawing.
- `product`: site access compliance package.

## Task 7: Rail Cant Calculation

Current world:

- Computes equilibrium cant, cant deficiency, and maximum allowable speed for a curved rail track.
- Inputs are design speed, curve radius, actual cant, maximum cant deficiency, and gauge type.
- Hard mode hides actual cant and maximum cant deficiency.
- The engine validates gauge-specific maximum actual cant and uses gauge constants.

Multimodal expansion:

- Best first modality: track alignment/cant table plus corridor class note.
- Alignment provides radius and design speed; track geometry records provide actual cant.
- Operating context provides allowable cant deficiency and gauge.

Requirements:

- Track curve table with radius, gauge, design speed, and actual cant.
- Corridor-class standards table for maximum deficiency and actual-cant limits.
- Construction gate for equilibrium cant, deficiency, and maximum speed.
- Compliance gate for whether design speed is within maximum allowable speed.

Harness opportunities:

- Add source-authority gate for actual cant and deficiency limits.
- Add event trigger if maximum-speed computation disagrees with actual cant plus allowable deficiency.
- Add product handle into transition spiral length.

Natural products:

- `curve-elements -> cant-calculation` if road/rail curve radius is shared.
- `cant-calculation -> transition-spiral-length` through actual cant, deficiency, and speed.
- Product world: rail horizontal curve ride/geometry package.

Meta-harness handles:

- `projection`: curve geometry, corridor/gauge source, cant arithmetic, speed compliance.
- `difference`: remove actual cant and deficiency, requiring table/context inference.
- `product`: rail curve design package.

## Task 8: Transition Spiral Length

Current world:

- Computes spiral length from cant runoff, cant-deficiency rate, twist criterion, and takes the governing maximum.
- Inputs are actual cant, cant deficiency, maximum speed, rate of change of cant, rate of change of cant deficiency, and minimum twist ratio.
- Hard mode hides the rate limits and twist ratio.

Multimodal expansion:

- Best first modality: corridor design criteria table plus rail curve/cant calculation handoff.
- A track geometry design sheet can provide actual cant, deficiency, speed, and required transition constraints.
- A plan can expose available tangent length to test feasibility.

Requirements:

- Handoff from `cant-calculation`: actual cant, cant deficiency, max speed.
- Standards/corridor table for cant rate, deficiency rate, and twist ratio.
- Construction gate for all three candidate lengths and governing selection.
- Optional feasibility check against available transition length from alignment plan.

Harness opportunities:

- Add governing-criterion event trigger if the max selection is wrong.
- Add source-authority gate for rate/twist limits.
- Add product-world gate that transition length fits between PC/PT or adjacent constraints.

Natural products:

- `cant-calculation -> transition-spiral-length`.
- `transition-spiral-length -> curve-elements` for chainage placement of spirals.
- `transition-spiral-length -> vertical-curve-design` in a route geometry package.

Meta-harness handles:

- `projection`: source criteria, handoff values, three criteria arithmetic, governing selection.
- `difference`: hide rate/twist limits and require corridor-context inference.
- `product`: rail curve transition package.

## Task 9: Vertical Curve Design

Current world:

- Computes algebraic grade difference, minimum vertical curve radius, and minimum vertical curve length.
- Inputs are initial grade, final grade, design speed, and maximum vertical acceleration.
- Hard mode hides acceptable vertical acceleration.
- The engine uses `R_v = V^2 / (3.6^2 * a_v)` and length from grade change times radius.

Multimodal expansion:

- Best first modality: rail longitudinal profile plus passenger/freight corridor-class note.
- The profile supplies grades; the corridor class supplies comfort/acceleration limit.
- A richer variant can compare proposed vertical curve length against minimum.

Requirements:

- Longitudinal profile artifact with grades and curve chainage.
- Corridor class standards table for vertical acceleration limits.
- Construction gate for algebraic grade difference and unit conversion.
- Optional compliance check against proposed radius/length.

Harness opportunities:

- Add source geometry gate for profile grades.
- Add source-authority gate for acceleration limit.
- Add event trigger if the model confuses percent grade with decimal grade in curve length.

Natural products:

- `vertical-curve-design -> ssd-on-grade` through profile/speed context.
- `vertical-curve-design -> transition-spiral-length` in route geometry portfolio.
- `vertical-curve-design -> rail thermal/stress` if route class and track type are shared, although physics is separate.

Meta-harness handles:

- `projection`: profile extraction, acceleration-limit source, radius/length arithmetic.
- `difference`: hide acceleration limit or proposed-curve labels.
- `product`: rail vertical alignment package.

## Task 10: Thermal Stress Calculation

Current world:

- Computes thermal stress, thermal force, and stress state in continuously welded rail.
- Inputs are rail area, thermal expansion coefficient, elastic modulus, and temperature change.
- Hard mode hides elastic modulus and thermal expansion coefficient.
- The engine reports stress/force magnitudes and encodes state by temperature-change sign: compression `1.0`, tension `-1.0`, neutral `0.0`.

Multimodal expansion:

- Best first modality: rail section/material note plus temperature-neutral-stress record.
- Rail area can come from a rail section table; material properties from a rail steel table; temperature change from installation and design temperature records.
- A richer variant can ask for risk classification or stress-free temperature adjustment.

Requirements:

- Rail section table with area.
- Material property table for rail steel modulus and thermal expansion.
- Temperature record for neutral and rail/design temperature.
- Construction gate for sign/state classification and magnitude conversion.

Harness opportunities:

- Add event trigger for stress-state sign reversal.
- Add source-authority gate for material properties.
- Add artifact-production variant requiring a CWR stress note with assumptions.

Natural products:

- `thermal-stress-calculation -> track alignment/maintenance package` through corridor and rail section context.
- `thermal-stress-calculation -> structural thermal movement` across civil/structural disciplines.
- `thermal-stress-calculation -> cant/track geometry` only as shared rail asset context, not as a direct numeric handoff.

Meta-harness handles:

- `projection`: material source, temperature source, stress arithmetic, sign/state classification.
- `difference`: remove material properties or neutral-temperature context.
- `product`: rail asset condition package.

## Cross-Task Product Worlds

### Product World A: Road Horizontal Alignment Package

Source pack:

- Horizontal alignment plan.
- Curve/alignment schedule.
- Road design-criteria sheet.
- AGRD side-friction and superelevation table.

Composed tasks:

1. `curve-elements` computes PC/PT and curve geometry.
2. `min-curve-radius` checks feasibility for the design speed.
3. `superelevation-rate` computes required superelevation and development length.

Why it is useful:

- It checks plan/schedule extraction, table lookup, unit conventions, and chainage consistency in one compact world.

### Product World B: Road Access And Sight Package

Source pack:

- Site access/driveway long section.
- Intersection plan.
- Vertical profile or grade notes.
- Vehicle/context design brief.

Composed tasks:

1. `driveway-gradient-check` checks access grade compliance.
2. `intersection-sight-distance` checks sight triangle and design vehicle.
3. `ssd-on-grade` checks stopping sight distance on the same approach.

Why it is useful:

- It is realistic for planning approvals: one drawing pack, multiple compliance checks, several source-derived hidden assumptions.

### Product World C: Rail Curve Geometry Package

Source pack:

- Track alignment curve table.
- Corridor class design criteria.
- Gauge/cant limits table.
- Available tangent/transition length from plan.

Composed tasks:

1. `cant-calculation` computes equilibrium cant, deficiency, and max speed.
2. `transition-spiral-length` consumes cant, deficiency, and speed to determine governing spiral length.
3. Optional `curve-elements` places the curve/transition in chainage.

Why it is useful:

- It has a clean handoff and a strong governing-criterion event target.

### Product World D: Rail Vertical And Thermal Condition Package

Source pack:

- Longitudinal rail profile.
- Corridor comfort table.
- Rail section/material table.
- Temperature/neutral-stress record.

Composed tasks:

1. `vertical-curve-design` computes vertical curve radius and length.
2. `thermal-stress-calculation` computes stress/force and compression/tension state.
3. Optional asset-review artifact records whether route geometry and thermal stress assumptions belong to the same corridor class.

Why it is useful:

- It tests shared rail asset context even where numeric handoff is loose; the meta-harness should distinguish true numeric pipelines from shared-context products.

## Initial Combination Findings

| Candidate | Product Axis | Handoff Fields | Main New Evidence |
| --- | --- | --- | --- |
| Curve to superelevation | `alignment_to_crossfall` | `curve_radius_m`, design speed, side friction, lane width | Alignment table, road design criteria, standards friction table. |
| Curve to radius compliance | `proposed_curve_to_minimum_radius` | proposed radius, speed, `e_max`, side friction | Alignment plan, criteria sheet, AGRD table. |
| Access to sight package | `access_geometry_to_safety_compliance` | grade, setback, vehicle type, design speed | Driveway long section, intersection plan, design vehicle note. |
| Cant to transition spiral | `cant_to_transition_length` | actual cant, cant deficiency, maximum speed | Track curve table, corridor class limits, transition plan. |
| Vertical profile to SSD | `profile_to_sight_distance` | grade, speed, reaction time, friction lookup | Vertical profile, route class table. |
| Rail material to stress state | `rail_material_to_thermal_state` | rail area, modulus, expansion coefficient, temperature change | Rail section table, material table, temperature record. |

## Meta-Harness Follow-Ups

Add operation handles to future explicit world sidecars:

- `source_artifacts.alignment_plan`
- `source_artifacts.alignment_schedule`
- `source_artifacts.road_design_criteria`
- `source_artifacts.standards_friction_table`
- `source_artifacts.road_cross_section`
- `source_artifacts.intersection_plan`
- `source_artifacts.driveway_long_section`
- `source_artifacts.vertical_profile`
- `source_artifacts.track_curve_table`
- `source_artifacts.corridor_class_table`
- `source_artifacts.rail_section_table`
- `source_artifacts.temperature_record`
- `branch_decisions.superelevation_clamp`
- `branch_decisions.governing_spiral_criterion`
- `branch_decisions.stress_state`
- `branch_decisions.grade_sign_convention`
- `compliance.driveway_gradient`
- `compliance.radius_minimum`
- `compliance.sight_distance`
- `handoffs.curve_radius`
- `handoffs.actual_cant`
- `handoffs.cant_deficiency`
- `handoffs.maximum_speed`

Add closure and construction gates:

- curve chainage identities close: `PC = IP - T` and `PT = PC + L`;
- side-friction and reaction-time assumptions are traceable to standards/source tables;
- superelevation clamp decision is recorded before development length;
- gap time equals base plus grade plus lane corrections;
- grade sign convention is explicit for stopping sight distance;
- driveway compliance matches gradient and selected location limit;
- cant deficiency and maximum speed use the selected gauge/corridor constraints;
- governing spiral length equals the maximum of the three criterion lengths;
- vertical curve length uses percent-grade difference consistently;
- stress state matches temperature-change sign.

