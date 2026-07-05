# ABOUTME: Detailed task-world review for structural marine, support, section, tolerance, and material tasks.
# ABOUTME: Records multimodal, composition, and meta-harness opportunities for the structural discipline slice.

# Structural Systems And Materials Pass 009

Review date: 2026-06-28

Reviewed task cards:

- `structural/berthing-energy/berthing-energy-calc`
- `structural/fender-design/fender-energy-check`
- `structural/marine-mooring/mooring-line-capacity`
- `structural/wind-load-analysis/effective-wind-area`
- `structural/bracket-connection/bracket-load-calc`
- `structural/pipe-support/pipe-support-dead-load`
- `structural/wind-turbine-foundations/gravity-base-stability`
- `structural/load-analysis/load-combinations`
- `structural/superstructure-design/composite-section`
- `structural/rebar-detailing/lap-splice-length`
- `structural/construction-tolerance/construction-tolerance`
- `structural/movement-tolerance/thermal-movement-calc`
- `structural/steel-specification/carbon-equivalent-calc`
- `structural/concrete-mix-design/scm-substitution`
- `structural/concrete-mix-design/target-strength-calc`

Source files read for this pass:

- `src/aec_bench/templates/builtin/structural/berthing_energy_calc/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/structural/fender_energy_check/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/structural/mooring_line_capacity/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/structural/effective_wind_area/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/structural/bracket_load_calc/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/structural/pipe_support_dead_load/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/structural/gravity_base_stability/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/structural/load_combinations/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/structural/composite_section/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/structural/lap_splice_length/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/structural/construction_tolerance/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/structural/thermal_movement_calc/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/structural/carbon_equivalent_calc/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/structural/scm_substitution/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/structural/target_strength_calc/{params.toml,instruction.md,engine.py}`

## Slice Read

The structural discipline currently has fewer hidden-parameter tasks than civil or ground. Most templates give all scalar inputs directly and rely on explicit factors. That does not make them weak candidates for richer task worlds. It shifts the multimodal opportunity toward source extraction, handoff integrity, and artifact consistency:

- marine source packs: vessel schedules, berth layouts, fender datasheets, mooring analysis outputs;
- building and plant supports: facade elevations, bracket details, pipe schedules, load tables, support drawings;
- foundations and ground interface: gravity-base reactions, allowable bearing pressure, middle-third checks;
- bridge and concrete detailing: composite section drawings, reinforcement schedules, lap splice notes;
- constructability and material compliance: tolerance stack-ups, movement joints, mill certificates, concrete mix designs, production records.

The best cross-discipline bridges are already visible: civil wind/load tasks feed facade, bracket, and structural load-combination tasks; ground foundation tasks receive gravity-base and support reactions; mechanical pipe tasks can feed pipe-support dead load; marine/coastal tasks can feed berth and fender contexts.

## Task 1: Berthing Energy Calculation

Current world:

- Computes kinetic energy, characteristic berthing energy, design berthing energy, and coefficient product.
- Inputs are vessel displacement, approach velocity, added mass coefficient, eccentricity coefficient, berth configuration coefficient, softness coefficient, and safety factor.
- All parameters are visible in every difficulty tier.
- The engine converts tonnes to kilograms and divides by 1000 to report kNm.

Multimodal expansion:

- Best first modality: vessel schedule plus berth approach diagram.
- A berth layout can expose approach angle, berth type, and configuration.
- A vessel schedule can expose displacement and design vessel class.
- A design basis table can expose coefficient and safety-factor choices.

Requirements:

- Vessel displacement source.
- Approach velocity/source scenario.
- Coefficient table or design-basis record.
- Berth configuration source.
- Energy handoff field for fender capacity check.

Harness opportunities:

- Add vessel-source gate for displacement.
- Add scenario gate for approach velocity.
- Add coefficient-product construction gate.
- Add handoff gate to `fender-energy-check`.
- Add event trigger if design energy is not characteristic energy times safety factor.

Natural products:

- `berthing-energy-calc -> fender-energy-check` as the marine berth energy chain.
- `berthing-energy-calc -> mooring-line-capacity` in a berth operation package.
- `berthing-energy-calc -> coastal/wave context` where berth exposure affects approach assumptions.

