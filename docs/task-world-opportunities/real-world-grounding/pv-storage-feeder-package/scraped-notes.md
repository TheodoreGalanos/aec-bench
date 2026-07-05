# ABOUTME: Source-bounded notes for the PV storage feeder package.
# ABOUTME: Preserves short evidence notes without copying full manuals or standards.

# PV Storage Feeder Package Scraped Notes

## NREL PVWatts V8 API

- PVWatts V8 is the current PVWatts API and uses updated weather data and PV module, inverter, and thermal effect models.
- The current documentation notes that API users should update `developer.nrel.gov` references to `developer.nlr.gov`, with the previous domain scheduled for shutdown on May 29, 2026.
- Required inputs include output format, API key, system capacity, module type, losses, array type, tilt, and azimuth.
- Location can be provided by latitude/longitude or a specific climate data file.
- Response fields include inputs, errors, warnings, version, station information, and outputs.
- Outputs include monthly plane-of-array irradiance, monthly DC energy, monthly AC energy, annual AC energy, annual solar radiation, capacity factor, and optional hourly outputs.
- The documentation includes JSON and XML examples, making it useful for deterministic harness fixtures.

## NREL SAM And PVWatts Website

- SAM and PVWatts are useful for production modelling and techno-economic context.
- They do not replace electrical-code checks for conductors, protection, grounding, disconnects, and interconnection.

## NREL REopt

- REopt API V3 is a public API surface for energy-system optimization. The public docs describe it as backed by REopt.jl and note that V3 revised inputs and outputs for clearer structure.
- The REopt API repository describes the model as an open-source development version of the REopt API, with the production API exposed through the REopt web tool path.
- The repository README frames REopt as a mixed-integer linear optimization model that can recommend technology mixes and dispatch strategies for renewable generation, conventional generation, and energy storage.
- For this task world, REopt is useful downstream of PVWatts: PVWatts can provide production, while REopt can produce storage, generator, cost, resilience, emissions, and dispatch alternatives.
- REopt should not be treated as the feeder-code checker. It helps optimize system configuration and operation; feeder studies, interconnection screens, and commissioning evidence still need their own verifier stages.

## IEEE 1547 And IEC 62548-1 Metadata

- IEEE 1547-2018 is the active DER interconnection and interoperability standard. Public metadata identifies technical specifications and tests for DER interconnection with electric power systems.
- IEEE's public page lists interconnection topics including performance, operation, testing, safety, maintenance, abnormal condition response, power quality, islanding, commissioning, and periodic tests.
- IEC 62548-1:2023 covers PV array design requirements. Public metadata includes DC array wiring, protection devices, switching, earthing, final power conversion equipment, and safety considerations.
- IEC 62548-1:2023 explicitly identifies additional protection requirements for PV arrays that are directly connected to batteries at DC level.
- The IEEE and IEC pages are authority metadata, not enough to embed detailed clause-level grading. Any task instance using their detailed criteria should provide the relevant excerpts or use a licensed/public-view basis.

## Energy Networks Australia DER Connection Guidelines

- The ENA National DER Grid Connection Guidelines define DER broadly enough to include generation and energy storage connected to distribution networks; storage can act as both load and generation.
- The guidelines frame a consistent DNSP technical-requirements approach, with objectives around accessible requirements, consistency, risk allocation, and active DER integration.
- Technical study topics include protection, harmonics, flicker, unbalance, fault level, active/reactive power flow, voltage level, voltage step change, and earthing.
- Commissioning documentation includes single-line diagrams, equipment specifications, shutdown and communication arrangements, export limits, power quality, protection settings, earthing, voltage fluctuation evidence, applicable AS/NZS standards, certificates, and test reports.
- The guidelines' connection-arrangement appendix names SLD content that is ideal for source-pack schemas: connection point, PCC, EG units, loads, meters, breakers, isolators, and related protection/control schematics.
- Static data fields include NMI, approved capacity, installer, phase information, central protection/control, islandable status, protection/control modes, AC connection data, inverter make/model/serial/status/kVA, standards, voltage/frequency settings, demand response, volt-watt/volt-var, ROCOF/vector shift/inter-trip, and storage capacity.
- This is one of the strongest public sources for turning PV+BESS feeder work into a multi-artifact interconnection task without requiring access to a real utility project.

## PG&E Electric Rule 21

