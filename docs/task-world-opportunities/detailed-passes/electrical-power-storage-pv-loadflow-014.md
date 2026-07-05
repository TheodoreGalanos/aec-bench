# ABOUTME: Detailed task-world review for electrical power supply, storage, PV, voltage, PFC, and fault-current tasks.
# ABOUTME: Records multimodal, composition, and meta-harness opportunities for the first electrical discipline slice.

# Electrical Power Storage PV And Loadflow Pass 014

Review date: 2026-06-28

Reviewed task cards:

- `electrical/power-supply/power-load-calculation`
- `electrical/power-supply/battery-sizing`
- `electrical/bess-design/bess-sizing-basic`
- `electrical/bess-design/bess-sizing`
- `electrical/solar-pv-design/dc-ac-ratio`
- `electrical/solar-pv-design/string-sizing`
- `electrical/solar-pv-design/voltage-drop-dc`
- `electrical/load-flow/pfc-sizing`
- `electrical/load-flow/radial-feeder-voltage-drop`
- `electrical/cable-sizing/voltage-drop`
- `electrical/electrical-parameters/voltage-regulation`
- `electrical/short-circuit/three-phase-fault-current`

Source files read for this pass:

- `src/aec_bench/templates/builtin/electrical/power_load_calculation/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/electrical/battery_sizing/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/electrical/bess_sizing_basic/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/electrical/bess_sizing/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/electrical/dc_ac_ratio/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/electrical/string_sizing/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/electrical/voltage_drop_dc/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/electrical/pfc_sizing/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/electrical/radial_feeder_voltage_drop/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/electrical/voltage_drop/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/electrical/voltage_regulation/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/electrical/three_phase_fault_current/{params.toml,instruction.md,engine.py}`

## Slice Read

This first electrical slice has much denser hidden-parameter structure than the mechanical slices. Hard modes hide future expansion, temperature derating, BESS DoD and efficiency, end-of-life retention, solar peak-sun-hours, site temperatures, conductor resistivity/material, reactive load, initial power factor, and IEC voltage factor. That makes it an immediate candidate for multimodal source packs and meta-harness inference operations.

The best product-world axis is a low-voltage or microgrid power package:

- equipment connected load feeds backup battery, UPS apparent power, and supply kVA;
- PV array and string sizing feed DC cable voltage drop and BESS sizing;
- PFC, feeder voltage drop, and voltage regulation share real/reactive power and impedance data;
- fault-current calculation provides protection and arc-flash inputs for later electrical tasks;
- mechanical pump, ventilation, gas, process, and life-safety loads can all hand off connected and critical load.

The practical meta-harness opportunity is source-role discipline. The same source pack may contain W, VA, kVA, kW, kVAr, kWh, MWh, Ah, AC voltage, DC voltage, nominal MPPT voltage, minimum MPPT voltage, source fault level, transformer impedance, and cable impedance. Composed tasks need explicit fields for each role.

## Task 1: Power Load Calculation

Current world:

- Computes total connected load, maximum demand, future allowance, and recommended supply size in kVA.
- Inputs are equipment power, quantity, diversity factor, future expansion percentage, and supply power factor.
- Hard mode hides `future_expansion_pct` in expansion context.
- The template is signalling-flavoured, but the structure is generally useful for equipment-room supplies.

Multimodal expansion:

- Best first modality: equipment schedule or signalling cabinet load list.
- A room/cabinet variant can require selecting only active equipment in the target cabinet.
- A hard variant can source future expansion from project basis notes or spare-way policy.

Requirements:

- Equipment power and quantity source.
- Diversity factor source.
- Future expansion source.
- Supply power factor source.
- kVA handoff to UPS, feeder, and battery tasks.

Harness opportunities:

- Add equipment-schedule extraction gate.
- Add load-role gate for connected load, maximum demand, and future allowance.
- Add hidden expansion source-authority gate.
- Add supply kVA consistency gate.

Natural products:

- `power-load-calculation -> battery-sizing`.
- `power-load-calculation -> radial-feeder-voltage-drop`.
- `mechanical pump-power-efficiency -> power-load-calculation` for connected mechanical loads.

Meta-harness handles:

- `projection`: load list, equipment-room schedule, design basis, spare-capacity note.
- `difference`: include future-only and installed equipment rows.
- `product`: equipment supply sizing record.

## Task 2: Battery Sizing

Current world:

- Computes required energy, required battery capacity, UPS rating, and battery block count.
- Inputs are critical load, autonomy, voltage, depth of discharge, temperature derating, inverter efficiency, load power factor, and block voltage.
- Hard mode hides `temperature_derating_factor`.
- The block count is ceiling of system voltage divided by block voltage.

Multimodal expansion:

- Best first modality: UPS/battery schedule plus autonomy requirement.
- A site-condition variant can source temperature derating from ambient enclosure conditions.
- A hard variant can receive critical load from `power-load-calculation` and output both Ah and VA requirements.

Requirements:

- Critical load source or handoff.
- Autonomy source.
- Battery voltage and block voltage source.
- DoD, derating, efficiency, and power factor sources.
- Unit separation for Wh/kWh, Ah, VA.

Harness opportunities:

- Add critical-load handoff gate.
- Add derating source gate.
- Add usable-fraction construction gate.
- Add block-count rounding gate.

Natural products:

- `power-load-calculation -> battery-sizing`.
- `nac-load-calculation -> battery-sizing` for fire alarm backup.
- `battery-sizing -> voltage-drop/feeder tasks` if UPS output feeders are included.

Meta-harness handles:

- `projection`: UPS schedule, battery datasheet, autonomy requirement, ambient temperature table.
- `difference`: include nominal and usable capacity in the same source.
- `product`: backup power sizing record.

## Task 3: BESS Sizing Basic

Current world:

- Computes nominal power rating, usable energy, nominal energy capacity, and beginning-of-life capacity.
- Inputs are discharge power, discharge duration, usable SOC range, round-trip efficiency, and end-of-life capacity retention.
- Hard mode hides `end_of_life_capacity_retention_pct`.
- The output semantics differ from `bess-sizing`: this template explicitly uses EOL retention as a separate capacity uplift.

Multimodal expansion:

- Best first modality: storage duty table plus battery lifecycle assumption sheet.
- A grid-firming variant can source discharge duration from service requirement.
- A hard variant can infer end-of-life retention from chemistry, warranty, or procurement basis.

Requirements:

- Discharge duty source.
- Usable SOC range source.
- Round-trip efficiency source.
- EOL retention source.
- Capacity semantic labels: usable, nominal, BOL.

Harness opportunities:

- Add storage-duty source gate.
- Add EOL-retention inference gate.
- Add capacity-role consistency gate.
- Add comparison gate with `bess-sizing`.

Natural products:

- `dc-ac-ratio/PV yield -> bess-sizing-basic` for renewable firming.
- `power-load-calculation -> bess-sizing-basic` for backup microgrid service.
- `bess-sizing-basic <-> bess-sizing` as a method/semantic comparison.

Meta-harness handles:

- `projection`: BESS duty table, battery warranty, SOC/efficiency design basis.
- `difference`: hide EOL retention and include multiple chemistry assumptions.
- `product`: basic BESS capacity record.

## Task 4: BESS Sizing

Current world:

- Computes nominal power, required energy, BOL capacity, and usable energy.
- Inputs are power requirement, discharge duration, DoD, round-trip efficiency, and degradation allowance.
- Hard mode hides `depth_of_discharge_pct` and `round_trip_efficiency_pct`.
- BOL capacity is required energy divided by DoD, efficiency, and non-degraded capacity fraction.

Multimodal expansion:

- Best first modality: battery datasheet plus project service requirement.
- A chemistry/context variant can infer DoD and efficiency from battery chemistry and application.
- A hard variant can combine PV production, load, and reserve duration to size BESS.

Requirements:

- Power and duration source.
- DoD and efficiency source or chemistry inference.
- Degradation allowance source.
- Capacity role labels.

Harness opportunities:

- Add chemistry-to-DoD/efficiency source gate.
- Add degradation allowance gate.
- Add BOL/usable capacity consistency gate.
- Add duplicate-template semantic guard with `bess-sizing-basic`.

Natural products:

- `power-load-calculation -> bess-sizing`.
- `dc-ac-ratio -> bess-sizing` for renewable firming.
- `bess-sizing -> voltage-regulation/radial feeder` for grid interconnection context.

Meta-harness handles:

- `projection`: battery datasheet, service requirement, degradation/warranty note, load profile.
- `difference`: include usable capacity and installed capacity without labels.
- `product`: BESS service sizing record.

## Task 5: DC/AC Ratio

Current world:

- Computes inverter loading ratio, estimated clipping loss, annual energy yield, and specific yield.
- Inputs are DC array capacity, inverter AC capacity, annual peak sun hours, and system losses.
- Hard mode hides `annual_psh` in site/location context.
- The engine uses a simple quadratic clipping estimate and fixed inverter efficiency.

