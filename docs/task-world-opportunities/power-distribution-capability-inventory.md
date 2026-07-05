# ABOUTME: Inventories power-distribution-relevant task seeds and template coverage.
# ABOUTME: Maps SME-style task requirements, workflows, and hardening opportunities.

# Power Distribution Capability Inventory

This inventory maps the power-distribution-relevant material currently visible in the repo. I did not find a separate SME skill bundle under `agents/`, `.codex/`, or `src/aec_bench/init/skill_data`; the actionable material is in the electrical task seeds under `tasks/electrical/**/source_task.json`, with partial implementation coverage in `src/aec_bench/templates/builtin/electrical/`.

## Source Set

The core power-distribution slice contains 55 task seeds:

| Source Community | Seeds | Built-In Templates | Seed Only | Role In The Capability |
| --- | ---: | ---: | ---: | --- |
| `transmission_lines` | 19 | 7 | 12 | Overhead/underground line geometry, conductor physics, clearances, loading, and ratings. |
| `substations` | 17 | 5 | 12 | Primary equipment, protection, grounding, cables, DC systems, busbars, and transformer loading. |
| `energy_systems_studies` | 11 | 3 | 8 | Load flow, voltage quality, harmonics, short circuit, motor starting, and arc flash studies. |
| `energy_generation_storage` | 7 | 4 | 3 | DER, BESS, PV strings, grid-code ride-through, and connection studies. |
| `grounding_systems` | 1 | 0 | 1 | Integrated substation grounding-grid layout. |

Adjacent electrical seeds also touch power distribution, but are not counted in the 55-core slice: building cable/protection checks, industrial motor feeders, rail traction power, ITS power supply, PoE cabinet power, and signalling backup power.

## Capability Map

