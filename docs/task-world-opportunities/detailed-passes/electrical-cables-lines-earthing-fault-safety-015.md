# ABOUTME: Detailed task-world review for electrical cable, conductor, line, earthing, arc-flash, and overhead loading tasks.
# ABOUTME: Records multimodal, composition, and meta-harness opportunities for the second electrical discipline slice.

# Electrical Cables Lines Earthing And Fault Safety Pass 015

Review date: 2026-06-28

Reviewed task cards:

- `electrical/electrical-parameters/ac-resistance-temperature`
- `electrical/cable-sizing/cable-ampacity`
- `electrical/thermal-rating/static-thermal-rating`
- `electrical/busbar-design/busbar-forces`
- `electrical/grounding-design/grid-resistance`
- `electrical/electrical-parameters/line-capacitance`
- `electrical/electrical-parameters/line-inductance`
- `electrical/arc-flash/incident-energy`
- `electrical/structural-loading/wind-load-conductor`
- `electrical/structural-loading/ice-load-calculation`
- `electrical/catenary-design/single-span-sag-tension`

Source files read for this pass:

- `src/aec_bench/templates/builtin/electrical/ac_resistance_temperature/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/electrical/cable_ampacity/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/electrical/static_thermal_rating/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/electrical/busbar_forces/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/electrical/grid_resistance/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/electrical/line_capacitance/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/electrical/line_inductance/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/electrical/incident_energy/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/electrical/wind_load_conductor/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/electrical/ice_load_calculation/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/electrical/single_span_sag_tension/{params.toml,instruction.md,engine.py}`

## Slice Read

This electrical slice is source-heavy and physically grounded. The task worlds naturally want cable schedules, installation notes, conductor datasheets, weather tables, soil resistivity reports, one-line diagrams, switchboard arrangements, busbar support details, arc-flash study tables, overhead line geometry, catenary/contact-wire schedules, and structural loading assumptions.

The strongest composition axis is a physical network safety package:

- fault-current output feeds busbar force and incident energy;
- cable/conductor resistance and ampacity feed voltage drop and thermal rating;
- soil resistivity and grid geometry feed grounding and GPR;
- line inductance and capacitance share overhead line geometry and feed voltage regulation;
- wind and ice loading plus sag-tension bridge electrical, civil, rail, and structural disciplines.

Several hidden parameters here are good meta-harness handles: conductor material, installation method, insulation type, emissivity/absorptivity, support condition, soil resistivity, frequency, bundle count, enclosure type/gap, terrain category, ice density, and wire weight.

## Task 1: AC Resistance Temperature

Current world:

- Computes DC resistance at operating temperature, skin effect factor, and AC resistance.
- Inputs are DC resistance at 20 C, conductor material, operating temperature, and frequency.
- Hard mode hides `conductor_material`.
- Material changes the temperature coefficient used for resistance correction.

Multimodal expansion:

- Best first modality: conductor datasheet plus operating-temperature schedule.
- A line-parameter variant can source frequency from network context and material from conductor code.
- A hard variant can feed AC resistance into line voltage regulation or thermal rating.

Requirements:

- Conductor resistance source.
- Conductor material source.
- Operating temperature source.
- Frequency source.
- Handoff of AC resistance.

Harness opportunities:

- Add conductor-code/material inference gate.
- Add temperature correction gate.
- Add skin-effect construction gate.
- Add resistance handoff gate.

Natural products:

- `ac-resistance-temperature -> static-thermal-rating`.
- `ac-resistance-temperature -> voltage-regulation`.
- `ac-resistance-temperature -> line-parameter package`.

Meta-harness handles:

- `projection`: conductor datasheet, line schedule, operating-temperature table.
- `difference`: hide material but provide conductor code/resistance clues.
- `product`: conductor AC resistance record.

## Task 2: Cable Ampacity

Current world:

- Computes base ampacity, temperature derating, grouping derating, and derated ampacity.
- Inputs are conductor size, insulation type, installation method, ambient temperature, maximum conductor temperature, and grouping count.
- Hard mode hides `insulation_type` and `installation_method`.
- The engine uses embedded base ampacity and grouping tables.

Multimodal expansion:

- Best first modality: cable schedule plus installation detail.
- A tray/conduit/buried variant can require inferring installation method from drawings.
- A hard variant can combine derated ampacity, load current, and voltage-drop compliance.

Requirements:

- Cable size source.
- Insulation and installation source.
- Ambient/max conductor temperature source.
- Grouping source.
- Table row evidence.

Harness opportunities:

- Add cable schedule extraction gate.
- Add installation-method inference gate.
- Add base-table source gate.
- Add derating-product consistency gate.

Natural products:

- `cable-ampacity -> voltage-drop`.
- `cable-ampacity -> three-phase-fault-current` where cable impedance/length are in the same schedule.
- `cable-ampacity -> mechanical/electrical motor load package`.

Meta-harness handles:

- `projection`: cable schedule, installation drawing, derating table, ambient condition note.
- `difference`: show several cable routes with different installation methods.
- `product`: derated cable ampacity record.

## Task 3: Static Thermal Rating

Current world:

- Computes convective cooling, radiative cooling, solar gain, and ampacity for a bare overhead conductor.
- Inputs include conductor diameter/resistance, maximum conductor temperature, ambient temperature, wind speed/angle, solar radiation, emissivity, and absorptivity.
- Hard mode hides `emissivity` and `absorptivity`.
- The engine returns zero ampacity if net cooling is less than or equal to solar gain.

Multimodal expansion:

- Best first modality: overhead conductor datasheet plus weather/design condition table.
- A seasonal rating variant can compare rating under multiple ambient/wind/solar cases.
- A hard variant can infer emissivity/absorptivity from conductor age and surface condition.

Requirements:

- Conductor geometry/resistance source.
- Weather and solar source.
- Surface condition source.
- Heat balance evidence.
- Branch evidence for zero-rating cases.

Harness opportunities:

- Add weather-case selection gate.
- Add emissivity/absorptivity inference gate.
- Add heat-balance component gate.
- Add zero-net-cooling event gate.

Natural products:

- `static-thermal-rating -> voltage-regulation`.
- `ac-resistance-temperature -> static-thermal-rating`.
- `static-thermal-rating -> wind-load-conductor/ice-load-calculation` through shared conductor/weather context.

Meta-harness handles:

- `projection`: conductor datasheet, weather table, surface-condition note, rating report.
- `difference`: include old/new conductor surface conditions.
- `product`: overhead conductor thermal rating record.

## Task 4: Busbar Forces

Current world:

- Computes electromagnetic force per metre, peak force, and bending stress.
- Inputs are peak short-circuit current, phase spacing, span length, busbar width/thickness, support condition, and busbar material.
- Hard mode hides `support_condition` and `busbar_material`.
- Support condition affects stress through bending coefficient; material is currently validation-only because yield strength is defined but not used in any output.

Multimodal expansion:

- Best first modality: switchboard/busbar layout plus fault-current study.
- A support-detail variant can infer simply supported versus fixed support from drawings.
- A hard variant can feed peak current from fault-current calculation and compare stress with material yield if output is extended.

Requirements:

- Peak short-circuit current source.
- Busbar geometry and spacing source.
- Support condition source.
- Material source if utilisation is added.
- Stress evidence.

Harness opportunities:

- Add fault-current handoff gate.
- Add busbar geometry extraction gate.
- Add support-condition inference gate.
- Add material-utilisation extension gate.

Natural products:

- `three-phase-fault-current -> busbar-forces`.
- `busbar-forces -> structural support/bracket tasks` if switchboard support is introduced.
- `busbar-forces -> incident-energy` as part of switchboard safety package.

Meta-harness handles:

- `projection`: switchboard layout, busbar section, support detail, fault study.
- `difference`: hide support condition or provide material labels with no yield output.
- `product`: busbar short-circuit force record.

## Task 5: Grid Resistance

Current world:

- Computes grid area, equivalent radius, grid resistance, and ground potential rise.
- Inputs are soil resistivity, grid length/width, total conductor length, burial depth, and grid current.
- Hard mode hides `soil_resistivity_ohm_m`.
- The task uses a simplified IEEE 80/Schwarz-style expression.

Multimodal expansion:

- Best first modality: grounding grid layout plus soil resistivity report.
- A substation variant can require extracting grid dimensions and conductor length from drawings.
- A hard variant can infer soil resistivity from geotechnical/site description or Wenner test table.

Requirements:

- Soil resistivity source.
- Grid geometry and conductor length source.
- Burial depth source.
- Grid current source.
- GPR evidence.

Harness opportunities:

- Add soil-resistivity source gate.
- Add grid geometry extraction gate.
- Add GPR handoff gate.
- Add grounding compliance extension gate.

Natural products:

- `three-phase-fault-current -> grid-resistance` through grid current.
- `grid-resistance -> incident-energy/earthing safety` if touch/step voltage tasks are added.
- `ground geotechnical soil records -> grid-resistance` as civil-electrical interface.

Meta-harness handles:

- `projection`: earthing layout, soil report, grid schedule, fault-current study.
- `difference`: include multiple soil layers or test locations.
- `product`: grounding grid resistance and GPR record.

## Task 6: Line Capacitance

Current world:

- Computes geometric mean distance, capacitance per km, charging Mvar per 100 km, and surge impedance.
- Inputs are conductor radius, phase spacings, nominal voltage, frequency, and inductance.
- Hard mode hides `frequency_hz`.
- Surge impedance uses the supplied inductance and computed capacitance.

Multimodal expansion:

- Best first modality: overhead line geometry drawing plus system-frequency context.
- A line-parameter package can pair this with line inductance from the same geometry.
- A hard variant can infer frequency from region/system context.

Requirements:

- Conductor radius source.
- Phase spacing source.
- Voltage and frequency source.
- Inductance handoff or source.
- Charging Mvar evidence.

Harness opportunities:

- Add geometry extraction gate.
- Add frequency inference gate.
- Add line-parameter handoff gate.
- Add surge-impedance consistency gate.

Natural products:

- `line-inductance -> line-capacitance`.
- `line-capacitance -> voltage-regulation`.
- `line-capacitance -> transmission-line parameter package`.

Meta-harness handles:

- `projection`: line arrangement drawing, conductor datasheet, system data sheet.
- `difference`: hide frequency and include regional grid context.
- `product`: overhead line capacitance record.

## Task 7: Line Inductance

Current world:

- Computes geometric mean distance, equivalent GMR, and inductance per km.
- Inputs are conductor GMR, phase spacings, bundle count, and bundle spacing.
- Hard mode hides `bundle_count`.
- Bundle count changes equivalent GMR formula.

Multimodal expansion:

- Best first modality: tower/cross-arm arrangement plus conductor/bundle datasheet.
- A hard variant can infer bundle count from drawing symbols or line class.
- A composition variant can feed inductance into line capacitance and voltage regulation.

Requirements:

- Conductor GMR source.
- Phase spacing source.
- Bundle count and spacing source.
- Line geometry evidence.

Harness opportunities:

- Add bundle-count inference gate.
- Add GMD construction gate.
- Add equivalent-GMR branch gate.
- Add inductance handoff gate.

Natural products:

- `line-inductance -> line-capacitance`.
- `line-inductance -> voltage-regulation`.
- `line-inductance -> static-thermal-rating` through shared conductor package.

Meta-harness handles:

- `projection`: tower geometry, bundle detail, conductor datasheet.
- `difference`: include single and bundled conductor drawings.
- `product`: overhead line inductance record.

