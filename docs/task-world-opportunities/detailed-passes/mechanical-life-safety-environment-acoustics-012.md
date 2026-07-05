# ABOUTME: Detailed task-world review for mechanical life-safety, fire, gas, ventilation, and acoustics tasks.
# ABOUTME: Records multimodal, composition, and meta-harness opportunities for the third mechanical discipline slice.

# Mechanical Life Safety Environment And Acoustics Pass 012

Review date: 2026-06-28

Reviewed task cards:

- `mechanical/fire-services/nac-load-calculation`
- `mechanical/prescriptive-compliance/occupant-load`
- `mechanical/egress-modeling/egress-width`
- `mechanical/design-fire/t-squared-hrr`
- `mechanical/structural-fire/steel-critical-temp`
- `mechanical/tenability-assessment/visibility-criterion`
- `mechanical/ventilation/air-changes`
- `mechanical/gas-services/gas-load-calculation`
- `mechanical/fundamental-calculations/a-weighting`
- `mechanical/fundamental-calculations/distance-attenuation`
- `mechanical/fundamental-calculations/sabine-rt60`
- `mechanical/fundamental-calculations/spl-log-sum`

Source files read for this pass:

- `src/aec_bench/templates/builtin/mechanical/nac_load_calculation/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/mechanical/occupant_load/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/mechanical/egress_width/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/mechanical/t_squared_hrr/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/mechanical/steel_critical_temp/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/mechanical/visibility_criterion/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/mechanical/air_changes/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/mechanical/gas_load_calculation/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/mechanical/a_weighting/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/mechanical/distance_attenuation/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/mechanical/sabine_rt60/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/mechanical/spl_log_sum/{params.toml,instruction.md,engine.py}`

## Slice Read

This slice is still all-given at the scalar level, but it is more obviously document-shaped than the hydraulic slices. The sources it wants are floor plans, occupancy schedules, egress plans, fire alarm device schedules, steel member/load schedules, design-fire scenarios, smoke or tenability output tables, room geometry, ventilation schedules, gas appliance schedules, octave-band spectra, acoustic source maps, and room-finish schedules.

The strongest task-world opportunity is a building safety and environment package:

- occupant load from area and occupancy criterion feeds egress width;
- notification appliance quantities and currents feed NAC circuit capacity;
- design-fire HRR feeds smoke/tenability scenarios and structural-fire questions;
- load ratio and critical temperature bridge mechanical fire safety and structural design;
- room volume and finishes feed ventilation and acoustics;
- gas appliance schedules become diversified gas demand.

The practical meta-harness work is source classification. The model needs to know whether a plan area is gross/net area, whether an egress width is provided clear width, whether a fire scenario is peak-limited, whether a steel load ratio comes from structural action effects, and whether an acoustic level is octave-band, source SPL, or receiver SPL.

## Task 1: NAC Load Calculation

Current world:

- Computes total notification appliance circuit load, utilisation, spare capacity, and pass flag.
- Inputs are strobe, horn, and speaker quantities/currents plus circuit capacity.
- At least one notification appliance quantity must be positive.
- Every difficulty tier exposes every input.

Multimodal expansion:

- Best first modality: fire alarm device schedule or reflected ceiling plan.
- A circuit variant can require selecting devices on a specific NAC loop from multiple plan zones.
- A hard variant can reconcile device current settings from manufacturer tables and schedule counts.

Requirements:

- Device quantity source by type.
- Device current source by type and setting.
- Circuit capacity source.
- Circuit/zone selection evidence.
- Pass/fail evidence.

Harness opportunities:

- Add device-count extraction gate.
- Add device-current source gate.
- Add circuit-membership gate.
- Add utilisation/margin/pass consistency gate.

Natural products:

- `nac-load-calculation -> electrical battery-sizing/power-supply` for fire alarm backup capacity.
- `nac-load-calculation -> occupant-load/egress-width` in a life-safety compliance package.
- `nac-load-calculation -> fire-services drawing review` if device coverage tasks are added.

Meta-harness handles:

- `projection`: fire alarm plan, device schedule, manufacturer current table, panel schedule.
- `difference`: include appliances from adjacent circuits as distractors.
- `product`: notification circuit capacity record.