| Capability Area | Tasks Present | Typical Requirements | Typical Practitioner Steps | Current Maturity |
| --- | --- | --- | --- | --- |
| Feeder and network voltage studies | `radial-feeder-voltage-drop`, `network-load-flow`, `voltage-regulation`, `pfc-sizing`, `motor-starting-study` | Network topology, source voltage, bus or node loads, line/cable R/X, transformer taps, power factor, voltage limits. | Define case and base values; assemble topology and impedances; solve voltage/current/losses; compare bus voltages and branch flows to limits; recommend PFC, taps, feeder changes, or load constraints. | Good starting point: `radial-feeder-voltage-drop`, `voltage-regulation`, and `pfc-sizing` already have built-in templates. |
| Short circuit, protection, and arc flash | `three-phase-fault-current`, `unsymmetrical-fault`, `equipment-duty-check`, `fault-current-calc`, `relay-pickup-setting`, `arc-flash-calculation`, `arc-flash-assessment` | Source impedance, transformer/cable/motor impedances, X/R ratio, grounding method, fault location/type, device ratings, CT ratio, clearing time, working distance. | Select fault case; compute symmetrical/asymmetrical or sequence currents; compare equipment making/breaking/withstand duty; set relay pickup margins; calculate incident energy and labels where needed. | Mixed: `three-phase-fault-current` is built in, most protection coordination and duty checks are seed-only. |
| Substation equipment sizing and checks | `transformer-sizing`, `thermal-loading`, `busbar-thermal`, `busbar-forces`, `battery-sizing`, `dc-system-study`, `arrester-selection`, `outdoor-lighting` | Load profiles, growth/diversity, transformer test data, busbar geometry, battery duty cycle, charger/load lists, MCOV/TOV/BIL, illumination criteria. | Select governing duty; calculate equipment rating or operating temperature; verify margins against standard criteria; produce rating, loss-of-life, capacity, or layout decision. | `busbar-forces`, `battery-sizing`, and several cable/grounding checks are built in; transformer thermal/loading and arrester selection are seed-only. |
| Cables, ducts, and installation constraints | `cable-ampacity`, `voltage-drop`, `conduit-fill`, `cable-ampacity-iec60287`, `cable-pulling-tension`, `duct-bank-mutual-heating` | Cable construction, conductor size/material, installation method, ambient or soil temperature, grouping, route length, bend radii, duct geometry, thermal resistivity. | Establish installation case; apply ampacity/derating or thermal model; check voltage drop or pulling sidewall pressure; identify limiting segment or hottest cable; record pass/fail and required size. | `cable-ampacity` and `voltage-drop` are built in; IEC 60287, pulling tension, and duct-bank thermal interaction are seed-only. |
| Overhead line geometry, sag, clearance, and loads | `catenary-sag-single-span`, `ruling-span-calculation`, `state-change-equation`, `ground-clearance-check`, `blowout-clearance`, `phase-to-phase-clearance`, `wind-load-conductor`, `ice-load-calculation`, `broken-wire-load` | Conductor properties, span lengths, tensions, temperature, wind/ice cases, attachment heights, terrain/crossing type, voltage level, structure type. | Select weather/load case; calculate sag/tension or conductor displacement; check ground/structure/phase clearances; compute wind/ice/broken-wire loads for structures; report governing condition and margin. | Strong formula substrate: `wind-load-conductor` and `ice-load-calculation` are built in; most sag/clearance variants remain seed-only. |
| Conductor electrical parameters and ratings | `ac-resistance-temperature`, `line-inductance`, `line-capacitance`, `static-thermal-rating`, `dynamic-line-rating` | Conductor geometry, GMR/GMD, phase spacing, operating temperature, weather time series, solar radiation, wind speed, maximum conductor temperature. | Compute electrical parameters; run heat balance or weather-series rating; produce ampacity, losses, voltage regulation inputs, and rating bottlenecks. | Good formula coverage for `ac-resistance-temperature`, `line-inductance`, `line-capacitance`, and `static-thermal-rating`; dynamic line rating remains seed-only. |
| Grounding and lightning safety | `grid-resistance`, `step-touch-potential`, `grounding-grid-layout`, `backflashover-rate` | Soil resistivity, grid area/conductor length, fault current/duration, surface layer, tower footing resistance, insulator CFO, ground flash density. | Build soil/fault case; calculate grid resistance/GPR or backflashover rate; verify touch/step safety or lightning performance; flag layout or footing improvements. | `grid-resistance` is built in; step/touch, full grid layout, and lightning backflashover are seed-only. |
| DER, PV, BESS, and grid-code interface | `bess-sizing-basic`, `dc-ac-ratio`, `string-sizing`, `voltage-drop-dc`, `fault-level-contribution`, `reactive-power-capability`, `voltage-ride-through`, `fault-ride-through` | PV/BESS ratings, inverter limits, temperature corrections, DC cable length, ride-through curves, grid-code thresholds, IBR fault contribution, PCC fault level. | Size energy/power/string configuration; check DC voltage/drop; calculate reactive capability or fault contribution; compare ride-through and grid-code margins. | PV/BESS arithmetic is well covered; grid-code ride-through and fault/reactive capability remain seed-only. |
| Power quality | `harmonic-distortion-calculation`, `ieee519-compliance` | PCC location, short-circuit ratio, non-linear load spectrum, system impedance by frequency, THD/TDD limits. | Assemble harmonic source and network case; calculate individual harmonics and THD/TDD; compare to IEEE 519 or regional limits; report margin and mitigation need. | Seed-only, likely needs source-pack fixtures or a small harmonic calculation engine. |

## Core Task Inventory

