# ABOUTME: Detailed task-world review for civil conveyance, outfall, and spillway hydraulics.
# ABOUTME: Records multimodal, composition, and meta-harness opportunities for the second civil slice.

# Civil Conveyance And Outfall Pass 002

Review date: 2026-06-28

Reviewed task cards:

- `civil/hydraulic-calculations/mannings-pipe-capacity`
- `civil/hydraulic-calculations/open-channel-capacity`
- `civil/hydraulic-calculations/roadway-spread`
- `civil/pipe-hydraulics/hazen-williams-headloss`
- `civil/pipe-hydraulics/darcy-weisbach-headloss`
- `civil/pipe-hydraulics/pipe-velocity-check`
- `civil/culvert-design/culvert-capacity`
- `civil/outfall-hydraulics/flap-gate-headloss`
- `civil/outfall-hydraulics/outfall-submergence-check`
- `civil/spillway-hydraulics/spillway-weir-capacity`
- `civil/spillway-hydraulics/stilling-basin-sizing`

Source files read for this pass:

- `src/aec_bench/templates/builtin/civil/mannings_pipe_capacity/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/civil/open_channel_capacity/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/civil/roadway_spread/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/civil/hazen_williams_headloss/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/civil/darcy_weisbach_headloss/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/civil/pipe_velocity_check/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/civil/culvert_capacity/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/civil/flap_gate_headloss/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/civil/outfall_submergence_check/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/civil/spillway_weir_capacity/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/civil/stilling_basin_sizing/{params.toml,instruction.md,engine.py}`

## Slice Read

This slice is the hydraulic middle and boundary of a drainage system: capacity, head loss, surface spread, culverts, outfalls, and spillways. The current templates are mostly single-equation worlds, but many include regime or compliance decisions that are perfect for meta-harness gates:

- partially full versus full circular pipe geometry;
- rectangular versus trapezoidal channel geometry;
- empirical Hazen-Williams versus Darcy-Weisbach friction models;
- laminar versus turbulent Darcy friction factor;
- service-type velocity compliance;
- inlet-control versus outlet-control culvert headwater;
- present versus future tidal submergence;
- pier/abutment correction and approach velocity head for spillways;
- Froude-number basin type selection.

The core opportunity is to turn scalar hydraulic coefficients into source-derived evidence. Roughness, C-factor, material, channel lining, gate type, outfall regime, pier shape, abutment shape, and tailwater are naturally read from drawings, schedules, tables, datasheets, maps, or operating scenarios.

## Task 1: Manning's Pipe Capacity

Current world:

- Computes circular pipe flow area, hydraulic radius, velocity, and capacity using Manning's equation.
- Inputs are `pipe_diameter_m`, `mannings_n`, `slope_m_per_m`, and `flow_depth_ratio`.
- Hard mode hides `mannings_n` and asks the model to infer roughness from pipe material.
- The engine branches between full-pipe geometry and partially full circular-segment geometry.

Multimodal expansion:

- Best first modality: pipe schedule plus long section.
- The schedule provides diameter/material; the long section provides slope and, if relevant, depth or hydraulic grade.
- A richer drawing-source variant can require the model to infer whether the pipe is full or partially full from a marked depth line.

Requirements:

- Generated pipe schedule with material, internal diameter, and roughness mapping.
- Long-section artifact with invert levels and reach length so slope can be derived.
- Geometry evidence record for `flow_depth_ratio`, not just final area.
- Roughness source table embedded in the task world.

Harness opportunities:

- Add construction gates for geometry regime: `full_pipe` versus `partial_pipe`.
- Add source-authority gate for Manning's `n`.
- Add contradiction event if the final capacity is right but the model used full-pipe assumptions for a partial-depth source.

Natural products:

- Upstream: hydrology tasks supply design flow.
- Downstream: `pipe-velocity-check`, `hgl-check`, and detention/outfall controls consume capacity or velocity.
- Product world: pipe schedule extraction plus capacity plus velocity compliance.

Meta-harness handles:

- `projection`: source geometry, roughness authority, hydraulic arithmetic.
- `difference`: remove explicit roughness, then remove slope and require long-section interpretation.
- `product`: compose with HGL or velocity compliance tasks.