## Task 2: Occupant Load

Current world:

- Computes calculated occupants, design occupants rounded up, and occupant density.
- Inputs are floor area and area per occupant.
- The engine uses `ceil` for design occupants.
- Every difficulty tier exposes every input.

Multimodal expansion:

- Best first modality: floor plan plus occupancy/use schedule.
- A code-table variant can require choosing area-per-occupant from occupancy classification.
- A hard variant can split a floor into zones and sum rounded or unrounded occupant loads according to the declared rule.

Requirements:

- Floor area source.
- Occupancy classification or area-per-occupant source.
- Rounding rule.
- Handoff field for design occupants.

Harness opportunities:

- Add area extraction gate.
- Add occupancy classification/source gate.
- Add rounding gate.
- Add handoff gate to `egress-width`.

Natural products:

- `occupant-load -> egress-width`.
- `occupant-load -> ventilation air-changes/outdoor air` if future ventilation criteria are added.
- `occupant-load -> electrical handling-capacity/escalator-capacity` in transport-building worlds.

Meta-harness handles:

- `projection`: architectural plan, occupancy schedule, code criterion table.
- `difference`: mix gross, net, and excluded service areas.
- `product`: occupant load schedule.

## Task 3: Egress Width

Current world:

- Computes required width, provided margin, utilisation ratio, and width-satisfies flag.
- Inputs are occupant load, width per occupant, and provided width.
- If provided width is zero, utilisation ratio becomes infinite and the pass flag is false.
- Every difficulty tier exposes every input.

Multimodal expansion:

- Best first modality: egress plan plus door/stair width schedule.
- A route variant can require choosing the controlling egress element.
- A hard variant can feed occupant load from multiple upstream floor/zone calculations.

Requirements:

- Occupant load handoff or source.
- Width-per-occupant criterion source.
- Provided clear width source.
- Route/element selection evidence.

Harness opportunities:

- Add egress-element selection gate.
- Add clear-vs-nominal width gate.
- Add occupant-load handoff gate.
- Add margin/utilisation/pass consistency gate.

Natural products:

- `occupant-load -> egress-width`.
- `egress-width -> visibility-criterion` in evacuation tenability worlds.
- `egress-width -> pedestrian/electrical handling capacity tasks` for station concourses.

Meta-harness handles:

- `projection`: egress plan, door/stair schedule, occupancy table.
- `difference`: include leaf width, frame width, and clear width together.
- `product`: egress capacity check.

## Task 4: T-Squared HRR

Current world:

- Computes unclipped HRR, HRR at time, time to peak, and peak-limited flag.
- Inputs are growth coefficient, time from ignition, and peak HRR.
- The engine caps HRR at peak and flags whether the cap is active.
- Every difficulty tier exposes every input.

Multimodal expansion:

- Best first modality: design-fire scenario table.
- A plot variant can require reading time and peak HRR from a fire-growth curve.
- A hard variant can select slow/medium/fast growth class from occupancy or fuel package.

Requirements:

- Growth coefficient source.
- Time/scenario source.
- Peak HRR source.
- Peak-limit branch evidence.

Harness opportunities:

- Add fire-growth-class source gate.
- Add peak-limit branch gate.
- Add time-to-peak consistency gate.
- Add handoff gate to tenability or structural-fire scenarios.

Natural products:

- `t-squared-hrr -> visibility-criterion` through smoke production if smoke tasks are added.
- `t-squared-hrr -> steel-critical-temp` as fire exposure context.
- `t-squared-hrr -> egress-width/occupant-load` in performance fire-safety packages.

Meta-harness handles:

- `projection`: design-fire scenario table, HRR curve, fuel/occupancy note.
- `difference`: include growth class labels without coefficients.
- `product`: design-fire HRR record.

## Task 5: Steel Critical Temperature

Current world:

- Computes critical steel temperature, margin to protection trigger, and protection-required flag.
- Inputs are structural-fire load ratio and protection trigger temperature.
- Load ratio must be greater than zero and less than one.
- Every difficulty tier exposes every input.

Multimodal expansion:

- Best first modality: structural member schedule plus fire protection criterion.
- A cross-discipline variant can source load ratio from structural utilisation or load-combination results.
- A hard variant can require matching a member to its fire protection trigger or coating schedule.