| Community | Category | Task | Human Meaning | Maturity |
| --- | --- | --- | --- | --- |
| `energy_generation_storage` | `bess-design` | `bess-sizing-basic` | Size BESS power and energy for a duty duration. | Built-in template |
| `energy_generation_storage` | `grid-connection` | `fault-level-contribution` | Estimate inverter-based resource fault contribution at the connection point. | Seed only |
| `energy_generation_storage` | `grid-connection` | `reactive-power-capability` | Check whether an inverter can meet required P-Q or power-factor capability. | Seed only |
| `energy_generation_storage` | `grid-connection` | `voltage-ride-through` | Verify generating plant ride-through settings against grid-code envelopes. | Seed only |
| `energy_generation_storage` | `solar-pv-design` | `dc-ac-ratio` | Calculate PV DC/AC sizing ratio and clipping implication. | Built-in template |
| `energy_generation_storage` | `solar-pv-design` | `string-sizing` | Choose module count per string under cold/hot voltage limits. | Built-in template |
| `energy_generation_storage` | `solar-pv-design` | `voltage-drop-dc` | Check DC string cable voltage drop and energy loss. | Built-in template |
| `energy_systems_studies` | `grid-code` | `fault-ride-through` | Verify generator fault ride-through recovery and compliance. | Seed only |
| `energy_systems_studies` | `harmonics` | `harmonic-distortion-calculation` | Calculate harmonic distortion at the PCC. | Seed only |
| `energy_systems_studies` | `harmonics` | `ieee519-compliance` | Check THD/TDD against IEEE 519 limits. | Seed only |
| `energy_systems_studies` | `load-flow` | `network-load-flow` | Solve an AC network model for bus voltages, flows, and losses. | Seed only |
| `energy_systems_studies` | `load-flow` | `pfc-sizing` | Size capacitor correction to reach a target power factor. | Built-in template |
| `energy_systems_studies` | `load-flow` | `radial-feeder-voltage-drop` | Calculate voltage drop and losses along a radial feeder. | Built-in template |
| `energy_systems_studies` | `protection` | `arc-flash-calculation` | Calculate incident energy and PPE boundary from fault and clearing data. | Seed only |
| `energy_systems_studies` | `short-circuit` | `equipment-duty-check` | Compare calculated fault duty against equipment ratings. | Seed only |
| `energy_systems_studies` | `short-circuit` | `three-phase-fault-current` | Calculate three-phase short-circuit current. | Built-in template |
| `energy_systems_studies` | `short-circuit` | `unsymmetrical-fault` | Calculate ground or line-line fault currents using sequence networks. | Seed only |
| `energy_systems_studies` | `stability` | `motor-starting-study` | Check voltage dip during motor starting. | Seed only |
| `grounding_systems` | `grid-design` | `grounding-grid-layout` | Lay out a grounding grid and verify IEEE 80 safety metrics. | Seed only |
| `substations` | `busbar-design` | `busbar-forces` | Calculate short-circuit forces on busbars. | Built-in template |
| `substations` | `busbar-design` | `busbar-thermal` | Size busbars for continuous current and temperature rise. | Seed only |
| `substations` | `cable-sizing` | `cable-ampacity` | Calculate derated cable current capacity. | Built-in template |
| `substations` | `cable-sizing` | `conduit-fill` | Select conduit size from cable fill percentage. | Seed only |
| `substations` | `cable-sizing` | `voltage-drop` | Verify cable voltage drop against allowable limits. | Built-in template |
| `substations` | `dc-systems` | `battery-sizing` | Size station battery capacity for control/protection duty. | Built-in template |
| `substations` | `dc-systems` | `dc-system-study` | Check DC voltage at loads during discharge. | Seed only |
| `substations` | `grounding-design` | `grid-resistance` | Calculate substation grounding-grid resistance and GPR. | Built-in template |
| `substations` | `grounding-design` | `step-touch-potential` | Verify step and touch voltages against tolerable limits. | Seed only |
| `substations` | `illumination-design` | `outdoor-lighting` | Lay out substation yard lighting for illuminance and uniformity. | Seed only |
| `substations` | `lightning-protection` | `arrester-selection` | Select surge arrester rating and protective margin. | Seed only |
| `substations` | `protection-coordination` | `relay-pickup-setting` | Set overcurrent relay pickup from load and minimum fault current. | Seed only |
| `substations` | `short-circuit-analysis` | `arc-flash-assessment` | Assess substation arc-flash incident energy and labels. | Seed only |
| `substations` | `short-circuit-analysis` | `equipment-duty-check` | Verify switchgear and equipment against available fault levels. | Seed only |
| `substations` | `short-circuit-analysis` | `fault-current-calc` | Calculate symmetrical, peak, breaking, and thermal fault currents. | Seed only |
| `substations` | `transformer-loading` | `thermal-loading` | Calculate transformer hot-spot temperature and loss of life. | Seed only |
| `substations` | `transformer-loading` | `transformer-sizing` | Select transformer kVA rating from load and growth assumptions. | Seed only |
| `transmission_lines` | `clearance-verification` | `blowout-clearance` | Check wind-blown conductor clearance to structures. | Seed only |
| `transmission_lines` | `clearance-verification` | `ground-clearance-check` | Check conductor ground clearance at maximum sag. | Seed only |
| `transmission_lines` | `clearance-verification` | `phase-to-phase-clearance` | Verify inter-phase clearance under differential movement. | Seed only |
| `transmission_lines` | `electrical-parameters` | `ac-resistance-temperature` | Calculate AC resistance at operating temperature. | Built-in template |
| `transmission_lines` | `electrical-parameters` | `line-capacitance` | Calculate line capacitance from conductor geometry. | Built-in template |
| `transmission_lines` | `electrical-parameters` | `line-inductance` | Calculate line inductance from phase spacing and GMR/GMD. | Built-in template |
| `transmission_lines` | `electrical-parameters` | `voltage-regulation` | Calculate receiving-end voltage and regulation on a line. | Built-in template |
| `transmission_lines` | `lightning-protection` | `backflashover-rate` | Estimate lightning backflashover outage rate. | Seed only |
| `transmission_lines` | `sag-tension` | `catenary-sag-single-span` | Calculate sag for one conductor span. | Seed only |
| `transmission_lines` | `sag-tension` | `ruling-span-calculation` | Calculate equivalent ruling span for a line section. | Seed only |
| `transmission_lines` | `sag-tension` | `state-change-equation` | Recalculate conductor tension and sag under new temperature/load. | Seed only |
| `transmission_lines` | `structural-loading` | `broken-wire-load` | Calculate unbalanced load from a broken conductor case. | Seed only |
| `transmission_lines` | `structural-loading` | `ice-load-calculation` | Calculate conductor ice plus wind loading. | Built-in template |
| `transmission_lines` | `structural-loading` | `wind-load-conductor` | Calculate wind load on conductor span. | Built-in template |
| `transmission_lines` | `thermal-rating` | `dynamic-line-rating` | Calculate weather-varying conductor ampacity. | Seed only |
| `transmission_lines` | `thermal-rating` | `static-thermal-rating` | Calculate steady-state overhead conductor ampacity. | Built-in template |
| `transmission_lines` | `underground-cables` | `cable-ampacity-iec60287` | Calculate underground cable ampacity using IEC 60287. | Seed only |
| `transmission_lines` | `underground-cables` | `cable-pulling-tension` | Check cable pulling tension and sidewall pressure. | Seed only |
| `transmission_lines` | `underground-cables` | `duct-bank-mutual-heating` | Derate duct-bank cables for mutual heating. | Seed only |