## Task 2: Open Channel Capacity

Current world:

- Computes area, wetted perimeter, hydraulic radius, velocity, capacity, and Froude number.
- Inputs are bottom width, flow depth, side slope, Manning's `n`, and channel slope.
- Hard mode hides `mannings_n`.
- The engine handles rectangular channels as `side_slope_z = 0` and trapezoidal channels otherwise.

Multimodal expansion:

- Best first modality: channel cross-section drawing plus lining schedule.
- A plan/profile pair can expose channel slope; the section exposes bottom width, depth, and side slope.
- A source table can map concrete, grass, riprap, earth, or gabion lining to roughness.

Requirements:

- Cross-section generator with known dimensions and labels.
- Channel lining/roughness table.
- Source-to-parameter record for geometry and slope.
- Intermediate gate for Froude number and hydraulic-depth calculation.

Harness opportunities:

- Add regime gate for rectangular/trapezoidal geometry.
- Add a Froude classification finding even if final capacity is numerically scored.
- Add a product handle for `flow_capacity_m3_s` into freeboard, overtopping, or downstream control tasks.

Natural products:

- `rational-method -> open-channel-capacity` as a design-flow capacity check.
- `open-channel-capacity -> stilling-basin-sizing` when channel/spillway discharge becomes unit discharge.
- `open-channel-capacity -> roadway-spread` for overland/gutter comparison worlds.

Meta-harness handles:

- `projection`: geometry extraction, roughness selection, flow-regime assessment.
- `subset`: rectangular only, trapezoidal only, lining-specific worlds.
- `product`: channel capacity plus freeboard or downstream energy dissipation.

## Task 3: Roadway Spread

Current world:

- Calculates gutter spread width and curb depth from HEC-22 Manning's equation for triangular gutter cross-sections.
- Inputs are gutter flow, cross slope, longitudinal slope, and Manning's `n`.
- Hard mode hides `mannings_n` from road surface description.

Multimodal expansion:

- Best first modality: road cross-section plus longitudinal grade profile.
- Drainage layout can supply gutter flow from an upstream catchment or inlet bypass calculation.
- The visual task can ask whether spread remains within lane/shoulder limits, but the current engine only returns spread and curb depth.

Requirements:

- Road cross-section artifact with cross slope and curb geometry.
- Longitudinal grade artifact or road chainage table.
- Embedded pavement roughness table.
- Optional compliance threshold for allowable spread width by road class.

Harness opportunities:

- Add source geometry gates for crossfall and longitudinal grade.
- Add an artifact-production variant that marks the spread envelope on a cross-section.
- Add a verifier extension for lane encroachment once allowable spread is added.

Natural products:

- `rational-method -> roadway-spread` using catchment/gutter flow.
- `roadway-spread -> inlet sizing` if an inlet-capture task is added.
- `roadway-spread -> road safety/sight-distance` as a shared road-context world.

Meta-harness handles:

- `projection`: road geometry, roughness source, spread arithmetic.
- `difference`: hide roughness or slope labels.
- `product`: combine with catchment hydrology and inlet-placement worlds.

## Task 4: Hazen-Williams Headloss

Current world:

- Computes pressurised pipe head loss, hydraulic gradient, and mean velocity.
- Inputs are flow rate in L/s, pipe diameter, pipe length, and Hazen-Williams `C`.
- Hard mode hides `c_factor` from pipe material/condition.
- The engine uses the SI form `hf = 10.67 * L * Q^1.852 / (C^1.852 * D^4.87)`.

Multimodal expansion:

- Best first modality: pipe asset schedule plus material/age condition table.
- A long section can supply length and diameter; a pump or network diagram can supply flow.
- A condition-assessment note can distinguish new PVC, ductile iron, aged cast iron, or corroded steel.

Requirements:

- Source table for material/condition to C-factor.
- Pipe schedule with flow, diameter, length, and material.
- Unit conversion evidence for L/s to m3/s and mm to m.
- Optional comparison with Darcy-Weisbach under same pipe context.

Harness opportunities:

- Add source-authority gate for `c_factor`.
- Add unit-conversion construction gate.
- Add model-selection product: choose Hazen-Williams versus Darcy-Weisbach and explain suitability.