Meta-harness handles:

- `projection`: vessel schedule, berth layout, coefficient table, design basis note.
- `difference`: remove coefficient source labels or hide berth configuration cues.
- `product`: marine berth design package.

## Task 2: Fender Energy Check

Current world:

- Computes total correction factor, corrected fender capacity, energy utilisation, and capacity margin.
- Inputs are design berthing energy, fender rated energy, temperature, velocity, angular, and manufacturing tolerance factors.
- All parameters are visible.
- The task is a capacity/utilisation check rather than a fender selection routine.

Multimodal expansion:

- Best first modality: fender datasheet plus berth environmental/context note.
- A datasheet can expose rated energy and correction-factor tables.
- A project condition note can expose temperature, angular approach, and velocity conditions.
- A berth energy calculation can provide design energy.

Requirements:

- Handoff from berthing energy.
- Fender datasheet source for rated energy.
- Correction-factor source or table.
- Utilisation and margin evidence.
- Optional fender selection list if extended.

Harness opportunities:

- Add handoff gate from `berthing-energy-calc`.
- Add correction-factor product gate.
- Add datasheet extraction gate.
- Add utilisation/margin consistency gate.
- Add contradiction event if capacity margin and utilisation imply opposite pass/fail stories.

Natural products:

- `berthing-energy-calc -> fender-energy-check`.
- `fender-energy-check -> mooring-line-capacity` for berth system acceptance.
- `fender-energy-check -> construction-tolerance` where fender brackets and slots need fit-up checks.

Meta-harness handles:

- `projection`: fender datasheet, correction table, berth environmental note.
- `difference`: hide correction-factor labels or datasheet row headings.
- `product`: fender system capacity package.

## Task 3: Mooring Line Capacity

Current world:

- Computes design tension, capacity margin ratio, reserve capacity, utilisation ratio, and pass flag.
- Inputs are line tension, dynamic factor, consequence factor, and minimum breaking load.
- All parameters are visible.
- The pass flag is numeric: `1.0` when design tension does not exceed MBL.

Multimodal expansion:

- Best first modality: mooring analysis summary plus rope/line datasheet.
- A mooring force table can expose line tension.
- A line datasheet can expose minimum breaking load.
- A design basis can expose dynamic and consequence factors.

Requirements:

- Line tension source.
- MBL source.
- Dynamic/consequence factor source.
- Pass/fail and utilisation evidence.

Harness opportunities:

- Add source gate for line tension and MBL.
- Add factor product gate for design tension.
- Add pass-flag consistency gate.
- Add reserve-capacity and utilisation reciprocal check.
- Add berth-system handoff from marine berthing/fender package.

Natural products:

- `mooring-line-capacity` joins `berthing-energy-calc` and `fender-energy-check` in a marine berth package.
- `mooring-line-capacity -> structural bracket/foundation` if bollard or hook support checks are added.
- `mooring-line-capacity -> coastal/wave` where environmental loads define line tensions.

Meta-harness handles:

- `projection`: mooring analysis table, line datasheet, berth operation note.
- `difference`: remove line material/MBL labels.
- `product`: berth mooring capacity package.

## Task 4: Effective Wind Area

Current world:

- Computes panel area, supporting-member tributary area, effective wind area, and area averaging ratio.
- Inputs are panel width/height, support span, tributary width, and minimum effective area.
- All parameters are visible.
- The engine takes the maximum of panel area, member tributary area, and minimum effective area.

Multimodal expansion:

- Best first modality: facade elevation with panel grid and support spacing.
- A drawing can expose panel sizes, mullion/transom spans, and tributary widths.
- A wind standard table can expose minimum effective area.

Requirements:

- Facade panel geometry source.
- Supporting member span and tributary width source.
- Minimum effective area source.
- Governing-area evidence.
- Handoff to civil wind pressure or cladding coefficient selection.

Harness opportunities:

- Add drawing geometry gate.
- Add governing maximum gate.
- Add source-authority gate for minimum effective area.
- Add handoff gate to `design-wind-pressure`.
- Add event trigger if panel and member tributary areas are swapped.

Natural products:

- `effective-wind-area -> design-wind-pressure` for cladding/facade loads.
- `effective-wind-area -> bracket-load-calc` through tributary wind load.
- `effective-wind-area -> construction-tolerance/thermal-movement` in facade packages.

Meta-harness handles:

- `projection`: facade elevation, panel schedule, support grid, pressure coefficient table.
- `difference`: remove panel dimension labels or support spacing labels.
- `product`: facade wind action package.

## Task 5: Bracket Load Calculation

Current world:

- Computes service vertical load, factored vertical load, factored lateral load, and factored resultant load.
- Inputs are dead, live, wind loads and explicit factors.
- All parameters are visible.
- The engine uses vector resultant from factored vertical and lateral loads.

Multimodal expansion:

- Best first modality: bracket detail plus load schedule.
- A bracket drawing can expose supported component and load direction.
- A load schedule can expose dead, live, and wind effects.
- A factor table can expose the provided load factors.

Requirements:

- Load effect source.
- Load direction source.
- Factor source.
- Resultant vector evidence.
- Optional connection capacity handoff if future tasks exist.

Harness opportunities:

- Add source gate for load effects.
- Add vertical/lateral direction gate.
- Add factor application gate.
- Add resultant closure gate.
- Add handoff from civil/structural load combinations.

Natural products:

- `design-wind-pressure -> bracket-load-calc` for facade/equipment brackets.
- `effective-wind-area -> bracket-load-calc` through tributary wind.
- `bracket-load-calc -> construction-tolerance` for bracket slot design.

Meta-harness handles:

- `projection`: bracket detail, load schedule, factor table.
- `difference`: hide load direction or factor labels.
- `product`: bracket connection action package.

## Task 6: Pipe Support Dead Load

Current world:

- Computes steel pipe load, contents load, insulation load, operating line load, and hydrotest line load.
- Inputs are pipe outside diameter, wall thickness, steel/content/insulation/hydrotest densities, and insulation thickness.
- All parameters are visible.
- The engine computes annulus and circular areas after converting millimetres to metres.

Multimodal expansion:

- Best first modality: pipe schedule plus insulation and process-fluid table.
- A pipe schedule can expose OD, wall thickness, and service.
- A fluid table can expose operating and hydrotest densities.
- An insulation schedule can expose insulation thickness and density.

Requirements:

- Pipe geometry source.
- Material/fluid density source.
- Insulation source.
- Operating versus hydrotest state record.
- Support load handoff to structural support/bracket/foundation tasks.

Harness opportunities:

- Add annulus geometry gate.
- Add mm-to-m conversion gate.
- Add operating/hydrotest state gate.
- Add source-authority gate for densities.
- Add handoff gate to support or bracket design tasks.

Natural products:

- `mechanical pipe hydraulics -> pipe-support-dead-load` through pipe schedule handoff.
- `pipe-support-dead-load -> bracket-load-calc` for support reactions.
- `pipe-support-dead-load -> gravity-base-stability` for equipment/support foundation packages.

Meta-harness handles:

- `projection`: pipe schedule, insulation table, fluid property table, support layout.
- `difference`: remove density/source labels or hydrotest state labels.
- `product`: pipe support load package.

## Task 7: Gravity Base Stability

Current world:

- Computes eccentricity, middle-third limit, maximum bearing pressure, bearing utilisation, and middle-third flag.
- Inputs are vertical load, overturning moment, base width/length, and allowable bearing pressure.
- All parameters are visible.
- The engine uses middle-third elastic bearing formula even when eccentricity exceeds the middle-third limit; the flag identifies whether that assumption is satisfied.

Multimodal expansion:

- Best first modality: foundation block plan plus load reaction table.
- A plan can expose base width/length.
- A load table can expose vertical load and overturning moment.
- A geotechnical note can expose allowable bearing pressure.

Requirements:

- Foundation geometry source.
- Load reaction source.
- Allowable bearing source from ground/geotechnical tasks.
- Middle-third and bearing utilisation evidence.
- Optional downstream repair if outside middle-third should trigger another pressure model.

Harness opportunities:

- Add geometry source gate.
- Add load handoff gate from wind/turbine/equipment loads.
- Add middle-third compliance gate.
- Add bearing utilisation gate.
- Add discipline-interface gate to ground bearing tasks.

Natural products:

- `civil wind/solar -> gravity-base-stability` for turbine or equipment foundation.
- `ground bearing-capacity -> gravity-base-stability` through allowable bearing.
- `gravity-base-stability -> structural/load-combinations` for governing action packages.

Meta-harness handles:

- `projection`: foundation plan, load reaction table, geotechnical bearing note.
- `difference`: hide allowable-bearing provenance or load direction labels.
- `product`: equipment foundation stability package.

## Task 8: Load Combinations

Current world:

- Computes three explicit moment combinations, identifies governing moment, associated governing shear, and combination index.
- Inputs are dead/live/wind/seismic moments and shears plus explicit factors.
- All parameters are visible.
- The governing combination is selected by maximum moment, not by shear.

Multimodal expansion:

- Best first modality: structural action table plus combination-factor table.
- A load effects table can expose moments and shears for each action.
- A factor table or design basis can expose combination factors.
- A member diagram can expose sign convention if future variants allow signed effects.

Requirements:

- Load effects source.
- Factor source.
- Combination-by-combination evidence for moment and shear.
- Explicit rule that governing index follows moment.
- Optional comparison with civil SLS/ULS load-combination templates.

Harness opportunities:

- Add source gate for action effects.
- Add factor application gate.
- Add governing-by-moment gate.
- Add associated-shear handoff gate.
- Add event trigger if governing shear is selected independently from governing moment.

Natural products:

- `civil sls/uls-load-combinations <-> structural/load-combinations` as standards/method comparison.
- `load-combinations -> bracket-load/composite-section` through member actions.
- `load-combinations -> gravity-base-stability` through overturning moment and vertical load.

Meta-harness handles:

- `projection`: load effects table, factor table, member diagram.
- `difference`: hide factor labels or governing criterion.
- `product`: structural design action package.

## Task 9: Composite Section

Current world:

- Computes transformed area, neutral axis, transformed inertia, bottom section modulus, and top section modulus.
- Inputs define steel girder rectangles, concrete slab/haunch rectangles, and modular ratio.
- All parameters are visible.
- The engine transforms concrete by dividing area and inertia by modular ratio and uses the parallel-axis theorem.

Multimodal expansion:

- Best first modality: composite girder section drawing.
- A drawing can expose flange/web/slab/haunch dimensions and datum from bottom flange.
- A material note can expose modular ratio.
- A richer variant can require a generated section sketch as output.

Requirements:

- Section geometry source.
- Material/modular ratio source.
- Component ledger with area, centroid, and local inertia.
- Neutral axis and transformed inertia evidence.

Harness opportunities:

- Add component extraction gate.
- Add datum/centroid gate.
- Add transformed concrete gate.
- Add parallel-axis construction gate.
- Add artifact consistency gate if a section diagram is generated.

Natural products:

- `composite-section -> load-combinations` for bridge member stresses if future stress tasks exist.
- `composite-section -> construction-tolerance/thermal-movement` through bridge/facade geometry.
- `composite-section -> target-strength/scm` through concrete material assumptions.

Meta-harness handles:

- `projection`: section drawing, material note, component table.
- `difference`: remove dimension labels or modular ratio source.
- `product`: bridge composite section property package.

## Task 10: Lap Splice Length

Current world:

- Computes calculated lap length, rounded required lap, margin, and pass flag.
- Inputs are development length, splice class factor, bar location factor, coating factor, and provided lap length.
- All parameters are visible.
- Required lap is rounded up to the nearest 10 mm.

Multimodal expansion:

- Best first modality: reinforcement schedule plus detail note.
- A bar schedule can expose development length and provided lap.
- A detailing note can expose splice class, bar location, and coating factors.
- A drawing can expose whether bars are top-cast, epoxy-coated, or wall/slab bars.

Requirements:

- Rebar schedule source.
- Detailing factor source.
- Provided lap source.
- Rounding evidence.
- Pass/fail evidence.

Harness opportunities:

- Add factor-source gates.
- Add rounding gate.
- Add pass-flag consistency gate.
- Add drawing/evidence gate for provided lap.
- Add handoff to construction tolerance if splice congestion or slot tolerance tasks are composed.

Natural products:

- `lap-splice-length -> construction-tolerance` in constructability/detailing packages.
- `target-strength/scm-substitution -> lap-splice-length` only indirectly if material class affects development length in future variants.
- `load-combinations -> lap-splice-length` if member reinforcement demand tasks are added.

Meta-harness handles:

- `projection`: rebar schedule, detail drawing, factor table.
- `difference`: hide factor labels or provided lap annotation.
- `product`: reinforcement detailing compliance package.

## Task 11: Construction Tolerance

Current world:

- Computes total allowance, root-sum-square tolerance, required slot length, and included clearance.
- Inputs are fabrication, erection, survey, movement, clearance allowances, and component length.
- All parameters are visible.
- Clearance is included in total allowance but excluded from RSS tolerance.
- Required slot length adds twice the total allowance.

Multimodal expansion:

- Best first modality: slotted connection detail plus tolerance stack-up table.
- A connection detail can expose component length and slot direction.
- A tolerance table can expose fabrication, erection, survey, movement, and clearance allowances.
- A construction sequence note can justify movement allowance.

Requirements:

- Component geometry source.
- Tolerance component source.
- Explicit RSS exclusion of clearance.
- Slot length evidence using allowance on both ends.

Harness opportunities:

- Add tolerance-source gate.
- Add RSS construction gate.
- Add total-versus-RSS distinction gate.
- Add slot-length closure gate.
- Add product gate with thermal movement and bracket loads.

Natural products:

- `thermal-movement-calc -> construction-tolerance` through movement allowance.
- `bracket-load-calc -> construction-tolerance` for slotted bracket details.
- `fender/bracket support -> construction-tolerance` for marine support fit-up.

Meta-harness handles:

- `projection`: connection detail, tolerance table, construction sequence note.
- `difference`: remove clearance/RSS labels.
- `product`: constructability tolerance package.

## Task 12: Thermal Movement Calculation

Current world:

- Computes total thermal movement, symmetric expansion/contraction, and accommodation required.
- Inputs are member length, temperature range, coefficient of thermal expansion, and joint safety factor.
- Hard mode hides coefficient of thermal expansion.
- The engine converts microstrain per degree C to strain per degree C.
- Expansion and contraction are reported as half of total movement.

Multimodal expansion:

- Best first modality: component schedule plus material table and temperature design range.
- A facade/member schedule can expose length and material.
- A climate/design-basis note can expose temperature range.
- A material table can expose CTE for hard mode.

Requirements:

- Member length source.
- Temperature range source.
- Material/CTE source.
- Safety-factor source.
- Movement allowance handoff to tolerance/joint tasks.

Harness opportunities:

- Add material-source gate for hidden CTE.
- Add microstrain conversion gate.
- Add symmetric movement gate.
- Add accommodation factor gate.
- Add handoff gate to construction tolerance.

Natural products:

- `thermal-movement-calc -> construction-tolerance` as a movement allowance chain.
- `effective-wind-area/bracket-load -> thermal movement` in facade support packages.
- `composite-section -> thermal-movement` for bridge movement packages if future thermal stress tasks are added.

Meta-harness handles:

- `projection`: component schedule, material table, temperature design basis.
- `difference`: hide material CTE or length labels.
- `product`: movement joint and tolerance package.

## Task 13: Carbon Equivalent Calculation

Current world:

- Computes IIW carbon equivalent, caution/high-risk margins, numeric weldability risk class, and preheat indication.
- Inputs are steel chemistry percentages and thresholds.
- All parameters are visible.
- Risk class is `0`, `1`, or `2` based on threshold comparisons.

Multimodal expansion:

- Best first modality: mill certificate plus welding specification thresholds.
- A mill certificate can expose elemental chemistry.
- A welding procedure/specification can expose caution and high-risk thresholds.
- A repair-work context can make threshold selection more consequential.

Requirements:

- Chemistry source with element names and units.
- Threshold source.
- Formula evidence.
- Risk class and preheat consistency record.

Harness opportunities:

- Add mill-certificate extraction gate.
- Add threshold comparison gate.
- Add risk-class branch gate.
- Add preheat flag consistency gate.
- Add product gate with welding/detailing tasks.

Natural products:

- `carbon-equivalent-calc -> construction/welding procedure` future package.
- `carbon-equivalent-calc -> bracket/pipe support` for steelwork repair or fabrication checks.
- `carbon-equivalent-calc -> material provenance` multimodal certificate task.

Meta-harness handles:

- `projection`: mill certificate, welding specification, repair context.
- `difference`: hide threshold labels or chemical element labels.
- `product`: steel weldability compliance package.

## Task 14: SCM Substitution

Current world:

- Computes cement content, SCM content, cement reduction, and water-binder ratio.
- Inputs are total binder, SCM replacement percentage, and water content.
- All parameters are visible.
- Cement reduction equals SCM content in the current engine.

Multimodal expansion:

- Best first modality: concrete mix design sheet.
- A mix sheet can expose total binder, water, and replacement percentage.
- A sustainability note can expose replacement intent or cement reduction target.
- A future variant can combine with embodied carbon factors if such tasks appear.

Requirements:

- Mix design source.
- Replacement percentage source.
- Water content source.
- Unit and percentage conversion evidence.
- Optional link to target strength if material performance is composed.

Harness opportunities:

- Add mix-sheet extraction gate.
- Add percent conversion gate.
- Add water-binder closure gate.
- Add product gate with target mean strength.
- Add contradiction event if cement plus SCM does not equal total binder.

Natural products:

- `scm-substitution -> target-strength-calc` in concrete mix design packages.
- `scm-substitution -> carbon/material compliance` future sustainability package.
- `scm-substitution -> composite-section` through slab concrete material context.

Meta-harness handles:

- `projection`: mix design sheet, sustainability note, binder table.
- `difference`: remove replacement percentage labels.
- `product`: concrete mix composition package.

## Task 15: Target Strength Calculation

Current world:

- Computes statistical margin, governing margin, target mean strength, and margin above specified strength.
- Inputs are specified strength, standard deviation, k-factor, and minimum margin.
- All parameters are visible.
- The governing margin is the maximum of `k * s` and minimum margin.

Multimodal expansion:

- Best first modality: concrete production record plus specification.
- A specification can expose specified strength and minimum margin.
- A production record can expose standard deviation.
- A reliability/design basis can expose k-factor.

Requirements:

- Specified strength source.
- Production standard deviation source.
- Reliability factor and minimum-margin source.
- Governing margin evidence.
- Handoff to mix design or quality-control compliance.

Harness opportunities:

- Add production-record extraction gate.
- Add governing max gate.
- Add target strength closure gate.
- Add product gate with SCM substitution.
- Add event trigger if a model averages margins instead of taking the maximum.

Natural products:

- `target-strength-calc -> scm-substitution` as strength and binder package.
- `target-strength-calc -> composite-section` through concrete material properties.
- `target-strength-calc -> construction quality` future package.

Meta-harness handles:

- `projection`: concrete specification, production records, reliability note.
- `difference`: hide k-factor or minimum-margin labels.
- `product`: concrete mix design and QA package.

## Cross-Discipline Threads Opened

Structural tasks are mostly downstream consumers and compliance wrappers:

- marine berth package: berthing energy, fender energy, and mooring line capacity;
- facade and bracket package: civil wind pressure, effective wind area, bracket loads, thermal movement, and construction tolerance;
- pipe/support/foundation package: mechanical pipe schedule, structural pipe-support dead load, bracket/support actions, gravity-base stability, and ground bearing capacity;
- bridge member package: composite section, load combinations, target concrete strength, and reinforcement detailing;
- material compliance package: carbon equivalent, SCM substitution, and target concrete strength from certificates/specifications.

## Meta-Harness Implications

The structural meta-harness pattern is less about hidden parameters and more about evidence joins:

- extract geometry and properties from schedules/drawings/certificates;
- preserve explicit factors instead of inventing extra code rules;
- carry handoff values from upstream tasks into structural checks;
- verify that pass/fail, utilisation, governing case, and margin outputs agree with intermediate values.

The best event candidates are:

- source-extraction mismatch from drawings or schedules;
- upstream handoff field omitted or rounded inconsistently;
- governing case selected by the wrong criterion;
- pass/fail flag contradicts utilisation or margin;
- explicit-factor task polluted by an invented code factor;
- material certificate values copied into the wrong formula term.