Requirements:

- Member load ratio source.
- Protection trigger source.
- Member identity/source evidence.
- Pass/fail story around protection required.

Harness opportunities:

- Add structural load-ratio source gate.
- Add member/protection-trigger matching gate.
- Add margin/pass consistency gate.
- Add cross-discipline handoff from structural load tasks.

Natural products:

- `structural load-combinations -> steel-critical-temp`.
- `t-squared-hrr -> steel-critical-temp` if fire exposure is developed.
- `steel-critical-temp -> material/protection specification` if coating tasks are added.

Meta-harness handles:

- `projection`: steel member schedule, structural calculation extract, fire-protection schedule.
- `difference`: include strength utilisation and fire load ratio in the same pack.
- `product`: structural-fire temperature check.

## Task 6: Visibility Criterion

Current world:

- Computes visibility, margin, utilisation ratio, and criterion-satisfied flag.
- Inputs are extinction coefficient, visibility constant, and minimum visibility.
- The formula is visibility constant divided by extinction coefficient.
- Every difficulty tier exposes every input.

Multimodal expansion:

- Best first modality: smoke model output table plus tenability criteria table.
- A route variant can require selecting an egress path or time slice.
- A hard variant can join design-fire HRR, smoke scenario, and egress route criteria.

Requirements:

- Extinction coefficient source.
- Visibility constant source.
- Minimum visibility criterion source.
- Time/location selection evidence.
- Pass/fail evidence.

Harness opportunities:

- Add smoke-output row selection gate.
- Add tenability criterion source gate.
- Add visibility/margin/pass consistency gate.
- Add time-dependent scenario gate.

Natural products:

- `t-squared-hrr -> visibility-criterion` in a fire scenario package.
- `egress-width -> visibility-criterion` for evacuation route adequacy.
- `visibility-criterion -> performance-solution evidence artifact`.

Meta-harness handles:

- `projection`: smoke model table, egress route map, tenability criteria sheet.
- `difference`: include multiple times or visibility constants.
- `product`: smoke visibility tenability record.

## Task 7: Air Changes

Current world:

- Computes air changes per hour from supply airflow and room volume.
- Inputs are supply airflow in m3/h and room volume in m3.
- It is a direct ventilation-rate closure gate.
- Every difficulty tier exposes every input.

Multimodal expansion:

- Best first modality: room schedule plus ventilation schedule.
- A drawing variant can derive room volume from plan area and ceiling height.
- A hard variant can compare actual ACH to a criteria table or hazardous-room requirement.

Requirements:

- Supply airflow source.
- Room volume source or geometry.
- Scenario/source label for ventilation mode.
- Optional ACH criterion if extended.

Harness opportunities:

- Add room-geometry volume gate.
- Add ventilation schedule source gate.
- Add operating-mode selection gate.
- Add compliance gate if criteria are added.

Natural products:

- `air-changes -> gas-load-calculation` for plant-room ventilation and gas services context.
- `air-changes -> visibility-criterion` if smoke control/ventilation tasks are added.
- `air-changes -> acoustics` where ventilation equipment drives noise worlds.

Meta-harness handles:

- `projection`: room schedule, ventilation schedule, mechanical plan, section.
- `difference`: include supply, exhaust, outdoor, and recirculated flows.
- `product`: room ventilation rate record.

## Task 8: Gas Load Calculation

Current world:

- Computes connected gas load, diversified gas load, and both values in kW.
- Inputs are three appliance load/quantity pairs and a diversity factor.
- The conversion uses `3.6 MJ/h per kW`.
- Every difficulty tier exposes every input.

Multimodal expansion:

- Best first modality: gas appliance schedule.
- A commercial kitchen variant can require identifying connected appliances from plan tags.
- A hard variant can source diversity factor from a standard table or project gas load schedule.

Requirements:

- Appliance load and quantity source.
- Diversity factor source.
- Unit contract for MJ/h and kW.
- Optional meter/regulator capacity source if extended.

Harness opportunities:

- Add appliance-schedule extraction gate.
- Add diversity-factor source gate.
- Add connected-vs-diversified role gate.
- Add MJ/h-to-kW conversion gate.