## Task 8: Incident Energy

Current world:

- Computes arcing current, incident energy, arc flash boundary, and PPE category.
- Inputs are voltage, bolted fault current, clearing time, working distance, electrode gap, and enclosure type.
- Hard mode hides `electrode_gap_mm` and `enclosure_type`.
- The engine assumes grounded systems and clamps PPE category above 40 cal/cm2 to category 4.

Multimodal expansion:

- Best first modality: arc-flash study table plus switchboard/equipment schedule.
- A fault-current variant can receive bolted fault current from `three-phase-fault-current`.
- A hard variant can infer enclosure type and electrode gap from equipment class.

Requirements:

- Voltage, fault current, and clearing time source.
- Working distance source.
- Enclosure type and electrode gap source.
- PPE category evidence.

Harness opportunities:

- Add equipment-class inference gate.
- Add fault-current handoff gate.
- Add arcing-current branch gate for LV versus HV.
- Add PPE/boundary consistency gate.

Natural products:

- `three-phase-fault-current -> incident-energy`.
- `incident-energy -> busbar-forces` through shared fault/switchboard context.
- `incident-energy -> safety compliance artifact`.

Meta-harness handles:

- `projection`: arc-flash label, switchboard schedule, protection study, equipment class table.
- `difference`: include bolted and arcing current fields together.
- `product`: arc-flash hazard record.

## Task 9: Wind Load Conductor

Current world:

- Computes height-adjusted wind pressure, wind load per unit length, and transverse span load.
- Inputs are wind pressure, conductor diameter, span length, drag coefficient, terrain category, and height above ground.
- Hard mode hides `terrain_category`.
- Terrain category maps to an exponent for height adjustment.

Multimodal expansion:

- Best first modality: overhead line profile plus wind/terrain design basis.
- A route variant can infer terrain category from corridor mapping.
- A hard variant can feed conductor wind load into pole/tower structural checks.

Requirements:

- Wind pressure source.
- Conductor geometry/source.
- Span length and height source.
- Terrain category source.
- Drag coefficient source.

Harness opportunities:

- Add terrain inference gate.
- Add height adjustment gate.
- Add span load handoff gate.
- Add structural interface gate.

Natural products:

- `wind-load-conductor -> single-span-sag-tension`.
- `wind-load-conductor -> structural loading/foundation tasks`.
- `wind-load-conductor <-> ice-load-calculation` for weather load combinations.

Meta-harness handles:

- `projection`: line profile, terrain map, wind design table, conductor datasheet.
- `difference`: include terrain category and exposure category distractors.
- `product`: conductor wind load record.

## Task 10: Ice Load Calculation

Current world:

- Computes iced diameter, ice weight, vertical load, wind-on-ice load, combined load, and span combined load.
- Inputs are conductor diameter, ice thickness/density, wind-on-ice pressure, and span length.
- Hard mode hides `ice_density_kg_m3`.
- It combines vertical ice weight and transverse wind load by hypotenuse.

Multimodal expansion:

- Best first modality: weather loading table plus conductor schedule.
- A route-climate variant can infer ice density/thickness from region or load case.
- A hard variant can combine ice and wind loads with sag-tension and structural support checks.

Requirements:

- Conductor diameter source.
- Ice thickness/density source.
- Wind-on-ice pressure source.
- Span length source.
- Combined-load evidence.

Harness opportunities:

- Add climate/load-case source gate.
- Add annular ice area gate.
- Add vector combination gate.
- Add span-load handoff gate.

Natural products:

- `ice-load-calculation -> single-span-sag-tension`.
- `ice-load-calculation -> structural pole/tower/foundation tasks`.
- `ice-load-calculation <-> wind-load-conductor`.

Meta-harness handles:

- `projection`: weather load table, route climate note, conductor datasheet, span schedule.
- `difference`: hide ice density while giving wet/dry/rime ice context.
- `product`: iced conductor load record.

## Task 11: Single Span Sag Tension