## Adjacent Seeds Worth Keeping In View

| Area | Examples | Why They Matter |
| --- | --- | --- |
| Building and industrial feeders | `single-circuit-cable-sizing`, `motor-cable-sizing`, `fault-current-at-load`, `equipment-fault-rating`, `bonding-verification` | These are distribution-adjacent calculations but scoped to facilities or equipment rather than utility distribution networks. |
| Rail and traction power | `traction-power/load-flow-simulation`, `traction-power/voltage-drop-calculation`, `third-rail-voltage-drop` | These reuse feeder/load-flow concepts in rail power networks. |
| ITS and field equipment power | `solar-power-sizing`, `power-load-calculation`, `poe-power-budget`, `wayside-cabinet-load-communications-backup-supply-package` | These are useful for low-voltage distribution to roadside or communications equipment. |
| Existing long-horizon packages | `mechanical-load-feeder-voltage-package`, `der-resilience-feeder-interconnection-package`, `regional-load-flow-voltage-regulation-package`, `pv-bess-interconnection-export-control-package` | These show how the formula seeds can become multi-artifact design tasks. |

## What A Runnable Task Usually Needs

Across the power-distribution slice, a strong task generally needs:

- A named design case: voltage level, load case, fault case, weather case, grid-code event, or operating scenario.
- Source artifacts: SLD, feeder schedule, conductor/cable schedule, transformer data, protection settings, network topology, load profile, weather series, or equipment datasheet.
- Standards or acceptance criteria: voltage limits, thermal limits, clearance limits, protection/duty margins, IEEE/IEC/AS criteria, or grid-code ride-through envelope.
- A calculation chain with explicit handoffs: impedances to currents, currents to voltage drop or fault duty, weather to conductor rating, load profile to transformer aging, or source case to pass/fail margin.
- A result ledger: final scalar results plus enough intermediate values to audit units, identity, and assumptions.