Multimodal expansion:

- Best first modality: PV array/inverter schedule plus solar resource table.
- A site variant can source peak sun hours from location, tilt, or solar yield table.
- A hard variant can combine PV layout, inverter schedule, and loss assumptions.

Requirements:

- DC array and inverter capacity source.
- Annual peak sun hours source.
- Loss assumption source.
- Clipping/yield evidence.

Harness opportunities:

- Add location-to-PSH inference gate.
- Add DC/AC capacity role gate.
- Add clipping branch gate.
- Add annual yield handoff gate to BESS sizing.

Natural products:

- `dc-ac-ratio -> bess-sizing`.
- `dc-ac-ratio -> voltage-drop-dc` through string/array current context.
- `civil solar-array-wind-load -> dc-ac-ratio` as PV package context.

Meta-harness handles:

- `projection`: PV layout, inverter schedule, solar resource table, loss assumption sheet.
- `difference`: include DC kWp and AC kW values in nearby rows.
- `product`: PV inverter loading and yield record.

## Task 6: String Sizing

Current world:

- Computes cold-corrected Voc, hot-corrected Vmp, maximum modules per string, and minimum modules per string.
- Inputs are module voltages, temperature coefficients, site minimum/maximum temperatures, and inverter voltage limits.
- Hard mode hides site minimum and maximum temperatures.
- The engine clamps MPPT cross-parameter relationships internally rather than rejecting independently sampled values.

Multimodal expansion:

- Best first modality: PV module datasheet plus inverter datasheet and site temperature record.
- A layout variant can require selecting the module/inverter pairing from a string schedule.
- A hard variant can infer site temperatures from location or project design criteria.

Requirements:

- Module Voc/Vmp and coefficients source.
- Site temperature source.
- Inverter voltage limit source.
- Rounding rule for max/min modules.
- Evidence when max modules is less than min modules if infeasible variants are introduced.

Harness opportunities:

- Add module/inverter datasheet extraction gates.
- Add site-temperature inference gate.
- Add voltage-temperature correction gates.
- Add feasibility gate for string window.

Natural products:

- `string-sizing -> voltage-drop-dc`.
- `string-sizing -> dc-ac-ratio` through array size and inverter pairing.
- `string-sizing -> solar PV wind/layout tasks` if physical rows are introduced.

Meta-harness handles:

- `projection`: module datasheet, inverter datasheet, site climate table, string schedule.
- `difference`: hide temperature records or include datasheets for multiple module types.
- `product`: PV string voltage window record.

## Task 7: Voltage Drop DC

Current world:

- Computes DC string voltage drop, voltage drop percentage, annual energy loss, and margin to maximum drop.
- Inputs are string current, DC cable length, cable cross-section, resistivity, string voltage, operating hours, and maximum voltage drop.
- Hard mode hides `cable_resistivity_ohm_mm2_m`.
- The resistance is loop resistance over positive and negative conductors.

Multimodal expansion:

- Best first modality: PV cable schedule plus cable datasheet/material table.
- A layout variant can derive cable length from array-to-inverter route.
- A hard variant can infer conductor resistivity from material and operating temperature.

Requirements:

- String current/source.
- Cable route length and size source.
- Resistivity/material source.
- String voltage source.
- Maximum drop criterion.

Harness opportunities:

- Add route-length extraction gate.
- Add conductor-resistivity source gate.
- Add loop-resistance construction gate.
- Add voltage-drop/margin consistency gate.

Natural products:

- `string-sizing -> voltage-drop-dc`.
- `dc-ac-ratio -> voltage-drop-dc` through PV array operating context.
- `voltage-drop-dc -> BESS/PV yield` when energy losses are included.

Meta-harness handles:

- `projection`: PV cable schedule, array layout, cable datasheet, voltage-drop criterion.
- `difference`: include one-way and loop cable lengths.
- `product`: PV DC cable loss record.

## Task 8: PFC Sizing

Current world:

- Computes initial and corrected apparent power, required capacitor kVAr, and current reduction.
- Inputs are real power, initial power factor, and target power factor.
- Hard mode hides `initial_power_factor`.
- The target power factor must be greater than the initial power factor.

Multimodal expansion:

- Best first modality: metering record or load study with kW/kVAr/power factor.
- A motor-load variant can infer initial PF from motor schedule or utility bill.
- A hard variant can feed corrected reactive power into feeder voltage drop.