Natural products:

- `gas-load-calculation -> pipe sizing/gas pressure tasks` if gas hydraulics are added.
- `gas-load-calculation -> ventilation air-changes` for plant-room or appliance ventilation packages.
- `gas-load-calculation -> electrical/mechanical energy performance` in whole-building services worlds.

Meta-harness handles:

- `projection`: appliance schedule, kitchen/plant-room plan, diversity table.
- `difference`: include standby appliances or future loads.
- `product`: gas connected and diversified load record.

## Task 9: A-Weighting

Current world:

- Computes total linear sound level, A-weighted total, and weighting adjustment.
- Inputs are octave-band levels from 31.5 Hz to 4000 Hz.
- The engine applies fixed A-weighting corrections and logarithmically sums levels.
- Every difficulty tier exposes every input.

Multimodal expansion:

- Best first modality: octave-band acoustic measurement table.
- A plant-noise variant can require selecting the relevant measurement location or equipment state.
- A hard variant can combine source spectra from several equipment items before A-weighting.

Requirements:

- Octave-band spectrum source.
- Measurement location/source state.
- A-weighting table or declared standard.
- Log-sum evidence.

Harness opportunities:

- Add band-label extraction gate.
- Add A-weighting coefficient gate.
- Add log-sum energy gate.
- Add spectrum/source-state selection gate.

Natural products:

- `spl-log-sum -> a-weighting` for multi-source octave spectra if extended.
- `a-weighting -> distance-attenuation` for environmental noise at receiver.
- `a-weighting -> sabine-rt60` only through shared room acoustic package, not direct numeric handoff.

Meta-harness handles:

- `projection`: octave-band table, measurement report, equipment noise datasheet.
- `difference`: shift band labels or include unweighted and weighted rows together.
- `product`: A-weighted noise level record.

## Task 10: Distance Attenuation

Current world:

- Computes distance ratio, attenuation, and target SPL.
- Inputs are reference SPL, reference distance, and target distance.
- The engine uses inverse-square point-source attenuation, `20 log10(r2/r1)`.
- Every difficulty tier exposes every input.

Multimodal expansion:

- Best first modality: source-receiver plan or acoustic site sketch.
- A hard variant can require measuring or extracting receiver distance from coordinates.
- A source-state variant can pair equipment SPL with operating scenario and target receiver.

Requirements:

- Reference SPL and distance source.
- Target distance source.
- Point-source assumption.
- Receiver identity/source evidence.

Harness opportunities:

- Add source-receiver geometry gate.
- Add model-assumption gate for point source.
- Add distance-ratio/log gate.
- Add receiver SPL handoff gate.

Natural products:

- `spl-log-sum -> distance-attenuation`.
- `a-weighting -> distance-attenuation`.
- `distance-attenuation -> environmental-noise compliance` if receiver criteria tasks are added.

Meta-harness handles:

- `projection`: site plan, source-receiver map, equipment noise datasheet.
- `difference`: include path length and straight-line distance as alternatives.
- `product`: receiver noise estimate.

## Task 11: Sabine RT60

Current world:

- Computes equivalent absorption area, average absorption coefficient, and reverberation time.
- Inputs are room volume, floor/wall/ceiling areas, and absorption coefficients.
- Absorption coefficients must be between zero and one.
- Every difficulty tier exposes every input.

Multimodal expansion:

- Best first modality: room finish schedule plus room geometry.
- A drawing variant can derive surface areas and volume from plans/sections.
- A hard variant can ask for reverberation before/after treatment using material alternatives.

Requirements:

- Room volume source.
- Surface area source.
- Absorption coefficient source by material/finish.
- Single-band assumption.

Harness opportunities:

- Add room-geometry extraction gate.
- Add finish-to-absorption source gate.
- Add equivalent absorption construction gate.
- Add RT60 formula gate.

Natural products:

- `sabine-rt60 -> a-weighting/spl-log-sum` in room acoustic package.
- `air-changes -> sabine-rt60` only through room geometry shared context.
- `sabine-rt60 -> acoustic treatment selection` if material selection tasks are added.

Meta-harness handles:

- `projection`: architectural plan, room section, finish schedule, absorption table.
- `difference`: mix area and volume records from different rooms.
- `product`: room reverberation record.