Natural products:

- `hazen-williams-headloss -> pump-power-calc` or mechanical pump-head tasks.
- `hazen-williams-headloss -> hgl-check` as a friction-loss stage.
- `hazen-williams-headloss + darcy-weisbach-headloss` as a comparison/consistency world.

Meta-harness handles:

- `projection`: source material selection versus arithmetic.
- `difference`: hide C-factor, then hide material condition in a note.
- `product`: friction model comparison or pump-system product world.

## Task 5: Darcy-Weisbach Headloss

Current world:

- Computes velocity, Reynolds number, Darcy friction factor, and head loss.
- Inputs are flow, diameter, length, roughness height, and kinematic viscosity.
- Hard mode hides `roughness_height_mm`.
- The engine branches: laminar `f = 64/Re` for `Re < 2300`; otherwise Swamee-Jain.

Multimodal expansion:

- Best first modality: pipe schedule plus material roughness table plus fluid property table.
- A more realistic version can hide viscosity behind temperature/fluid-type context.
- A high-value variant compares roughness source uncertainty against head-loss sensitivity.

Requirements:

- Source table for material roughness height.
- Optional source table for fluid viscosity by temperature.
- Construction gate for Reynolds number and regime selection.
- Intermediate evidence record for relative roughness and friction factor.

Harness opportunities:

- Add event trigger for wrong friction-regime selection.
- Add source-authority gate for roughness and viscosity.
- Add a sensitivity/report artifact that records whether roughness uncertainty matters to final head loss.

Natural products:

- `darcy-weisbach-headloss -> pump station/power` worlds.
- `darcy-weisbach-headloss + hazen-williams-headloss` comparison under same pipe network.
- `darcy-weisbach-headloss -> transient-analysis` if paired with mechanical wave-speed/Joukowsky tasks.

Meta-harness handles:

- `projection`: regime selection, source property selection, head-loss arithmetic.
- `difference`: hide roughness, then hide viscosity and require fluid-property inference.
- `product`: compare with Hazen-Williams or feed pump/system curves.

## Task 6: Pipe Velocity Check

Current world:

- Computes pipe velocity and compliance against AS/NZS 3500.1 service-type limits.
- Inputs are pipe diameter, flow rate, and service type.
- Hard mode hides `service_type` and requires inference from site description.
- Output `compliance` is binary numeric: `1.0` if velocity is within the service limit band, else `0.0`.

Multimodal expansion:

- Best first modality: services schedule or network diagram.
- The diagram/schedule can expose service type, pipe diameter, and flow.
- A standards-table source can expose velocity limits rather than baking them into the prompt.

Requirements:

- Service-type to velocity-limit table embedded in the task.
- Pipe schedule or services diagram.
- Compliance evidence record with selected min/max limits.
- Optional action recommendation when compliance fails.

Harness opportunities:

- Add construction gate: selected service type and velocity band must be recorded.
- Add contradiction gate: `compliance` must agree with computed velocity and selected band.
- Add a repair-world variant where the model proposes a diameter change to pass.

Natural products:

- `mannings-pipe-capacity -> pipe-velocity-check`.
- `hazen-williams-headloss -> pipe-velocity-check` under same pipe schedule.
- `pipe-velocity-check -> redesign task` where failed compliance triggers diameter/flow adjustment.

Meta-harness handles:

- `projection`: service classification, arithmetic, compliance decision.
- `difference`: hide service type and/or velocity limit table labels.
- `product`: pair with capacity/headloss for a pipe design package.

## Task 7: Culvert Capacity

Current world:

- Computes inlet-control headwater, outlet-control headwater, controlling condition, and headwater elevation using HDS-5-style circular culvert logic.
- Inputs include diameter, length, slope, design flow, configuration, tailwater depth, and invert elevation.
- Hard mode hides `invert_elevation_m`.
- The engine contains nontrivial internal calculations: critical depth, entrance/configuration coefficients, outlet-control losses, and selection of the higher headwater. `controlling_condition` is `1.0` for inlet control and `2.0` for outlet control.

Multimodal expansion:

- Best first modality: culvert long section plus inlet/headwall detail.
- A site plan can expose roadway crossing geometry and upstream/downstream levels.
- A tailwater hydrograph or water-surface profile can supply tailwater depth.

Requirements:

- Culvert long-section artifact with inlet invert, length, slope, tailwater, and road/embankment levels.
- Configuration table for material/inlet type to coefficients.
- Branch evidence for inlet versus outlet control.
- Headwater elevation tied to a flood-risk or overtopping threshold if added.

Harness opportunities:

- Add branch gate: controlling condition must equal the larger headwater.
- Add source geometry gate for invert elevation and slope.
- Add event trigger for regime mismatch: inlet-control result used when outlet controls, or vice versa.

Natural products:

- `rational-method -> culvert-capacity` using design flow.
- `culvert-capacity -> roadway overtopping/freeboard` if road crest levels are added.
- `culvert-capacity -> stilling-basin-sizing` for high-energy outlets.

Meta-harness handles:

- `projection`: source geometry, inlet-control model, outlet-control model, controlling decision.
- `difference`: hide invert elevation, tailwater, or culvert configuration.
- `product`: culvert crossing design package with hydrology and downstream energy dissipation.

## Task 8: Flap Gate Headloss

Current world:

- Computes flap gate headloss, unseating head, capacity reduction, and discharge coefficient.
- Inputs are pipe diameter, flow velocity, gate type, and upstream head.
- Hard mode hides `gate_type`.
- The engine uses a lookup table of discharge coefficients by gate type and an orifice-based headloss equation.

Multimodal expansion:

- Best first modality: outfall detail or gate datasheet.
- A manufacturer table can expose gate type, coefficient range, and unseating assumptions.
- A tidal outfall drawing can supply pipe diameter and available upstream head.

Requirements:

- Datasheet-like table for gate type to discharge coefficient.
- Outfall drawing with gate, pipe diameter, and head reference.
- Source-to-parameter trace for `gate_type` and coefficient.
- Optional produced artifact: outfall hydraulic loss record.

Harness opportunities:

- Add source-authority gate for gate type and coefficient.
- Add contradiction event if capacity reduction does not agree with selected coefficient.
- Add product handle for outfall submergence and downstream tailwater.

Natural products:

- `hgl-check -> flap-gate-headloss` when flap gate is downstream of a pipe reach.
- `outfall-submergence-check -> flap-gate-headloss` where tidal submergence affects available head.
- `flap-gate-headloss -> detention/outlet redesign` if gate losses constrain release.

Meta-harness handles:

- `projection`: gate identification, coefficient lookup, headloss arithmetic.
- `difference`: remove gate type and require visual/datasheet identification.
- `product`: pair with tidal submergence or HGL checks.

## Task 9: Outfall Submergence Check

Current world:

- Computes present and future submergence fractions/hours using a sinusoidal tide model.
- Inputs are outfall invert, mean sea level, tidal amplitude, sea-level rise, and tidal period.
- Hard mode hides `tidal_period_hours`.
- The engine handles edge cases: always unsubmerged, always submerged, and sinusoidal threshold crossing.

Multimodal expansion:

- Best first modality: coastal/outfall long section plus tide table or tidal regime note.
- A map/profile can expose invert level relative to datum; a sea-level scenario table can expose SLR.
- A richer world can compare present-day and future maintenance/access or backwater risk.

Requirements:

- Datum-aware profile artifact with invert, MSL, and future MSL.
- Tide/regime source table with semi-diurnal or diurnal period.
- Construction gate for the threshold `x = (invert - MSL) / amplitude`.
- Edge-case gate for always dry/always submerged conditions.

Harness opportunities:

- Add source-authority gate for tidal period and sea-level-rise scenario.
- Add event trigger for datum inconsistency: using the wrong vertical datum should fail source evidence even if arithmetic is plausible.
- Add artifact-production variant requiring a present/future outfall-risk note.

Natural products:

- `outfall-submergence-check -> flap-gate-headloss`.
- `wave/coastal tasks -> outfall-submergence-check` for shared coastal boundary conditions.
- `outfall-submergence-check -> HGL/backwater` if downstream tailwater is fed into pipe checks.