Requirements:

- Real power source.
- Initial PF source.
- Target PF criterion.
- Capacitor kVAr evidence.

Harness opportunities:

- Add PF inference/source gate.
- Add apparent/reactive power role gate.
- Add capacitor sizing consistency gate.
- Add feeder voltage-drop handoff gate.

Natural products:

- `pfc-sizing -> radial-feeder-voltage-drop`.
- `mechanical pump motor loads -> pfc-sizing`.
- `pfc-sizing -> voltage-regulation` for network reactive-load reduction.

Meta-harness handles:

- `projection`: power bill, metering report, motor schedule, PF target note.
- `difference`: include lagging and target PF values without labels.
- `product`: power factor correction record.

## Task 9: Radial Feeder Voltage Drop

Current world:

- Computes feeder current, voltage drop, voltage drop percentage, receiving-end voltage, and feeder loss.
- Inputs are feeder R/X, length, real/reactive load, and source voltage.
- Hard mode hides `load_reactive_power_kvar`.
- The calculation uses three-phase apparent power and R/X drop terms.

Multimodal expansion:

- Best first modality: single-line diagram plus feeder schedule and load list.
- A load-flow variant can source reactive load from power factor or PFC task output.
- A hard variant can select the feeder section and load point from a radial network.

Requirements:

- Feeder impedance and length source.
- Real and reactive load source.
- Source voltage source.
- Receiving-end voltage criterion if extended.

Harness opportunities:

- Add one-line feeder selection gate.
- Add reactive-load inference gate.
- Add apparent-current construction gate.
- Add loss and voltage-drop consistency gate.

Natural products:

- `power-load-calculation -> radial-feeder-voltage-drop`.
- `pfc-sizing -> radial-feeder-voltage-drop`.
- `radial-feeder-voltage-drop -> voltage-regulation` as LV/MV analogues.

Meta-harness handles:

- `projection`: single-line diagram, feeder schedule, load list, impedance table.
- `difference`: include upstream and downstream feeder sections.
- `product`: radial feeder voltage-drop record.

## Task 10: Voltage Drop

Current world:

- Computes cable voltage-drop coefficient, voltage drop, voltage drop percentage, and compliance flag.
- Inputs are cable size, length, current, power factor, conductor material, and circuit type.
- Hard mode hides `conductor_material`.
- The engine uses embedded voltage-drop coefficient tables and a fixed 5 percent compliance threshold.

Multimodal expansion:

- Best first modality: cable schedule plus installation/material notes.
- A hard variant can infer conductor material from schedule code or drawing note.
- A composition variant can receive load current from power or motor tasks.

Requirements:

- Cable size and length source.
- Load current source.
- Power factor source.
- Conductor material source.
- Circuit type and voltage-drop criterion.

Harness opportunities:

- Add conductor material inference gate.
- Add cable-table source gate.
- Add single-phase/three-phase branch gate.
- Add compliance flag consistency gate.

Natural products:

- `power-load-calculation -> voltage-drop`.
- `pump-power-efficiency -> voltage-drop` for motor feeders.
- `voltage-drop -> battery/UPS output feeder` in backup power worlds.

Meta-harness handles:

- `projection`: cable schedule, single-line diagram, voltage-drop table, installation note.
- `difference`: hide conductor material or include aluminium/copper alternatives.
- `product`: cable voltage-drop compliance record.

## Task 11: Voltage Regulation

Current world:

- Computes line voltage drop, voltage regulation percentage, receiving-end voltage, and power loss.
- Inputs are line R/X, length, real/reactive load, and sending voltage.
- Hard mode hides `load_reactive_power_mvar`.
- It is a transmission/subtransmission analogue of feeder voltage drop.

Multimodal expansion:

- Best first modality: line parameter schedule plus load-flow case table.
- A grid variant can require sourcing reactive load from power factor or capacitor-correction cases.
- A hard variant can compare several operating cases and identify voltage regulation worst case.

Requirements:

- Line impedance and length source.
- Real/reactive load source.
- Sending voltage source.
- Receiving-end voltage evidence.

Harness opportunities:

- Add line parameter source gate.
- Add reactive-load inference gate.
- Add load-flow case selection gate.
- Add voltage-regulation/loss consistency gate.

Natural products:

- `pfc-sizing -> voltage-regulation`.
- `davis-resistance/traction power -> voltage-regulation` in rail power contexts.
- `BESS/PV -> voltage-regulation` for grid support worlds.