## Task 12: SPL Log Sum

Current world:

- Computes total linear energy, combined SPL, and dominant source SPL from three independent sources.
- Inputs are three source SPLs.
- The calculation uses logarithmic energy addition.
- Every difficulty tier exposes every input.

Multimodal expansion:

- Best first modality: equipment noise schedule with several sources.
- A room/plant variant can require selecting only simultaneously operating equipment.
- A hard variant can combine log-sum with distance attenuation or A-weighting.

Requirements:

- Source SPL table.
- Operating scenario/source inclusion rule.
- Evidence for logarithmic, not arithmetic, summation.
- Dominant-source identification.

Harness opportunities:

- Add source-inclusion gate.
- Add log-energy construction gate.
- Add dominant-source consistency gate.
- Add handoff to distance attenuation or A-weighting.

Natural products:

- `spl-log-sum -> distance-attenuation`.
- `spl-log-sum -> a-weighting` if octave-band source spectra are introduced.
- `spl-log-sum -> sabine-rt60` in room acoustic comfort packages.

Meta-harness handles:

- `projection`: equipment noise schedule, operating scenario, room/source map.
- `difference`: include standby or non-simultaneous equipment rows.
- `product`: combined source sound level record.

## Cross-Slice Product Worlds

### Life Safety Prescriptive Package

Candidate chain:

1. Read floor plan and occupancy schedule.
2. Compute occupant load with rounding.
3. Read egress plan and provided clear widths.
4. Compute required egress width and capacity margin.
5. Add NAC circuit capacity check for the same zone.

Why it is interesting:

- It is heavily source-driven and plan-driven.
- It separates occupant demand, physical egress capacity, and alarm circuit capacity.
- It can connect to electrical security, transport handling-capacity, and smoke tenability worlds.

### Fire Scenario And Tenability Package

Candidate chain:

1. Select a design-fire growth scenario.
2. Compute HRR at the relevant time and peak-limit branch.
3. Read smoke/visibility model output at the egress route and time.
4. Check visibility tenability criterion.
5. Optionally connect to steel critical temperature for structural-fire acceptance.

Why it is interesting:

- It introduces time-indexed evidence, not just static scalar calculations.
- It creates branch events around peak-limited fire growth and tenability failure.
- It is a natural place for meta-harness repair: change scenario, route, smoke control, or protection requirement.

### Building Services Room Package

Candidate chain:

1. Read room geometry and services schedules.
2. Compute ACH from airflow and room volume.
3. Compute gas connected/diversified load from appliance schedule.
4. Compute room acoustic RT60 and equipment/source SPL.
5. Produce a room-level environment and services record.

Why it is interesting:

- It lets one source pack drive ventilation, gas, and acoustics tasks.
- It tests source role labelling: room volume, surface area, equipment load, appliance load, and sound level must not collapse into one generic schedule value.
- It can link to electrical energy/performance and mechanical pump/plant-room tasks.

### Acoustic Source-To-Receiver Package

Candidate chain:

1. Read equipment noise schedule.
2. Log-sum simultaneous source SPLs.
3. Apply A-weighting if octave-band data is supplied.
4. Apply distance attenuation to a receiver.
5. Compare against a future criterion or produce an evidence record.

Why it is interesting:

- It requires logarithmic reasoning across multiple transformations.
- It can be made multimodal with equipment schedules, source maps, room drawings, and receiver plans.
- It gives the meta-harness clear repair levers: source inclusion, band labelling, distance geometry, and receiver selection.

## Repair And Extension Notes

- `egress-width` can emit infinite utilisation when provided width is zero. That is fine as a scalar edge case, but a composed verifier should explicitly flag zero-width/source-missing cases instead of treating `inf` as an ordinary numeric result.
- `t-squared-hrr` exposes a useful branch variable, `peak_limited`. Future fire scenario worlds should require the model to state whether the branch is active.
- `steel-critical-temp` is a strong cross-discipline bridge, but load ratio provenance needs a sidecar. A structural utilisation ratio and a structural-fire load ratio are not automatically the same thing.
- The acoustic tasks are simple individually but powerful in composition. The main verifier risk is arithmetic addition of dB values where log-sum is required.
