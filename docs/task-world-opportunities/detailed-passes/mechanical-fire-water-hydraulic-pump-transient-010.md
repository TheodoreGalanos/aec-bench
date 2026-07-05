# ABOUTME: Detailed task-world review for mechanical fire-water, pipe hydraulics, pump, and transient tasks.
# ABOUTME: Records multimodal, composition, and meta-harness opportunities for the first mechanical discipline slice.

# Mechanical Fire Water Hydraulic Pump And Transient Pass 010

Review date: 2026-06-28

Reviewed task cards:

- `mechanical/hydrant-flow-test/available-flow-calculation`
- `mechanical/hydrant-flow-test/water-supply-curve`
- `mechanical/pipe-hydraulics/hazen-williams-friction`
- `mechanical/pipe-sizing-water/pressure-loss-calculation`
- `mechanical/sprinkler-hydraulics/friction-loss-hazen-williams`
- `mechanical/sprinkler-hydraulics/elevation-pressure`
- `mechanical/sprinkler-hydraulics/sprinkler-discharge`
- `mechanical/pipe-hydraulics/minor-losses-calculation`
- `mechanical/pipe-hydraulics/velocity-check`
- `mechanical/thrust-restraint/thrust-force-calculation`
- `mechanical/transient-analysis/wave-speed-calculation`
- `mechanical/transient-analysis/joukowsky-pressure`
- `mechanical/pump-hydraulics/pump-head-calculation`
- `mechanical/pump-hydraulics/npsh-available`
- `mechanical/pump-sizing/pump-affinity-laws`
- `mechanical/pump-sizing/pump-power-calculation`
- `mechanical/pump-hydraulics/pump-power-efficiency`
- `mechanical/system-curves/por-aor-compliance`

Source files read for this pass:

- `src/aec_bench/templates/builtin/mechanical/available_flow_calculation/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/mechanical/water_supply_curve/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/mechanical/hazen_williams_friction/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/mechanical/pressure_loss_calculation/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/mechanical/friction_loss_hazen_williams/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/mechanical/elevation_pressure/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/mechanical/sprinkler_discharge/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/mechanical/minor_losses_calculation/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/mechanical/velocity_check/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/mechanical/thrust_force_calculation/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/mechanical/wave_speed_calculation/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/mechanical/joukowsky_pressure/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/mechanical/pump_head_calculation/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/mechanical/npsh_available/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/mechanical/pump_affinity_laws/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/mechanical/pump_power_calculation/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/mechanical/pump_power_efficiency/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/mechanical/por_aor_compliance/{params.toml,instruction.md,engine.py}`

## Slice Read

This mechanical slice is currently all-scalar and all-given across every difficulty tier. There are no hidden parameters to infer from prose. That makes the immediate multimodal opportunity very clear: keep these templates as deterministic closure gates, but replace the directly provided scalars with source evidence from hydrant test sheets, hydraulic calculation sheets, sprinkler layouts, pipe schedules, P&IDs, pump curves, pump submittals, transient assumptions, and thrust-restraint drawings.

The strongest composition axis is a fire-water or pump-station hydraulic package:

- hydrant source capacity: `available-flow-calculation` and `water-supply-curve`;
- sprinkler and pipe demand: `sprinkler-discharge`, `friction-loss-hazen-williams`, `elevation-pressure`, `hazen-williams-friction`, `pressure-loss-calculation`, `minor-losses-calculation`, and `velocity-check`;
- pump duty and equipment selection: `pump-head-calculation`, `npsh-available`, `pump-affinity-laws`, `pump-power-calculation`, `pump-power-efficiency`, and `por-aor-compliance`;
- pressure integrity and restraint: `wave-speed-calculation`, `joukowsky-pressure`, and `thrust-force-calculation`.

The interesting meta-harness setting is therefore not just harder arithmetic. It is a source-to-network task world: read a system, extract the operating point, construct pipe losses and elevations, check pump duty, then propagate outputs into electrical load sizing, structural pipe support, civil pump station duty, or thrust-restraint design.

## Task 1: Available Flow Calculation

Current world:

- Computes test pressure drop, target pressure drop, available fire flow in L/s, and available flow in m3/h.
- Inputs are static pressure, residual pressure, test flow, and target residual pressure.
- The formula uses the hydrant-flow exponent `0.54`.
- Every difficulty tier exposes every input.

Multimodal expansion:

- Best first modality: hydrant flow test sheet or scanned commissioning record.
- A second useful modality is a pressure-flow curve where the model must read the test point and target residual.
- A hard variant can include multiple hydrant tests and require selecting the test that matches the site context.

Requirements:

- Source row for static pressure, residual pressure, and test flow.
- Target residual pressure source or design criterion.
- Unit contract for kPa and L/s.
- Evidence that the selected pressure drop is positive.

Harness opportunities:

- Add a hydrant-test source-authority gate.
- Add a pressure-drop construction gate before flow extrapolation.
- Add a unit-consistency gate between L/s and m3/h.
- Add a handoff gate to sprinkler demand or fire-water storage tasks.

Natural products:

- `available-flow-calculation -> water-supply-curve` as a method-comparison pair.
- `available-flow-calculation -> sprinkler-discharge -> friction-loss-hazen-williams` as a supply-demand check.
- `available-flow-calculation -> civil pump station duty` when a booster or tank is required.

Meta-harness handles:

- `projection`: hydrant test form, pressure-flow graph, fire services design basis.
- `difference`: include distractor tests or remove target-residual labels.
- `product`: fire-water supply adequacy package.

## Task 2: Water Supply Curve

Current world:

- Computes pressure drop at the flow test, curve coefficient, flow at target residual, and available flow at 20 psi.
- Inputs are static pressure, residual pressure, test flow, and target residual pressure in imperial units.
- The formula uses the same `0.54` exponent as the available-flow task.
- Every difficulty tier exposes every input.

Multimodal expansion:

- Best first modality: hydrant flow test sheet with psi/gpm fields.
- A curve-plot variant can require extracting the test point from a graph and then reporting 20 psi available flow.
- A standards-context variant can require identifying whether 20 psi is the correct residual criterion for the scenario.

Requirements:

- Test pressure and flow source.
- Target residual and 20 psi residual criterion.
- Explicit imperial unit contract.
- Evidence for curve coefficient and target-flow calculation.

Harness opportunities:

- Add a method-equivalence gate with `available-flow-calculation`.
- Add a curve-coefficient construction gate.
- Add a source-vs-output graph consistency gate.
- Add a target-residual branch gate when target residual differs from 20 psi.

Natural products:

- `water-supply-curve -> sprinkler-discharge/friction-loss-hazen-williams` for sprinkler hydraulic adequacy.
- `water-supply-curve -> pump-head-calculation` when a fire booster is introduced.
- `water-supply-curve <-> available-flow-calculation` for metric/imperial consistency worlds.

Meta-harness handles:

- `projection`: hydrant test sheet, pressure-flow curve, fire hydraulic calculation cover sheet.
- `difference`: mix psi/kPa and gpm/L/s source pages to test unit discipline.
- `product`: fire supply curve record.

## Task 3: Hazen-Williams Friction

Current world:

- Computes flow rate in m3/s, pipe head loss, pressure loss, and hydraulic gradient.
- Inputs are pipe length, internal diameter, flow rate, Hazen-Williams `C`, and fluid density.
- The engine uses the metric Hazen-Williams coefficient `10.67`.
- Every difficulty tier exposes every input.

Multimodal expansion:

- Best first modality: pipe schedule plus material roughness table.
- A long-section variant can require extracting pipe length and diameter from a drawing or schedule.
- A material-source variant can require selecting the `C` value from pipe material and age/condition.

Requirements:

- Pipe length, internal diameter, and flow source.
- Material or condition source for `C`.
- Density source when the fluid is not ordinary water.
- Handoff field for head loss or pressure loss.

Harness opportunities:

- Add a pipe-schedule extraction gate.
- Add a `C` source-authority gate.
- Add a head-loss-to-pressure-loss unit gate.
- Add a hydraulic-gradient consistency gate.

