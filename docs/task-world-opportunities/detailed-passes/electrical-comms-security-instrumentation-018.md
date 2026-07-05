# ABOUTME: Detailed task-world review for electrical communications, security, structured cabling, wireless, and instrumentation tasks.
# ABOUTME: Records multimodal, composition, and meta-harness opportunities for the final electrical discipline slice.

# Electrical Communications Security And Instrumentation Pass 018

Review date: 2026-06-28

Reviewed task cards:

- `electrical/access-control/access-controller-sizing`
- `electrical/its-communications/bandwidth-calculation`
- `electrical/cctv-design/cctv-storage-calculation`
- `electrical/cctv-design/ppm-calculation`
- `electrical/poe-network/poe-power-budget`
- `electrical/structured-cabling/conduit-fill-calculation`
- `electrical/structured-cabling/fiber-link-loss-budget`
- `electrical/wireless-design/rf-link-budget`
- `electrical/signal-processing/4-20ma-scaling`
- `electrical/control-valve-sizing/cv-liquid-incompressible`

Source files read for this pass:

- `src/aec_bench/templates/builtin/electrical/access_controller_sizing/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/electrical/bandwidth_calculation/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/electrical/cctv_storage_calculation/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/electrical/ppm_calculation/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/electrical/poe_power_budget/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/electrical/conduit_fill_calculation/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/electrical/fiber_link_loss_budget/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/electrical/rf_link_budget/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/electrical/four_twenty_ma_scaling/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/electrical/cv_liquid_incompressible/{params.toml,instruction.md,engine.py}`

## Slice Read

This final electrical slice is a good example of low-voltage systems as real engineering worlds rather than pure IT arithmetic. The source packs it wants are door schedules, controller schedules, access-control risers, CCTV camera schedules, surveillance objective tables, video retention policies, PoE switch schedules, ITS device inventories, network topology diagrams, conduit/cable schedules, fibre loss budgets, wireless path sketches, instrument datasheets, process ranges, and control-valve datasheets.

The strongest composition axes are:

- security systems package: access controller sizing, PoE headroom, CCTV PPM, CCTV storage, and bandwidth;
- structured communications package: conduit fill, fibre link loss, RF link budget, PoE power, and future bandwidth buffer;
- instrumentation/control package: 4-20 mA scaling, process range selection, control valve Cv, choked-flow/cavitation branch, and mechanical/process pipe handoff;
- ITS display/network package: VMS readability from the previous pass plus network bandwidth and RF/fibre backhaul.

The practical meta-harness opportunity is policy/source governance. Retention days, target PPM, future bandwidth buffer, PoE headroom, maximum conduit fill, fibre loss budget, obstacle losses, upper range value, fluid properties, and valve recovery factor are often not in drawings; they live in design criteria, client standards, datasheets, or site context.

## Task 1: Access Controller Sizing

Current world:

- Computes controllers required, door device load, total system load, power supplies required, and battery capacity.
- Inputs are door count, doors per controller, device currents, controller current, supply capacity, backup duration, and battery derating factor.
- Hard mode hides `battery_derating_factor`.
- Controllers and power supplies are rounded up with `ceil`.

Multimodal expansion:

- Best first modality: door/access schedule plus security riser diagram.
- A campus variant can require grouping doors by controller location or building.
- A hard variant can infer battery derating from environment, battery type, or security standard.

Requirements:

- Door count/source grouping.
- Device current source.
- Controller capacity source.
- Power supply capacity source.
- Backup duration and derating source.

Harness opportunities:

- Add door schedule extraction gate.
- Add controller grouping gate.
- Add derating source gate.
- Add controller and supply rounding gates.

Natural products:

- `access-controller-sizing -> poe-power-budget`.
- `access-controller-sizing -> battery-sizing`.
- `access-controller-sizing -> bandwidth-calculation` through access network devices.

Meta-harness handles:

- `projection`: door schedule, access-control riser, device datasheet, backup policy.
- `difference`: include future doors or doors on another controller.
- `product`: access-control power and controller sizing record.

## Task 2: Bandwidth Calculation

Current world:

- Computes base bandwidth, peak demand with overhead, and required bandwidth with future buffer.
- Inputs are camera/controller/sensor counts and data rates, network overhead, and future buffer.
- Hard mode hides `future_capacity_buffer_pct`.
- All device counts and rates may be zero except the factors; the calculation can represent sparse inventories.

Multimodal expansion:

- Best first modality: ITS or security device inventory plus network design basis.
- A corridor variant can require selecting devices on one network segment.
- A hard variant can infer future buffer from planning context.