Meta-harness handles:

- `projection`: line schedule, load-flow table, single-line diagram, reactive compensation note.
- `difference`: include sending, nominal, and receiving voltages together.
- `product`: line voltage regulation record.

## Task 12: Three-Phase Fault Current

Current world:

- Computes source, transformer, cable, and total impedance, plus initial symmetrical and peak fault current.
- Inputs are system voltage, source fault level, transformer rating/impedance, cable R/X/length, and voltage factor.
- Hard mode hides `voltage_factor_c`, which is expected to come from IEC 60909 voltage class context.
- Source and transformer impedances are simplified as purely reactive.

Multimodal expansion:

- Best first modality: single-line diagram plus transformer datasheet and cable schedule.
- A standards-table variant can infer voltage factor from nominal voltage class.
- A hard variant can feed fault current into incident energy, busbar force, or protection setting tasks.

Requirements:

- System voltage and source fault level source.
- Transformer rating and impedance source.
- Cable impedance and length source.
- Voltage factor source.
- Fault-location identity.

Harness opportunities:

- Add fault-location selection gate.
- Add voltage-class/voltage-factor gate.
- Add impedance decomposition gate.
- Add handoff gate to arc-flash and busbar force tasks.

Natural products:

- `three-phase-fault-current -> incident-energy`.
- `three-phase-fault-current -> busbar-forces`.
- `three-phase-fault-current -> cable-ampacity/protection package` if protective device tasks are added.

Meta-harness handles:

- `projection`: single-line diagram, transformer datasheet, cable schedule, IEC voltage-factor table.
- `difference`: include upstream and downstream fault locations.
- `product`: short-circuit current record.

## Cross-Slice Product Worlds

### Equipment Supply And Backup Package

Candidate chain:

1. Read equipment load list and compute connected load, demand, and future allowance.
2. Size UPS/battery autonomy from critical load.
3. Check cable or feeder voltage drop.
4. Feed short-circuit or protection tasks from the same single-line context.

Why it is interesting:

- It is a common infrastructure product world and strongly multimodal.
- It joins mechanical/process/life-safety loads to electrical supply design.
- It has multiple hidden context values: diversity, future allowance, derating, PF, and material.

### PV And Storage Package

Candidate chain:

1. Read module, inverter, site climate, and solar resource data.
2. Determine string window and DC/AC ratio.
3. Check DC cable voltage drop and annual energy loss.
4. Size BESS capacity for firming, backup, or peak-shaving duty.

Why it is interesting:

- It forces source-role separation between module voltage, string voltage, inverter voltage, solar yield, losses, and storage capacity.
- It naturally supports multimodal PV layouts and datasheets.
- It connects to civil solar wind actions and electrical grid voltage regulation.

### Feeder Voltage And Reactive Power Package

Candidate chain:

1. Read load study and feeder/line parameters.
2. Size PFC capacitor from initial and target PF.
3. Recompute feeder voltage drop or line regulation with corrected reactive load.
4. Report receiving-end voltage, current reduction, and losses.

Why it is interesting:

- It makes reactive power visible as an intermediate handoff.
- It provides a clean repair loop: add PFC, resize cable, shorten feeder, or revise load.
- It can be text-only or single-line/load-flow-table multimodal.

### Fault Current To Protection Package

Candidate chain:

1. Read one-line, source fault level, transformer, and cable data.
2. Compute three-phase fault current at a chosen fault location.
3. Handoff current to incident energy, busbar forces, or protection coordination.

Why it is interesting:

- It is a natural cross-template backbone for later electrical safety tasks.
- It tests fault-location selection and source impedance construction.
- It gives meta-harness mutation handles: change fault location, voltage factor, cable length, or transformer impedance.

## Repair And Extension Notes

- `bess-sizing-basic` and `bess-sizing` overlap but do not use identical capacity semantics. One uses EOL retention explicitly; the other uses degradation allowance. Combined worlds must name capacity roles rather than treating all BESS outputs as interchangeable.
- `string-sizing` clamps inverter MPPT relationships internally for sampler-generated values. Multimodal variants should either expose effective clamped values in the world sidecar or move infeasible MPPT relationships into an explicit design-repair event.
- `three-phase-fault-current` hides `voltage_factor_c` but does not verify that the provided factor matches the voltage class table. A staged verifier should check that source inference before trusting the final current.
- `voltage-drop` relies on embedded coefficient tables and a fixed 5 percent criterion. Source-artifact variants should record the table row and criterion authority.