Natural products:

- `hazen-williams-friction -> pump-head-calculation` for total dynamic head.
- `hazen-williams-friction -> velocity-check` for pipe sizing and compliance.
- `hazen-williams-friction -> pressure-loss-calculation` where fittings are added to the same reach.

Meta-harness handles:

- `projection`: pipe schedule, long section, material table.
- `difference`: remove material labels or swap nominal and internal diameters.
- `product`: pipe reach hydraulic-loss record.

## Task 4: Pressure Loss Calculation

Current world:

- Computes velocity, Hazen-Williams friction loss, fitting loss, and total pressure loss.
- Inputs are flow, internal diameter, pipe length, `C`, total fitting `K`, and fluid density.
- It combines distributed pipe loss and local fitting loss.
- Every difficulty tier exposes every input.

Multimodal expansion:

- Best first modality: P&ID or pipe run takeoff with a fitting schedule.
- A hydraulic-calculation-sheet variant can require reconciling pipe length, fittings, and fluid density.
- A hard variant can ask for the governing pressure loss across several branches.

Requirements:

- Pipe geometry source.
- Flow source or upstream demand handoff.
- Fitting count and `K` source.
- Roughness and density source.
- Total pressure-loss handoff.

Harness opportunities:

- Add fitting-takeoff and total-`K` gates.
- Add velocity construction gate before fitting loss.
- Add distributed/local loss separation gate.
- Add branch-governing selection gate for multi-branch worlds.

Natural products:

- `minor-losses-calculation -> pressure-loss-calculation` when fitting losses are first calculated as head loss or equivalent length.
- `pressure-loss-calculation -> pump-head-calculation` for pump TDH.
- `pressure-loss-calculation -> velocity-check` for same-reach compliance.

Meta-harness handles:

- `projection`: P&ID, pipe schedule, fitting table, hydraulic calculation sheet.
- `difference`: include fittings on a different branch as distractors.
- `product`: pressure-loss calculation package.

## Task 5: Friction Loss Hazen-Williams

Current world:

- Computes friction loss per foot, equivalent length, pipe friction loss, and total pressure loss in psi.
- Inputs are sprinkler flow, pipe length, internal diameter, `C`, and fitting equivalent length.
- The engine uses the NFPA imperial Hazen-Williams coefficient `4.52`.
- Every difficulty tier exposes every input.

Multimodal expansion:

- Best first modality: sprinkler hydraulic calculation sheet or branch-line schedule.
- A drawing variant can require identifying the branch line or feed main from a sprinkler plan.
- A hard variant can require extracting equivalent fitting length from a fitting schedule.

Requirements:

- Flow source from sprinkler demand or hydraulic node.
- Pipe schedule and internal diameter source.
- Equivalent length source.
- Unit contract for ft, in, gpm, and psi.

Harness opportunities:

- Add sprinkler-branch source gate.
- Add equivalent-length construction gate.
- Add imperial Hazen-Williams unit gate.
- Add pipe-only vs total-loss consistency gate.

Natural products:

- `sprinkler-discharge -> friction-loss-hazen-williams -> elevation-pressure` as a sprinkler branch calculation.
- `water-supply-curve -> friction-loss-hazen-williams` for supply-demand adequacy.
- `friction-loss-hazen-williams <-> pressure-loss-calculation` as imperial/metric method contrast.

Meta-harness handles:

- `projection`: sprinkler plan, branch schedule, hydraulic calculation sheet.
- `difference`: mix branch-line and feed-main rows.
- `product`: sprinkler pipe loss package.

## Task 6: Elevation Pressure

Current world:

- Computes elevation head, pressure change in kPa, and pressure change in bar.
- Inputs are fluid density and elevation change.
- The sign of elevation change is meaningful: positive produces positive pressure change in the current engine.
- Every difficulty tier exposes every input.

Multimodal expansion:

- Best first modality: riser diagram or pump station section.
- A profile variant can require reading upstream/downstream elevations and deriving the elevation change.
- A hard variant can test sign convention between pump head, sprinkler pressure loss, and static pressure change.

Requirements:

- Elevation datum and two point elevations.
- Fluid density source.
- Explicit sign convention.
- Handoff to pressure/head calculations.

Harness opportunities:

- Add datum consistency gate.
- Add elevation sign-convention gate.
- Add pressure/head/bar unit gate.
- Add cross-check against pump static head.

Natural products:

- `elevation-pressure -> friction-loss-hazen-williams` for sprinkler hydraulic node pressure.
- `elevation-pressure -> pump-head-calculation` for total static head.
- `elevation-pressure -> npsh-available` for suction elevation cases.

Meta-harness handles:

- `projection`: riser diagram, hydraulic profile, pump station section.
- `difference`: invert elevation direction or hide datum labels.
- `product`: elevation pressure adjustment record.

## Task 7: Sprinkler Discharge

Current world:

- Computes sprinkler discharge in L/min and L/s plus pressure in kPa.
- Inputs are sprinkler K-factor and operating pressure in bar.
- The calculation is `Q = K * sqrt(P)`.
- Every difficulty tier exposes every input.

Multimodal expansion:

- Best first modality: sprinkler datasheet plus ceiling/fire-zone layout.
- A drawing variant can require selecting the design sprinkler type from a room/zone.
- A hydraulic-sheet variant can require extracting operating pressure at the remote sprinkler.

Requirements:

- K-factor source.
- Operating pressure source.
- Unit contract for bar, kPa, L/min, and L/s.
- Optional count/area field for total demand if extended.

Harness opportunities:

- Add sprinkler-type source gate.
- Add pressure source gate.
- Add flow unit conversion gate.
- Add handoff to pipe friction and water-supply tasks.

Natural products:

- `sprinkler-discharge -> friction-loss-hazen-williams` for pipe flow.
- `sprinkler-discharge -> water-supply-curve` for supply adequacy.
- `sprinkler-discharge -> pump-power-calculation` if a fire pump is needed.

Meta-harness handles:

- `projection`: sprinkler datasheet, sprinkler layout, hydraulic node table.
- `difference`: include multiple sprinkler K-factors.
- `product`: sprinkler demand record.

## Task 8: Minor Losses Calculation

Current world:

- Computes total fitting `K`, velocity head, total minor loss, and equivalent length.
- Inputs include three fitting `K` values with quantities, flow velocity, pipe diameter, and Darcy friction factor.
- Equivalent length is derived from the minor loss, diameter, friction factor, and velocity head.
- Every difficulty tier exposes every input.

Multimodal expansion:

- Best first modality: P&ID or fittings takeoff table.
- A drawing variant can require counting valves, bends, tees, and appurtenances on a pipe run.
- A hard variant can compare explicit `K` losses with equivalent-length methods.

Requirements:

- Fitting type and quantity source.
- `K` coefficient table.
- Velocity and pipe diameter source.
- Darcy friction factor source.
- Clear method label for `K` vs equivalent length.

Harness opportunities:

- Add fitting-count extraction gate.
- Add coefficient-source gate.
- Add total-`K` construction gate.
- Add equivalent-length consistency gate.

Natural products:

- `minor-losses-calculation -> pressure-loss-calculation`.
- `minor-losses-calculation -> pump-head-calculation`.
- `minor-losses-calculation -> velocity-check` when the same pipe velocity is reused.

Meta-harness handles:

- `projection`: P&ID, fitting schedule, Crane/AWWA coefficient table.
- `difference`: add fittings that are shown but not on the selected path.
- `product`: fitting loss takeoff.

## Task 9: Velocity Check

Current world:

- Computes pipe area, velocity, margins to minimum and maximum velocity, and a pass flag.
- Inputs are flow rate, internal diameter, minimum velocity, and maximum velocity.
- The pass flag is `1.0` when velocity lies inside the inclusive range.
- Every difficulty tier exposes every input.

Multimodal expansion:

- Best first modality: pipe schedule plus design-criteria table.
- A network variant can require selecting the critical pipe segment from several rows.
- A hard variant can combine velocity limits with pressure-loss and pump duty.

Requirements:

- Flow source.
- Internal diameter source.
- Velocity criteria source.
- Pass/fail criterion.

Harness opportunities:

- Add criteria-source gate.
- Add diameter-source gate that distinguishes nominal and internal diameter.
- Add pass-flag consistency gate.
- Add minimum and maximum margin sign gates.

Natural products:

- `velocity-check -> pressure-loss-calculation`.
- `velocity-check -> thrust-force-calculation` where pressure and diameter are reused.
- `velocity-check -> pump-head-calculation` in a pipe sizing package.

Meta-harness handles:

- `projection`: pipe schedule, design criteria, hydraulic node table.
- `difference`: include nominal diameter distractors.
- `product`: pipe velocity compliance record.

## Task 10: Thrust Force Calculation

Current world:

- Computes pipe area, pressure force, and bend thrust force.
- Inputs are internal pressure, internal diameter, and bend angle.
- The thrust formula is `2 * pressure_force * sin(angle / 2)`.
- Every difficulty tier exposes every input.

Multimodal expansion:

- Best first modality: pipe alignment plan or thrust-block schedule.
- A profile/P&ID variant can require identifying the bend angle and design pressure.
- A transient variant can add surge pressure from Joukowsky pressure rise.

Requirements:

- Bend angle source.
- Pipe internal diameter source.
- Design pressure source.
- Optional surge pressure handoff.
- Restraint or thrust-block acceptance criterion if extended.

Harness opportunities:

- Add bend-angle extraction gate.
- Add pressure-source gate.
- Add base-pressure plus surge-pressure composition gate.
- Add force-unit consistency gate.

Natural products:

- `joukowsky-pressure -> thrust-force-calculation` for surge restraint.
- `pressure-loss-calculation -> thrust-force-calculation` where operating pressure is known at the bend.
- `thrust-force-calculation -> structural/ground foundation checks` for thrust block bearing.

Meta-harness handles:

- `projection`: pipe alignment plan, thrust-block detail, pressure profile.
- `difference`: hide whether pressure is operating, test, or surge pressure.
- `product`: thrust restraint design action.

## Task 11: Wave Speed Calculation

Current world:

- Computes fluid-only wave speed, pipe flexibility ratio, flexibility factor, and wave speed.
- Inputs are fluid bulk modulus, fluid density, pipe elastic modulus, pipe diameter, pipe wall thickness, and restraint condition.
- The restraint condition maps to factors for fully restrained, anchored with expansion, or unrestrained pipes.
- Every difficulty tier exposes every input.

Multimodal expansion:

- Best first modality: pipe material schedule plus restraint/detail note.
- A datasheet variant can require extracting elastic modulus, wall thickness, and class.
- A hard variant can require classifying restraint from supports, anchors, and expansion joints on a drawing.

Requirements:

- Fluid property source.
- Pipe material and wall thickness source.
- Restraint condition source.
- Handoff field for wave speed.

Harness opportunities:

- Add restraint-classification gate.
- Add pipe-flexibility construction gate.
- Add material-property source gate.
- Add handoff gate to `joukowsky-pressure`.

Natural products:

- `wave-speed-calculation -> joukowsky-pressure`.
- `wave-speed-calculation -> thrust-force-calculation` through surge pressure.
- `wave-speed-calculation -> pump-affinity-laws` in a pump shutdown/startup scenario.

Meta-harness handles:

- `projection`: pipe material schedule, pipe support drawing, transient scenario note.
- `difference`: remove restraint labels and force inference from anchors/expansion joints.
- `product`: transient screening input record.

## Task 12: Joukowsky Pressure

Current world:

- Computes pressure rise in Pa, pressure rise in kPa, and pressure head.
- Inputs are fluid density, wave speed, and velocity change.
- Velocity change must be non-negative in the current engine.
- Every difficulty tier exposes every input.

Multimodal expansion:

- Best first modality: transient scenario note or pump shutdown case.
- A pump-control variant can derive velocity change from flow, diameter, and valve/pump event.
- A hard variant can combine pipe wave speed and operating velocity before calculating surge pressure.

Requirements:

- Fluid density source.
- Wave speed handoff or source.
- Velocity-change source or derivation.
- Unit contract for pressure and pressure head.

Harness opportunities:

- Add handoff gate from `wave-speed-calculation`.
- Add velocity-change derivation gate.
- Add pressure/head consistency gate.
- Add surge-pressure handoff to thrust and pump-rating checks.

Natural products:

- `wave-speed-calculation -> joukowsky-pressure -> thrust-force-calculation`.
- `velocity-check -> joukowsky-pressure` if velocity change is derived from pipe flow.
- `joukowsky-pressure -> pump_head or pipe rating` in a transient acceptance package.

Meta-harness handles:

- `projection`: pump trip note, valve closure scenario, transient screening worksheet.
- `difference`: include multiple operating cases with different velocity changes.
- `product`: surge pressure screening record.

## Task 13: Pump Head Calculation

Current world:

- Computes static head, pressure head differential, friction head, total dynamic head, and hydraulic power.
- Inputs are flow, suction pressure, discharge pressure, elevation difference, pipe friction losses, and fluid density.
- The friction and pressure inputs are converted from kPa to head.
- Every difficulty tier exposes every input.

Multimodal expansion:

- Best first modality: pump station section plus hydraulic profile.
- A P&ID/system-curve variant can require extracting suction/discharge pressure nodes and pipe losses.
- A hard variant can require comparing several operating cases and choosing the governing TDH.

Requirements:

- Flow source.
- Suction/discharge pressure source.
- Elevation source.
- Friction loss handoff from pipe calculations.
- Fluid density source.

Harness opportunities:

- Add pressure-reference gate for gauge/absolute conventions.
- Add elevation sign gate.
- Add friction-loss handoff gate.
- Add TDH-to-power consistency gate.

Natural products:

- `pressure-loss-calculation -> pump-head-calculation`.
- `pump-head-calculation -> pump-power-calculation` and `pump-power-efficiency`.
- `pump-head-calculation -> npsh-available` in a pump station duty package.

Meta-harness handles:

- `projection`: pump station section, P&ID, hydraulic profile, system curve.
- `difference`: hide whether the elevation difference is suction-to-discharge or pump-to-static level.
- `product`: pump duty calculation package.

## Task 14: NPSH Available

Current world:

- Computes pressure head, vapor pressure head, loss head, NPSH available, cavitation margin, and margin ratio.
- Inputs are suction vessel absolute pressure, liquid level above pump, suction pipe losses, vapor pressure absolute, fluid density, and NPSH required.
- The task explicitly compares NPSHA with NPSHR but does not emit a binary pass flag.
- Every difficulty tier exposes every input.

Multimodal expansion:

- Best first modality: suction vessel data sheet plus pump curve.
- A process-fluid variant can require extracting vapor pressure from fluid temperature.
- A pump station drawing variant can derive static suction head from vessel level and pump centerline.

Requirements:

- Absolute suction pressure source.
- Liquid level and pump datum source.
- Suction loss source.
- Vapor pressure source.
- Pump NPSHR source.

Harness opportunities:

- Add absolute-vs-gauge pressure gate.
- Add suction elevation datum gate.
- Add vapor-pressure source gate.
- Add cavitation-margin compliance gate.

Natural products:

- `pressure-loss-calculation -> npsh-available` for suction line losses.
- `npsh-available -> pump-head-calculation` as part of pump duty acceptance.
- `npsh-available -> pump-affinity-laws` when operating speed changes affect flow and NPSHR.

Meta-harness handles:

- `projection`: pump curve, suction vessel datasheet, fluid property table, pump station section.
- `difference`: provide gauge pressure in the source and require conversion to absolute.
- `product`: pump suction/cavitation check.

## Task 15: Pump Affinity Laws

Current world:

- Computes speed ratio, new flow, new head, and new power.
- Inputs are original speed, new speed, original flow, original head, and original power.
- It assumes same pump geometry and uses the classic linear/square/cube affinity relationships.
- Every difficulty tier exposes every input.

Multimodal expansion:

- Best first modality: pump curve or VSD schedule.
- A system-curve variant can compare the affinity-law estimate against an operating point.
- A hard variant can require determining whether the same-pump assumption is valid from a submittal note.

Requirements:

- Original operating point source.
- New speed source.
- Same-pump/same-impeller assumption source.
- Handoff of new flow/head/power.

Harness opportunities:

- Add same-pump assumption gate.
- Add speed-ratio construction gate.
- Add cubic-power consistency gate.
- Add downstream operating-range gate with `por-aor-compliance`.

Natural products:

- `pump-affinity-laws -> por-aor-compliance`.
- `pump-affinity-laws -> pump-power-calculation`.
- `pump-affinity-laws -> electrical power-load-calculation` for changed motor demand.

Meta-harness handles:

- `projection`: pump curve, VSD schedule, pump submittal.
- `difference`: include impeller-trim data that should not be treated as speed change.
- `product`: variable-speed pump operating-point estimate.

## Task 16: Pump Power Calculation

Current world:

- Computes flow in m3/s, hydraulic power, shaft power, and efficiency fraction.
- Inputs are flow, total dynamic head, density, and pump efficiency.
- It uses L/s input and reports kW outputs.
- Every difficulty tier exposes every input.

Multimodal expansion:

- Best first modality: pump duty schedule plus pump efficiency curve.
- A handoff variant can take TDH from `pump-head-calculation`.
- A hard variant can require selecting efficiency at the operating point from a curve.

Requirements:

- Flow and TDH source.
- Fluid density source.
- Efficiency source.
- Unit conversion evidence.

Harness opportunities:

- Add TDH handoff gate.
- Add efficiency-curve source gate.
- Add hydraulic-vs-shaft-power separation gate.
- Add unit gate for L/s to m3/s.

Natural products:

- `pump-head-calculation -> pump-power-calculation`.
- `pump-power-calculation -> pump-power-efficiency`.
- `pump-power-calculation -> electrical power-load-calculation`.

Meta-harness handles:

- `projection`: pump schedule, efficiency curve, duty-point table.
- `difference`: include multiple efficiencies at different flow points.
- `product`: pump shaft power calculation.

## Task 17: Pump Power Efficiency

Current world:

- Computes hydraulic power, shaft power, motor input power, and recommended motor size.
- Inputs are flow in m3/h, TDH, density, pump efficiency, motor efficiency, and motor sizing factor.
- The output is closer to equipment sizing than the simpler pump power task.
- Every difficulty tier exposes every input.

Multimodal expansion:

- Best first modality: pump datasheet plus motor schedule.
- A project-standard variant can source the motor sizing factor from design criteria.
- A hard variant can join hydraulic duty, pump efficiency curve, motor efficiency, and standard motor size selection.

Requirements:

- Flow and TDH source.
- Pump and motor efficiency sources.
- Motor sizing factor source.
- Optional standard motor size table if extended beyond the current numeric recommendation.

Harness opportunities:

- Add motor-efficiency source gate.
- Add sizing-factor authority gate.
- Add recommended-power gate.
- Add electrical handoff gate for connected load.

Natural products:

- `pump-head-calculation -> pump-power-efficiency -> electrical power-load-calculation`.
- `pump-affinity-laws -> pump-power-efficiency` for changed pump speed.
- `pump-power-efficiency -> structural pipe/support/foundation package` where pump and pipe loads share equipment records.

Meta-harness handles:

- `projection`: pump datasheet, motor schedule, design criteria, electrical load list.
- `difference`: include motor output power and input power in the same source.
- `product`: pump motor sizing record.

## Task 18: POR AOR Compliance

Current world:

- Computes operating-flow ratio to best-efficiency flow, margins to POR limits, and binary within-POR/within-AOR flags.
- Inputs are operating flow, best-efficiency flow, POR min/max ratios, and AOR min/max ratios.
- The input validation enforces `AOR min <= POR min <= POR max <= AOR max`.
- Every difficulty tier exposes every input.

Multimodal expansion:

- Best first modality: pump curve with BEP and operating point.
- A standard-range variant can source POR/AOR ratios from Hydraulic Institute guidance or project criteria.
- A hard variant can ask whether a changed-speed operating point remains inside preferred or allowable range.