## Good Next Template Candidates

The highest-value candidates are not necessarily the easiest formulas; they are the tasks that connect real distribution engineering artifacts to clear verifier gates.

| Candidate | Why It Is Useful | Hardening Need |
| --- | --- | --- |
| `equipment-duty-check` | Forces source fault levels, equipment ratings, and pass/fail margins to stay consistent. | Needs switchgear rating schedule, fault-current source, and negative cases for stale ratings. |
| `relay-pickup-setting` | Converts protection intent into settings and fault-detection margin. | Needs CT ratio, load/fault cases, relay curve metadata, and source echo checks. |
| `transformer-sizing` and `thermal-loading` | Very recognizable distribution planning/design work. | Needs load profile, ambient profile, overload rule, growth assumption, and loss-of-life output checks. |
| `step-touch-potential` or `grounding-grid-layout` | Strong safety-critical engineering surface. | Needs soil model, grid layout, fault clearing time, surface layer data, and authority boundary. |
| `dynamic-line-rating` | Turns weather time series into operational ampacity. | Needs weather CSV, conductor data, thermal model, and time-series verifier checks. |
| `duct-bank-mutual-heating` | Real distribution cable problem with geometry, thermal, and loading interaction. | Needs duct-bank geometry, soil thermal values, circuit load factors, and hottest-cable diagnostics. |
| `voltage-ride-through` / `fault-ride-through` | Connects DER settings to grid-code compliance. | Needs ride-through curves, trip settings, fault event profile, and explicit compliance margins. |

## Gaps

The visible slice is strong on calculations, but less complete as a distribution practice model:

- There is no obvious explicit distribution-planning task for load growth, ADMD/diversity, or feeder augmentation.
- Protection coordination is mostly represented as pickup, duty, and arc-flash tasks; curve coordination and selectivity are still thin.
- There is no clear recloser/sectionalizer/fuse coordination task.
- Hosting capacity, voltage unbalance, flicker, and distributed PV penetration studies are not explicit.
- Network model exchange is not grounded yet in OpenDSS, PowerFactory, CYME, PSS/E, or utility GIS/ADMS-style files.
- Most source seeds are still proposed metadata, not source-pack hardened or benchmark-ready tasks.

## Suggested Working Boundary

Treat this as a power-distribution capability inventory, not a benchmark readiness claim. The core substrate is already broad enough to support a serious distribution task program; the next useful move is to pick one or two source-pack-style tasks and harden them around real engineering artifacts rather than adding more formula breadth.