Requirements:

- Device inventory and data-rate source.
- Network overhead source.
- Future capacity buffer source.
- Network segment identity.

Harness opportunities:

- Add device inventory source gate.
- Add segment membership gate.
- Add overhead/future-buffer source gates.
- Add bandwidth handoff to fibre/RF link budgets.

Natural products:

- `cctv-storage-calculation/ppm-calculation -> bandwidth-calculation`.
- `vms-legibility-distance -> bandwidth-calculation` for ITS display networks.
- `bandwidth-calculation -> fiber-link-loss-budget/rf-link-budget` through network path selection.

Meta-harness handles:

- `projection`: ITS device schedule, network topology, data-rate table, capacity planning note.
- `difference`: include installed and future devices without labels.
- `product`: network bandwidth capacity record.

## Task 3: CCTV Storage Calculation

Current world:

- Computes daily storage per camera, usable required storage, and raw storage with overhead.
- Inputs are camera count, average bitrate, recording hours per day, retention days, and storage overhead.
- Hard mode hides `retention_days`.
- Recording hours must not exceed 24.

Multimodal expansion:

- Best first modality: CCTV camera schedule plus retention policy.
- A precinct variant can group cameras by recording profile or objective.
- A hard variant can connect PPM/objective with bitrate and retention classes.

Requirements:

- Camera count/source group.
- Bitrate source.
- Recording hours source.
- Retention policy source.
- Storage overhead source.

Harness opportunities:

- Add camera group source gate.
- Add retention-policy inference gate.
- Add bitrate/profile gate.
- Add usable/raw storage role gate.

Natural products:

- `ppm-calculation -> cctv-storage-calculation` through camera objective/profile.
- `cctv-storage-calculation -> bandwidth-calculation`.
- `cctv-storage-calculation -> poe-power-budget` through camera count.

Meta-harness handles:

- `projection`: camera schedule, retention policy, recording profile table, storage system datasheet.
- `difference`: mix continuous and motion-recording camera profiles.
- `product`: CCTV storage sizing record.

## Task 4: PPM Calculation

Current world:

- Computes horizontal field of view, pixels per metre, and margin against target PPM.
- Inputs are horizontal pixels, sensor width, focal length, target distance, and target PPM.
- Hard mode hides `target_ppm`.
- The task reports margin but not a binary pass/fail flag.

Multimodal expansion:

- Best first modality: camera datasheet plus surveillance objective/target-distance plan.
- A site plan variant can derive target distance from camera-to-target geometry.
- A hard variant can infer target PPM from objective: detection, recognition, or identification.

Requirements:

- Camera resolution/sensor/lens source.
- Target distance source.
- Surveillance objective/source target PPM.
- Margin evidence.

Harness opportunities:

- Add camera datasheet extraction gate.
- Add objective-to-target-PPM gate.
- Add geometry distance gate.
- Add margin sign/compliance gate.

Natural products:

- `ppm-calculation -> cctv-storage-calculation`.
- `ppm-calculation -> bandwidth-calculation` through bitrate/profile selection.
- `ppm-calculation -> access/security coverage package`.

Meta-harness handles:

- `projection`: camera datasheet, camera layout, surveillance objective table.
- `difference`: include detection/recognition/identification targets together.
- `product`: CCTV coverage density record.

## Task 5: PoE Power Budget

Current world:

- Computes total power requirement, utilisation, available headroom, required headroom, and headroom margin.
- Inputs are device count, power per device, switch PoE budget, and required headroom percentage.
- Hard mode hides `required_headroom_pct`.
- Negative headroom margin indicates insufficient budget but there is no binary pass flag.

Multimodal expansion:

- Best first modality: PoE switch schedule plus connected device schedule.
- A security-network variant can combine access controllers, cameras, and wireless APs.
- A hard variant can infer headroom policy from design standard or client requirement.

Requirements:

- Device count/source group.
- Device power source.
- Switch budget source.
- Required headroom source.
- Margin evidence.

Harness opportunities:

- Add switch-port/device membership gate.
- Add device power source gate.
- Add headroom policy gate.
- Add margin/compliance gate.

Natural products:

- `access-controller-sizing -> poe-power-budget`.
- `cctv-storage/ppm -> poe-power-budget` through camera count.
- `poe-power-budget -> power-load-calculation`.

Meta-harness handles:

- `projection`: switch schedule, device schedule, PoE class table, headroom policy.
- `difference`: include powered and non-powered network devices.
- `product`: PoE power budget record.

## Task 6: Conduit Fill Calculation

Current world:

- Computes total cable area, conduit area, fill percentage, and fill margin.
- Inputs are conduit internal diameter, cable count, cable outer diameter, and maximum fill percentage.
- Hard mode hides `maximum_fill_pct`.
- The calculation assumes circular cables and conduit.

Multimodal expansion:

- Best first modality: conduit/cable schedule plus pathway standard.
- A pathway variant can require selecting the correct conduit segment and cable group.
- A hard variant can infer maximum fill from standard or pathway type.

Requirements:

- Conduit internal diameter source.
- Cable count and outside diameter source.
- Fill limit source.
- Segment identity.

Harness opportunities:

- Add conduit segment selection gate.
- Add cable bundle membership gate.
- Add fill-limit source gate.
- Add margin sign gate.

Natural products:

- `conduit-fill-calculation -> fiber-link-loss-budget` through same pathway schedule.
- `conduit-fill-calculation -> poe/bandwidth package`.
- `conduit-fill-calculation -> electrical cable schedule QA`.

Meta-harness handles:

- `projection`: conduit schedule, cable schedule, pathway drawing, TIA fill criteria.
- `difference`: include spare conduits and future cables.
- `product`: structured cabling pathway fill record.

## Task 7: Fibre Link Loss Budget

Current world:

- Computes fibre loss, connector loss, splice loss, total link loss, and power margin.
- Inputs are fibre length/attenuation, connector/splice counts and losses, and system loss budget.
- Hard mode hides `system_loss_budget_db`.
- The margin can be negative when the link exceeds budget.

Multimodal expansion:

- Best first modality: fibre route schedule plus transceiver/system budget datasheet.
- A backbone variant can select connectors/splices from patching and route drawings.
- A hard variant can infer system budget from optical module type.

Requirements:

- Fibre length and attenuation source.
- Connector/splice count and loss source.
- System loss budget source.
- Route identity.

Harness opportunities:

- Add fibre route extraction gate.
- Add connector/splice count gate.
- Add transceiver budget source gate.
- Add margin/compliance gate.

Natural products:

- `bandwidth-calculation -> fiber-link-loss-budget`.
- `conduit-fill-calculation -> fiber-link-loss-budget`.
- `fiber-link-loss-budget -> ITS/security network package`.

Meta-harness handles:

- `projection`: fibre schedule, patching diagram, transceiver datasheet, link budget table.
- `difference`: include route length and cable sheath length alternatives.
- `product`: fibre optical link budget record.

## Task 8: RF Link Budget

Current world:

- Computes free-space path loss, total path loss, received signal level, and link margin.
- Inputs are transmit power/gain, distance, frequency, receive gain, obstacle losses, and required sensitivity.
- Hard mode hides `obstacle_losses_db`.
- The link margin can be negative.

Multimodal expansion:

- Best first modality: wireless path sketch plus radio datasheets.
- A terrain/building variant can infer obstacle losses from line-of-sight/path context.
- A hard variant can compare several candidate antenna locations.

Requirements:

- Transmit/receive power and gain source.
- Distance/frequency source.
- Obstacle loss source.
- Receiver sensitivity source.
- Link margin evidence.

Harness opportunities:

- Add path geometry gate.
- Add obstacle-loss inference gate.
- Add dB arithmetic gate.
- Add margin/compliance gate.

Natural products:

- `bandwidth-calculation -> rf-link-budget`.
- `vms/ITS package -> rf-link-budget`.
- `rf-link-budget -> power/PoE package` for remote wireless devices.

Meta-harness handles:

- `projection`: path profile, radio datasheet, antenna schedule, obstruction map.
- `difference`: include LOS and obstructed path alternatives.
- `product`: wireless link budget record.

## Task 9: 4-20 mA Scaling

Current world:

- Computes span percentage, current signal, and reconstructed process value.
- Inputs are process value, lower range value, and upper range value.
- Hard mode hides `upper_range_value`.
- Process value must lie within configured range.

Multimodal expansion:

- Best first modality: instrument datasheet or loop schedule.
- A process-control variant can infer upper range from tag range or P&ID note.
- A hard variant can compare measured current with reconstructed process value.

Requirements:

- Process value source.
- Lower and upper range source.
- Instrument tag identity.
- Range validity evidence.

Harness opportunities:

- Add instrument range source gate.
- Add span construction gate.
- Add current/reconstruction round-trip gate.
- Add out-of-range event gate.

Natural products:

- `4-20ma-scaling -> cv-liquid-incompressible` through process measurement/control context.
- `4-20ma-scaling -> mechanical process mass-balance` for instrumentation evidence.
- `4-20ma-scaling -> controls commissioning artifact`.