Meta-harness handles:

- `projection`: datum extraction, tidal-regime selection, submergence arithmetic.
- `difference`: remove tidal period, then remove explicit datum labels.
- `product`: coastal boundary product with flap gate, HGL, or freeboard checks.

## Task 10: Spillway Weir Capacity

Current world:

- Computes effective crest length, approach velocity head, total energy head, discharge, and unit discharge.
- Inputs include crest length, design head, discharge coefficient, number of piers, pier shape, abutment shape, approach width, and approach depth.
- Hard mode hides `discharge_coefficient`, `pier_shape`, and `abutment_shape`.
- The instruction specifies defaults for missing pier/abutment shapes and pier count.

Multimodal expansion:

- Best first modality: spillway plan/elevation plus pier/abutment detail.
- A hydraulic design table can expose pier and abutment correction coefficients.
- A dam/site plan can expose approach channel geometry.

Requirements:

- Spillway drawing with crest length, piers, abutments, head, approach section.
- Source table for pier and abutment contraction coefficients.
- Construction gate for effective crest length.
- Energy-head evidence gate for approach velocity correction.

Harness opportunities:

- Add source geometry gate for crest and approach dimensions.
- Add source-authority gate for pier/abutment shape selection.
- Add contradiction event where discharge passes but effective crest length or unit discharge is inconsistent.

Natural products:

- `spillway-weir-capacity -> stilling-basin-sizing` using `unit_discharge_m3_s_per_m`.
- `detention/weir-outlet-design -> spillway-weir-capacity` as a simple-to-detailed spillway progression.
- `spillway-weir-capacity -> freeboard/wave-runup` for dam or basin safety checks.

Meta-harness handles:

- `projection`: geometry extraction, correction-factor selection, energy-head calculation.
- `difference`: hide coefficient and shapes; later hide approach geometry.
- `product`: compose with stilling basin and freeboard worlds.

## Task 11: Stilling Basin Sizing

Current world:

- Estimates Froude number, Belanger sequent depth, basin length, and USBR basin type.
- Inputs are unit discharge, drop height, and tailwater depth.
- Hard mode hides `tailwater_depth_m`.
- The instruction defines basin type by Froude number: no basin, Type I, Type II, or Type III.

Multimodal expansion:

- Best first modality: spillway/outlet profile plus downstream tailwater table.
- A hydraulic grade or water-surface profile can expose tailwater depth.
- A richer task can include a layout constraint: required basin length versus available footprint.

Requirements:

- Longitudinal section with drop height and tailwater.
- Source table for USBR basin type and length factors.
- Construction gate for Froude number and basin-type selection.
- Optional feasibility artifact comparing required length with available basin length.

Harness opportunities:

- Add event trigger for wrong basin-type selection at Froude thresholds.
- Add source geometry gate for tailwater and drop height.
- Add artifact-production variant requiring a basin selection note with type code and rationale.

Natural products:

- `spillway-weir-capacity -> stilling-basin-sizing` using unit discharge.
- `culvert-capacity -> stilling-basin-sizing` for high-energy culvert outlets if unit discharge is added.
- `stilling-basin-sizing -> structural/foundation` worlds if basin dimensions or loads are added.

Meta-harness handles:

- `projection`: energy calculation, basin-type classification, geometry feasibility.
- `difference`: hide tailwater and require profile/table interpretation.
- `product`: spillway plus stilling basin product world.

## Cross-Task Product Worlds

### Product World A: Pipe Reach Design Package

Source pack:

- Drainage long section.
- Pipe schedule.
- Material/roughness table.
- Design-flow handoff from hydrology.

Composed tasks:

1. `mannings-pipe-capacity` checks capacity.
2. `pipe-velocity-check` checks service velocity.
3. `hazen-williams-headloss` or `darcy-weisbach-headloss` computes friction loss.
4. `hgl-check` from the previous pass checks surcharge.

Why it is useful:

- It tests source extraction, equation selection, unit conversion, compliance, and handoff consistency without needing a large network solver.

### Product World B: Culvert Crossing Package

Source pack:

- Catchment/design-flow summary.
- Culvert long section.
- Headwall/inlet configuration detail.
- Tailwater table and road crest level.