Requirements:

- Operating flow source.
- BEP flow source.
- POR/AOR ratio source.
- Pass/fail evidence for both ranges.

Harness opportunities:

- Add pump-curve extraction gate.
- Add range-authority gate.
- Add POR and AOR flag consistency gates.
- Add operating-point repair event when the point is outside POR but still inside AOR.

Natural products:

- `pump-affinity-laws -> por-aor-compliance`.
- `pump-head-calculation -> por-aor-compliance` when the operating point is taken from system curve intersection.
- `por-aor-compliance -> pump selection/redesign meta-harness event`.

Meta-harness handles:

- `projection`: pump curve, system curve, operating point table, HI range note.
- `difference`: hide BEP label or give multiple candidate operating points.
- `product`: pump operating range compliance record.

## Cross-Slice Product Worlds

### Fire-Water Supply And Sprinkler Demand Package

Candidate chain:

1. Read hydrant test sheet and construct supply curve.
2. Read sprinkler layout and compute sprinkler demand.
3. Calculate sprinkler pipe friction and elevation pressure.
4. Compare demand pressure/flow against available supply.

Why it is interesting:

- It combines source interpretation, imperial/metric unit discipline, pressure-flow curve extrapolation, and hydraulic network reasoning.
- It can be tested as text-only, table-source, drawing-source, or mixed scan/table variants.
- It exposes whether a model can preserve supply and demand as separate curves instead of collapsing them into a single scalar.

### Pipe Reach Hydraulic Loss Package

Candidate chain:

1. Read pipe schedule and selected run.
2. Compute velocity and check criteria.
3. Compute distributed Hazen-Williams loss.
4. Compute fitting/minor losses.
5. Produce total pressure loss for pump TDH.

Why it is interesting:

- It creates natural handoffs between pipe geometry, velocity, friction loss, fitting loss, and pump duty.
- It supports branch-governing variants where only one pipe run controls the system.
- It can connect directly to civil sewer/water pipe tasks and structural pipe support tasks.

### Pump Station Duty And Electrical Handoff Package

Candidate chain:

1. Read pump station section and hydraulic profile.
2. Compute total dynamic head.
3. Check NPSH available against pump curve.
4. Compute shaft and motor input power.
5. Check POR/AOR at the operating point.
6. Handoff connected load to electrical power tasks.

Why it is interesting:

- It is a real product-world package: one pump cannot be accepted by head alone.
- It creates separate failure modes for suction, duty point, efficiency, motor sizing, and range compliance.
- It naturally links mechanical, civil, and electrical templates.

### Transient And Thrust Restraint Package

Candidate chain:

1. Read pipe material, wall thickness, and restraint condition.
2. Compute pressure wave speed.
3. Compute Joukowsky pressure rise from the transient event.
4. Add surge pressure to design pressure.
5. Compute bend thrust and pass the action to a restraint/block/foundation check.

Why it is interesting:

- It tests whether a model can propagate a transient pressure into a structural action.
- It requires scenario selection: pump trip, valve closure, rapid startup, or shutdown.
- It gives the meta-harness a repair path: if surge controls the design, reroute the pipe-restraint package.

## Repair And Extension Notes

- The current slice has no hidden parameters; difficulty is mostly range/archetype variation rather than inference. Multimodal expansion should add source artifacts and explicit extraction gates before adding more formula variants.
- Several templates use overlapping concepts with different units: metric Hazen-Williams, imperial sprinkler Hazen-Williams, L/s pump power, m3/h pump motor sizing, kPa pressure loss, psi fire-supply curves. A `unit_system` sidecar would make cross-template composition much safer.
- `npsh-available` has an implicit compliance story through margin and margin ratio but no binary pass flag. If a composed pump package needs deterministic pass/fail, add a named `cavitation_margin_pass` or require a verifier gate over the existing margin.
- Pump and hydrant curve worlds should distinguish source points, fitted/extrapolated curves, and operating points. Without that distinction, a model can report a plausible final flow while using the wrong curve segment.