Current world:

- Computes parabolic sag, exact catenary sag, wire length, and catenary constant.
- Inputs are span length, wire weight, horizontal tension, and wire diameter.
- Hard mode hides `wire_weight_per_m_n`.
- Wire diameter is validated but not used in the current sag/tension outputs.

Multimodal expansion:

- Best first modality: OLE/catenary span schedule plus contact-wire datasheet.
- A rail corridor variant can infer wire weight from material/diameter/type.
- A hard variant can combine wind/ice load with sag/tension and clearance checks.

Requirements:

- Span length source.
- Wire weight source.
- Horizontal tension source.
- Wire type/diameter source.
- Clearance criterion if extended.

Harness opportunities:

- Add wire-weight inference gate.
- Add parabolic vs catenary comparison gate.
- Add weather-load handoff gate.
- Add clearance/compliance extension gate.

Natural products:

- `single-span-sag-tension -> electrical signal/rail clearance tasks`.
- `wind-load-conductor/ice-load-calculation -> single-span-sag-tension`.
- `civil rail geometry -> single-span-sag-tension` through corridor profile.

Meta-harness handles:

- `projection`: OLE span schedule, wire datasheet, tensioning table, route profile.
- `difference`: hide wire weight but include material and diameter.
- `product`: overhead contact wire sag-tension record.

## Cross-Slice Product Worlds

### Switchboard Fault Safety Package

Candidate chain:

1. Read single-line, transformer/cable data, and switchboard layout.
2. Compute three-phase fault current upstream.
3. Use peak current for busbar force and bolted fault current for incident energy.
4. Emit busbar stress and arc-flash safety evidence.

Why it is interesting:

- It is a high-value composition with shared fault location and equipment identity.
- It separates mechanical withstand from human safety hazard.
- It exposes source-role traps: bolted current, arcing current, peak current, and clearing time are different values.

### Cable And Feeder Physical Rating Package

Candidate chain:

1. Read cable schedule and installation details.
2. Compute derated ampacity.
3. Compute AC resistance at operating temperature where relevant.
4. Feed voltage drop, thermal rating, or fault current tasks.

Why it is interesting:

- It joins cable tables, installation drawings, ambient conditions, and network calculations.
- It has strong hidden-parameter inference around material, insulation, and installation method.
- It supports repair operations: change route, cable size, grouping, or insulation.

### Overhead Line Parameter And Weather Package

Candidate chain:

1. Read conductor/tower geometry and conductor datasheet.
2. Compute line inductance and capacitance.
3. Compute thermal rating under weather case.
4. Compute wind and ice loads for structural interface.

Why it is interesting:

- It creates one shared multimodal line corridor world.
- It links electrical parameters, thermal performance, and structural loading.
- It can mutate weather, terrain, bundle count, and conductor surface condition.

### OLE Sag And Weather Loading Package

Candidate chain:

1. Read catenary span and wire schedule.
2. Infer wire weight and compute sag/tension.
3. Add wind/ice loading for adverse weather cases.
4. Handoff to rail clearance or support design tasks.

Why it is interesting:

- It is an electrical-rail-civil interface.
- It is highly drawing/schedule driven.
- It can connect to rail vertical geometry and signalling sighting worlds.

## Repair And Extension Notes

- `busbar-forces` hides `busbar_material`, but material yield is currently not used in outputs. Add stress utilisation or material margin before using material inference as a real hard-mode requirement.
- `single-span-sag-tension` validates `wire_diameter_mm` but does not use it in the current outputs. It can still support wire-weight inference, but the active formula only uses span, weight, and tension.
- `static-thermal-rating` returns zero ampacity when solar gain exceeds cooling. Future variants should expose this as a heat-balance branch event.
- `incident-energy` defines typical electrode gaps by enclosure type, but the engine uses the supplied/default gap directly. Source-world variants should make gap provenance explicit rather than implying enclosure alone controls it.