Meta-harness handles:

- `projection`: instrument datasheet, loop schedule, P&ID tag, historian row.
- `difference`: include calibrated range and alarm range together.
- `product`: analogue signal scaling record.

## Task 10: Cv Liquid Incompressible

Current world:

- Computes pressure drop, required Cv, choked pressure drop, and a choked-flow flag.
- Inputs are flow, upstream/downstream pressures, specific gravity, vapor pressure, critical pressure, and valve FL recovery factor.
- Hard mode hides fluid specific gravity, vapor pressure, critical pressure, and FL.
- The engine limits effective pressure drop to the choked pressure drop when actual pressure drop exceeds it.

Multimodal expansion:

- Best first modality: control valve datasheet plus process line data.
- A P&ID/process variant can source flow and pressures from process conditions.
- A hard variant can infer fluid properties from fluid name, temperature, and datasheet.

Requirements:

- Flow and pressure source.
- Fluid property source.
- Valve FL source.
- Choked-flow branch evidence.
- Cv output handoff to valve selection.

Harness opportunities:

- Add P&ID/process condition gate.
- Add fluid property inference gate.
- Add choked-flow branch gate.
- Add valve selection/authority extension gate.

Natural products:

- `mechanical pressure-loss/mass-balance -> cv-liquid-incompressible`.
- `4-20ma-scaling -> cv-liquid-incompressible` in a control loop package.
- `cv-liquid-incompressible -> pump/process duty` for process plant worlds.

Meta-harness handles:

- `projection`: P&ID, valve datasheet, process data sheet, fluid property table.
- `difference`: include normal, maximum, and minimum flow cases.
- `product`: control valve sizing record.

## Cross-Slice Product Worlds

### Security Systems Package

Candidate chain:

1. Read door schedule, access controller riser, and security device schedule.
2. Size access controllers, power supplies, and backup capacity.
3. Compute PoE switch budget for access/CCTV devices.
4. Compute CCTV PPM and storage by camera objective.
5. Compute bandwidth for network segment.

Why it is interesting:

- It is a real low-voltage/security design package.
- It forces the model to keep door counts, camera counts, power draw, bitrate, retention, and network segment membership separate.
- It can be strongly multimodal with schedules, risers, layouts, and policy tables.

### Structured Communications Link Package

Candidate chain:

1. Read network topology and pathway schedules.
2. Compute conduit fill for the selected pathway.
3. Compute fibre link loss or RF link budget for the selected communications path.
4. Compare against required bandwidth and margin.

Why it is interesting:

- It combines physical pathway capacity with communications performance.
- It provides clean repair actions: larger conduit, fewer cables, lower-loss fibre, fewer splices, antenna relocation, or higher-link-budget radios.
- It can connect directly to ITS/VMS and security systems.

### Instrumented Process Control Package

Candidate chain:

1. Read P&ID, process conditions, instrument loop schedule, and valve datasheet.
2. Scale the process value to 4-20 mA.
3. Size liquid control valve Cv and identify choked/cavitating flow.
4. Handoff flow/pressure/control state to mechanical process or pump tasks.

Why it is interesting:

- It bridges electrical/instrumentation and mechanical process engineering.
- It has strong hidden-property inference from fluid and valve datasheets.
- It can test whether the model preserves tag identity across P&ID, loop schedule, and calculation.

### ITS Display And Backhaul Package

Candidate chain:

1. Use VMS readability/message constraints from the transport pass.
2. Add ITS camera/controller/sensor inventory.
3. Compute bandwidth.
4. Check fibre or RF backhaul margin.

Why it is interesting:

- It combines human readability, device inventory, network load, and physical link design.
- It allows meta-harness mutations at message, device, network, and route/path levels.
- It naturally creates evidence artifacts: sign schedule, message library, topology, and link budget.

## Repair And Extension Notes

- `ppm-calculation`, `poe-power-budget`, `fiber-link-loss-budget`, and `rf-link-budget` expose margins but not pass/fail flags. Product-world verifiers should check margin sign before declaring compliance.
- `bandwidth-calculation` can validly produce zero demand if all device counts/rates are zero. Multimodal variants should treat empty inventories as explicit source states, not accidental omissions.
- `cv-liquid-incompressible` carries several hidden fluid/valve properties and a choked-flow branch. It is a strong candidate for staged source verification before final Cv scoring.
- Security and communications tasks need segment membership gates: the most common multimodal failure will be counting devices from the wrong floor, building, network segment, or controller.