- Local PDF inspection of PG&E Electric Rule 21 found a current 290-page tariff PDF with creation and modification metadata dated June 26, 2026.
- Rule 21 defines single-line diagrams as schematic drawings that show major switchgear, protective-function devices, relay/CT/PT configurations, circuit breakers/fuses, wires, generators, transformers, meters, and other devices with enough detail for qualified engineering review.
- Initial Review Screen I asks whether power will be exported across the PCC. The screen branches into export, non-export, inadvertent export, limited export, PCS-based export control, and fast-track implications.
- Non-export and limited-export options include reverse-power protection, minimum-power protection, certified non-islanding protection, relative generating-facility rating, certified PCS, and PCS response-time constraints.
- Commissioning testing, where required, verifies protective settings and functionality on site. Rule 21 names over/under voltage, over/under frequency, anti-islanding, non-exporting, and dead-line energization functions as examples.
- The expedited non-export energy-storage section requires completed interconnection requests and supporting documentation, including SLDs with specific details, manufacturer data sheets, and control-system descriptions.
- The same section constrains eligible systems to non-exporting battery storage, inverter-based equipment, an aggregate maximum inverter nameplate limit, a single meter/PCC/disconnect arrangement, non-export protection options, coordinated controls, and UL 1741/UL 1741 SA-listed equipment.
- Rule 21 is useful as a realistic US utility world. It should not be generalized to all US utilities without authority-basis metadata on the task instance.

## California Energy Commission Solar Equipment Lists

- The CEC Solar Equipment Lists page says the lists include equipment meeting established national safety and performance standards and are used by incentive programs, grid-connection services, consumers, and state/local programs.
- The page identifies PV modules, inverters including smart inverters, meters, batteries, ESS, PCS, and related equipment as list families.
- CEC notes that some utilities or local governments may use the lists during interconnection or permit application processes.
- Grid-support inverter notes distinguish solar, battery, and solar/battery inverter lists, and warn that the required smart-inverter functionality can vary by utility, AHJ, or responsible entity.
- The Energy Storage System list covers battery energy storage systems and notes that some ESS entries may include inverters with advanced functionality.
- The PCS list records approved functionality use cases and basic manufacturer/model/functionality information; the CEC page notes a legacy PCS request-form cutoff after June 30, 2026.
- This creates a natural verifier stage: check whether listed equipment, smart-inverter functionality, ESS/battery details, and PCS/export-control function line up with the interconnection basis.

## GreenEVT / SMART-DS / OpenDSS

- GreenEVT describes an open-source testbed that jointly simulates electric distribution and transportation networks.
- The GitHub README points readers to the project wiki, cites the IEEE Systems Journal paper/preprint, states that the project uses Git LFS, and gives a fallback ZIP download when cloning is blocked by quota.
- The repository license file is MIT for the software/documentation package; actual redistributable benchmark use still needs a data-file check because large datasets are managed through Git LFS.
- `.gitattributes` marks SQLite databases, SUMO network/route/flow/additional/log XML files, shapefiles, DBF files, and database backups as Git LFS content.
- The power-grid side uses OpenDSS and high-fidelity synthetic electric distribution data from NREL SMART-DS.
- The paper says SMART-DS models capture electrical connections down to individual households, using actual building information with synthetic loads that were extensively validated against real distribution-system behavior.
- The described feeder dataset includes buses, lines, transformers, generators, loads, voltage/current limits, peak planning loads, and yearly time-series loads.
- For the Greensboro urban-suburban region, the paper reports 21 substations, 61 feeders, 154,241 buses, 218,166 total devices, and 612.7 MW total active peak load.
- OpenDSS simulations produce component power/current flows and bus voltages, and can export network data, modify components, execute time simulations, and print solution reports.
- This is not a PV+BESS design report, but it gives a realistic public substrate for feeder, load-profile, voltage-limit, and geospatial coupling variants.

## GreenEVT Repository Inspection Notes

- `data/open_dss/README.txt` says the OpenDSS folder contains network data for each substation and the subtransmission level in the Greensboro urban-suburban dataset.
- The same README names `Buscoords.dss`, `Master.dss`, `bus_info.csv`, `Long_lat_buscoords.txt`, an `analysis` folder, and multiple feeder `Load.dss` files representing EV penetration scenarios.
- `scripts/solve_opendss.py` depends on a SQLite database with table `Vehicles` and OpenDSS network files with `Master.dss`.
- The solver queries charging EVs per bus by timestamp and scenario, then adds `num_ev_charging * load_per_charging_ev` to matching DSS load lines in a working `Loads.dss` file.
- The solver compiles `Master.dss`, solves the circuit, and exports timestamped reports such as `Overloads_<timestamp>.csv`.
- The script default example uses scenario id 2, 7.5 kW per charging EV, 5 minute time steps, and `../data/UDS.db`.
- Requirements include `OpenDSSDirect.py[extras]`, `sumolib`, `pyproj`, `shapely`, `rtree`, `numpy`, and plotting/CLI helper libraries.

## Dead Ends And Limits

- Public search for accepted PV+BESS SLDs and interconnection application packages remains weak. Rule 21 and ENA define required package shape, but this pass did not recover accepted project applications with drawings, cable schedules, settings, and study results.
- Standards Australia store pages for AS/NZS 5033, AS/NZS 4777, and AS/NZS 5139 are useful as authority metadata but did not provide detailed criteria through the accessible public route.
- NFPA, IEEE, IEC, AS/NZS, and utility-specific detailed criteria should be represented as task-supplied excerpts or authority-basis metadata until licensed/public-view text is available.