Composed tasks:

1. Hydrology supplies `design_flow_m3_s`.
2. `culvert-capacity` computes inlet and outlet control.
3. Optional `stilling-basin-sizing` checks outlet energy.
4. Optional freeboard/overtopping task checks headwater against road level.

Why it is useful:

- Culvert control selection gives a clear branch event, and headwater elevation gives a natural downstream decision.

### Product World C: Coastal Outfall Package

Source pack:

- Outfall long section.
- Tide regime/source table.
- Sea-level-rise scenario table.
- Flap gate detail or datasheet.

Composed tasks:

1. `outfall-submergence-check` computes present/future submergence.
2. `flap-gate-headloss` computes gate losses and capacity reduction.
3. `hgl-check` consumes downstream/tailwater consequences if extended.

Why it is useful:

- It combines multimodal vertical-datum extraction, future scenario interpretation, and hydraulic loss.

### Product World D: Spillway Energy-Dissipation Package

Source pack:

- Spillway plan/elevation.
- Pier/abutment correction table.
- Approach channel section.
- Downstream tailwater profile.

Composed tasks:

1. `spillway-weir-capacity` computes discharge and unit discharge.
2. `stilling-basin-sizing` consumes unit discharge and tailwater/depth.
3. Optional structural/foundation tasks consume basin dimensions or loads.

Why it is useful:

- It has strong multimodal geometry, correction-factor lookup, and regime classification in one auditable chain.

## Initial Combination Findings

| Candidate | Product Axis | Handoff Fields | Main New Evidence |
| --- | --- | --- | --- |
| Manning pipe to velocity/HGL | `capacity_to_compliance` | `flow_capacity_m3_s`, diameter, velocity, roughness | Pipe schedule, long section, roughness table. |
| Hazen-Williams to pump/system head | `friction_to_pump_head` | `head_loss_m`, `hydraulic_gradient`, flow | Pipe material schedule, pump duty point, network sketch. |
| Darcy-Weisbach comparison | `friction_model_comparison` | `head_loss_m`, `flow_velocity_m_s`, model assumptions | Material roughness table, fluid property table. |
| Culvert crossing | `hydrology_to_headwater` | `design_flow_m3_s`, tailwater, invert, headwater elevation | Culvert long section, inlet detail, tailwater table. |
| Coastal outfall | `tailwater_to_outfall_loss` | submergence percent, tidal period, gate type, headloss | Outfall profile, tide/SLR table, gate datasheet. |
| Spillway to stilling basin | `spillway_to_energy_dissipation` | `unit_discharge_m3_s_per_m`, drop height, tailwater | Spillway drawing, correction table, tailwater profile. |

## Meta-Harness Follow-Ups

Add operation handles to future explicit world sidecars:

- `source_artifacts.pipe_schedule`
- `source_artifacts.pipe_long_section`
- `source_artifacts.roughness_table`
- `source_artifacts.channel_section`
- `source_artifacts.road_cross_section`
- `source_artifacts.culvert_long_section`
- `source_artifacts.outfall_profile`
- `source_artifacts.tide_scenario_table`
- `source_artifacts.gate_datasheet`
- `source_artifacts.spillway_drawing`
- `source_artifacts.correction_factor_table`
- `source_artifacts.tailwater_profile`
- `branch_decisions.pipe_geometry_regime`
- `branch_decisions.friction_regime`
- `branch_decisions.culvert_control`
- `branch_decisions.tidal_edge_case`
- `branch_decisions.basin_type`
- `compliance.velocity_pass_fail`
- `handoffs.design_flow`
- `handoffs.unit_discharge`
- `handoffs.tailwater`

Add closure and construction gates:

- selected roughness or C-factor is traceable to source material/condition;
- pipe/channel geometry regime matches the source artifact;
- Darcy friction regime follows the computed Reynolds number;
- culvert controlling condition is the larger of inlet and outlet headwater;
- tidal edge case is selected correctly for always submerged/unsubmerged conditions;
- spillway effective crest length reflects pier and abutment corrections;
- stilling basin type follows Froude-number thresholds;
- downstream task inputs equal upstream outputs within declared units.

