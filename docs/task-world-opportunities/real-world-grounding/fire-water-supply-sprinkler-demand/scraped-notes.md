# ABOUTME: Source-bounded notes for the fire water supply and sprinkler demand package.
# ABOUTME: Preserves short evidence notes without copying full standards or copyrighted material.

# Fire Water Supply And Sprinkler Demand Scraped Notes

## NFPA Source Access

- NFPA 13, NFPA 20, and NFPA 291 public pages were reachable as authority landing pages, but exposed little or no extractable text through the current access path.
- Treat these as primary-gated sources until licensed or public-view standard text can be consulted.

## Public Orientation Sources

- Public hydraulic-calculation summaries describe sprinkler hydraulic calculations as checks that water supply and pipe network can meet demand.
- Public hydrant-flow-test summaries describe static pressure, residual pressure, flow hydrant, pitot pressure, and estimated available flow.
- Public fire-pump summaries describe fire pumps as devices used to boost water supply for sprinkler/standpipe/fire protection systems when supply pressure is inadequate.

## USEPA EPANET Water-Supply Modelling

- EPA describes EPANET as a public-domain water-distribution modelling application used by engineers and consultants for design, retrofit, operations, emergency preparation, and fire-flow analysis.
- EPANET models pressurized pipe networks with pipes, nodes, pumps, valves, storage tanks, and reservoirs.
- EPA lists outputs and reporting surfaces relevant to source packs: pipe flow, node pressure, tank height, pump energy/cost, data tables, profile plots, and network maps.
- EPA notes hydraulic capabilities that map to a fire-water supply chain: Hazen-Williams/Darcy-Weisbach/Chezy-Manning headloss, minor losses, variable-speed pumps, valves, and pressure-dependent emitter flows.
- This helps the hydrant/supply-network side of the task. It does not replace NFPA/EN/AS sprinkler design criteria or AHJ review requirements.
- The EPANET 2.2 repository says the release archives the source code, user manual, and integrated help material for the EPA/OWA 2.2.0 release under MIT license.
- The online EPANET manual records an example network with node elevations, demands, pipe lengths/diameters/C-factors, pump head/flow, tank dimensions, GPM units, and Hazen-Williams setup.
- The EPANET FAQ gives a direct fire-flow modelling pattern: add fire flow to normal junction demand and inspect resulting pressure, or estimate available flow at a target pressure using a high emitter coefficient and pressure-head adjustment.
- This gives enough structure for an EPANET-backed water-supply fixture even if the sprinkler-code side remains task-supplied.

## USEPA WNTR Fire-Flow Fixtures

- WNTR's public documentation describes it as an EPANET-compatible Python package for simulating and analyzing water-distribution network resilience.
- The WNTR docs and repository identify capabilities relevant to fire-flow fixtures: generating or modifying water-network models, adding disruptive events, simulating pressure-dependent demand, simulating demand-driven hydraulics, evaluating resilience, and visualizing results.
- The USEPA/WNTR repository states that its `examples` directory contains examples and network files and that WNTR is released under a Revised BSD license.
- Repository tree inspection found redistributable EPANET-compatible network files in `examples/networks`: `Net1.inp`, `Net2.inp`, `Net3.inp`, `Net6.inp`, `ky4.inp`, and `ky10.inp`, with matching JSON files for several networks.
- The same tree inspection found `examples/fire_flow.py`, `examples/fire_flow_tutorial.ipynb`, and fire-flow output CSVs under `wntr/tests/data_for_testing`: `fire_flow_junctions_impacted.csv` and `fire_flow_people_impacted.csv`.
- WNTR `fire_flow.py` uses `networks/Net3.inp`, sets the hydraulic demand model to PDD, adds 4000 gpm fire-fighting demand at node `197` from hour 10 to hour 36, runs the fire-flow simulation, removes the fire demand, runs the nominal simulation, and plots pressure difference at 24 hours.
- The WNTR fire-flow tutorial uses `networks/Net3.inp`, minimum pressure 5 psi, required pressure 20 psi, 8000 gpm fire demand, hydrant candidates derived from connected pipe diameters, a baseline non-zero-demand pressure screen, per-hydrant fire-flow simulations, impacted-junction counts, impacted-population estimates, and CSV exports.
- Downloaded `examples/networks/Net3.inp` identifies itself as "EPANET Example Network 3" and includes junctions, reservoirs, tanks, pipes, pumps, valves, demands, patterns, curves, controls, energy settings, emitters, quality/sources/reactions, times, report settings, options, coordinates, vertices, and labels.
- The inspected Net3 file has 496 lines, uses a 168:00 duration, and the inspected options use GPM units and Hazen-Williams headloss.
- The inspected fire-flow output CSVs are small two-column result tables keyed by node or hydrant/fire-flow location; one records impacted-junction counts and the other records impacted-population values.
- The inspected `fire_flow_junctions_impacted.csv` has 39 keyed rows after the header; six rows are nonzero: 151 has 1, 213 has 3, 255 has 1, 237 has 3, 143 has 1, and 141 has 1, for 10 total impacted junctions.
- The inspected `fire_flow_people_impacted.csv` has 39 keyed rows after the header; the same six keys are nonzero: 151 has 340.0, 213 has 917.0, 255 has 420.0, 237 has 917.0, 143 has 1902.0, and 141 has 1902.0, for 6,398 total impacted people.
- The inspected notebook has 18 cells. Its fire-flow parameter cell sets a 2-hour start, 4-hour fire duration, 8000 gpm demand, 5 psi minimum pressure, 20 psi required pressure, and a 6-to-8-inch pipe-diameter filter for hydrant candidate selection.
- The inspected notebook derives hydrant candidates from junctions connected to pipes in the selected diameter range, screens normal low-pressure nodes using average expected demand and PDD simulation, applies a binary fire-flow pattern at each candidate, records additional low-pressure non-zero-demand junctions as impacted, sums population for those impacted junctions, and writes the two CSV outputs.
- GitHub API inspection pinned current WNTR `main` to commit `2a69d56073436c9bb5d0290ce1276d46c38b5474`, committed 2026-06-25T19:12:01Z with message `Test cleanup (#570)`.
- GitHub API inspection reported latest WNTR release tag `1.4.0`, named `Version 1.4.0 Release`, published 2025-11-22T00:20:39Z, targeting `main`.
- Commit-pinned raw downloads from `2a69d56073436c9bb5d0290ce1276d46c38b5474` produced this manifest: `fire_flow.py` 32 lines, 1,221 bytes, SHA-256 `614f343b58950f621a4c616ac4b99991d76716068fedb0213605f54b79c8ea2c`; `fire_flow_tutorial.ipynb` 298 lines, 10,637 bytes, SHA-256 `17618036eed5f3e4540dc1ac97d2a440e43d9a230850fb6d62c9736ef1be7734`; `Net3.inp` 496 lines, 31,249 bytes, SHA-256 `ea3e825c4fef0b5cba47fb06301bc85253f18b6364dc96c44d9fb492c40faa52`; `fire_flow_junctions_impacted.csv` 40 lines, 236 bytes, SHA-256 `246048894b32d23bb4608fc0277b255a1ba2cda8d584ebf4dc8f365411420847`; `fire_flow_people_impacted.csv` 40 lines, 328 bytes, SHA-256 `91c4bd53c4c14c128b1b26c142fb1f25415cebbbcd248d9cac2974359fa7cea3`.
- Commit-pinned notebook metadata reports nbformat 4.4, 18 cells, `python3` kernel, and Python 3.12.10 language metadata.
- WNTR's public license file says WNTR is distributed under the Revised BSD License and includes EPANET code under MIT license. If these files become bundled source-pack artifacts, preserve the license notices rather than copying files without provenance.
- Local `uv run python` inspection in this repo found `wntr_installed False` for the base environment, but a temporary `uv run --with wntr==1.4.0` command installed an ephemeral WNTR runtime and reported `wntr 1.4.0`.
- A temporary reproduction script mirroring the WNTR tutorial logic was run against the commit-pinned raw files with `uv run --with wntr==1.4.0`. It reported WNTR version 1.4.0, 39 hydrant candidates, 39 actual rows in each output, 10 impacted junctions, 6,398 impacted people, nonzero keys 141, 143, 151, 213, 237, and 255 for both outputs, `junction_match=True`, and `people_match=True`.
- This materially improves the redistributable fire-flow model fixture path, but it does not produce a filled hydrant-flow form, processed AHJ water-flow request, AHJ-approved sprinkler hydraulic calculation, FM deterministic data-sheet criterion, or filled FUS WS4 attachment bundle.

## FM Property-Risk Review Surface

- FM's project-services page identifies fire sprinkler installations or modifications, new fire pumps, suction tanks, and underground fire-water mains as projects that should be submitted for review.
- FM frames project review as property-risk/loss-prevention work rather than AHJ permitting, so it is a parallel authority/review surface for commercial tasks.
- FM's plan-review checklist requires fire-protection drawings of the proposed sprinkler system, section views as needed, material cut sheets, sprinkler detail drawings, hydraulic calculations, and actual hydrant-flow water-supply evidence.
- The same checklist adds cross-discipline fields: seismic bracing proposal/drawings/calculations in earthquake zones, storage commodity and arrangement details for storage areas, pump curves and pump-room details for fire/booster pumps, and shop drawings/material cut sheets for underground mains.
- FM's data-sheet page says property loss prevention data sheets are free engineering guidelines, but this pass did not recover a stable specific sprinkler data sheet or worked calculation artifact from the dynamic index.
- Harness implication: use the FM checklist as a source-pack schema and review-path variant, but do not silently grade against unstated FM data-sheet criteria.

## FM Code-Support Reports

- FM's code-support report page says FM research in fire, construction, natural hazards, and risk evaluation is incorporated into FM Property Loss Prevention Data Sheets and used to enhance external standards and codes.
- The same page says the technical reports are provided so supporting material for code/standard criteria is freely available to interested readers.
- The page exposes named sprinkler/fire-protection reports for EN 12845 and NFPA 13, including EN 12845 incidental plastics storage, NFPA 13 in-rack automatic sprinkler designs, and NFPA 13 ESFR protection of exposed nonexpanded Group A plastics.
- The EN 12845 incidental-storage report is a public release report prepared for CEN TC191/WG5/TG2 to support revision of EN 12845.
- The EN 12845 report explicitly links the proposal to FM Global Property Loss Prevention Data Sheet 3-26, Fire Protection for Nonstorage Occupancies.
- The EN 12845 report records incidental-storage test conditions with plastic pallets, target CUP commodity, storage heights, aisle width, ceiling heights, K160/K11.2 sprinklers, 0.5 bar/7 psi operating pressure, 12 mm/min density, activation counts, temperature and heat-release observations, and target-involvement outcomes.
- The EN 12845 report states that all 49 sprinklers operated in each of the three tests; it uses that result to warn that the demand area can exceed a typical non-storage sprinkler demand area.
- The EN 12845 report's recommendation boundary is useful for tasks because it links storage footprint, plastic content, height, and aisle separation to sprinkler-demand concern, while still being report evidence rather than a project hydraulic calculation.
- The NFPA 13 in-rack report is a public release report prepared for the NFPA 13 Sprinkler System Discharge Criteria committee.
- The NFPA 13 in-rack report contains table/figure lists for rack-storage configuration, pre-test images, plan views, IRAS layout, activation patterns, post-test damage, gas temperatures, recommendations, and appendices.
- The NFPA 13 in-rack report documents instrumentation, timing wires, thermocouples, gas/temperature measurements, full-scale test setup, and evaluation paths for in-rack automatic sprinkler designs.
- The NFPA 13 in-rack report gives a recommendation-style boundary for UUP rack protection using quick-response pendent K320/K22.4 or larger face sprinklers, maximum vertical and horizontal spacing, and minimum flow.
- The NFPA 13 ESFR report supports proposed NFPA 13 guideline changes for exposed nonexpanded Group A plastics and rubber tires at ceiling heights above 30 ft.
- The NFPA 13 ESFR report summarizes five full-scale fire tests with ceiling height, storage height, aisle width, ignition location, sprinkler K-factor, sprinkler pressure, activation timing/counts, temperature outputs, fire-spread outcomes, and acceptability.
- The NFPA 13 ESFR report states that ESFR water supplies are typically designed for 12 operating sprinklers and uses a lower activation-count threshold as part of its safety-factor evaluation.
- The NFPA 13 ESFR report's useful benchmark fields are storage arrangement, ceiling/storage height, sprinkler K-factor, discharge pressure or flow, activation count, gas/steel temperature evidence, horizontal spread outcome, target-array outcome, and acceptability.
- These FM reports materially improve the storage-sprinkler demand/report-artifact branch. They still do not supply processed water-flow requests, filled hydrant-flow forms, AHJ-approved calculation packs, full FM data sheets, or project-specific FM review responses.

## Fire Underwriters Survey Canada Branch

- FUS's Water Supply for Public Fire Protection guide is a public Canadian recommended-practice document for assessing water distribution adequacy and reliability for public fire protection.
- The guide separates community water-supply assessment from building required-fire-flow calculation and uses required fire flows in community risk and response-capacity evaluation.
- Its water-supply assessment includes delivery at required fire flow and duration during maximum-day demand, residual pressure, storage availability, pumping capacity, power/fuel reliability, and water-main/distribution reliability.
- The required-fire-flow branch uses construction type, effective floor area, occupancy/contents adjustment, automatic sprinkler protection adjustment, and exposure adjustment.
- FUS treats automatic sprinklers as significant private protection that can affect fire-flow/community-risk reasoning where systems meet relevant installation, maintenance, water-supply, and fire-department response conditions.
- The Hydrant Terms bulletin distinguishes public and private hydrants by ownership/maintenance/accessibility and warns that private hydrants may be unrecognized unless maintenance and operability are verified.
- The FUS downloads page exposes Water Supply Form (WS4) under outreach-program form downloads for updating basic water-supply details.
- The directly captured WS4 PDF is a one-page AcroForm titled "Fire Underwriters Survey Outreach - Water Supply Form (WS4)" and asks submitters to save/email the form back with attachments where specified.
- WS4 records province, region/county/district, municipality, date completed, water-system name, water-system type, contact name, contact email, and contact phone.
- WS4 Part A records water-system background questions: whether a servicing bylaw requires fire hydrants for all new developments and whether the Water Supply for Public Fire Protection Guide is referenced for required fire flows and hydrant coverage.
- WS4 asks for hydrant spacing standards for dwelling districts/zones and non-dwelling districts/zones such as industrial areas.
- WS4 asks whether all dwelling structures are within 300 m of a hydrant and whether all non-dwelling structures are within 150 m of a hydrant.
- WS4 records hydrant visual-inspection, full-teardown, and flow-testing frequencies.
- WS4 explicitly asks for flow-test results, hydrant maps, engineering reports, hydraulic-model results for fire flow plus maximum-day-demand conditions, and flow schematics when available.
- WS4 records whether the system has multiple pressure zones and asks for the number of pressure zones.
- WS4 records pump count and asks for pump capacities to be attached when pumps are used throughout the system.
- WS4 asks whether non-pressurized dry hydrants exist and asks for the hydrant map with the completed submission.
- This branch supports public-fire-flow and hydrant-recognition tasks; it is not a complete commercial sprinkler hydraulic-calculation standard.

## BSI Sprinkler Standard Metadata

- BSI lists BS EN 12845:2015+A2:2026 as current, published 30 Apr 2026.
- The BS EN 12845:2015+A2:2026 scope says it covers requirements and recommendations for design, installation, and maintenance of fixed fire sprinkler systems in buildings and industrial plants.
- The current EN 12845 metadata identifies hazard classification, water supplies, components, installation/testing, maintenance, and extension or modification of existing systems.
- BSI lists BS 9251:2021 as current, published 30 Jun 2021.
- The BS 9251:2021 page says it specifies design, installation, components, water supplies, backflow protection, commissioning, maintenance, and testing for domestic and residential sprinkler systems.
- The BS 9251:2021 page notes updates from 2014, including a fourth category for taller residential buildings or higher-risk scenarios, larger capacity minimum water supplies, duplicate pumps, reliability enhancements, non-residential occupancies in protected buildings, and information for fire-service interaction.
- BSI describes BS EN 12845 as setting minimum requirements for fixed fire sprinkler design, installation, and maintenance in buildings and industrial plants.
- The BSI page identifies hazard classification, water supply, hydraulic design criteria, pumps, pipe sizing/layout, valves, and alarms as topics.
- BSI describes BS 9251 as a domestic/residential sprinkler code of practice covering design, installation, components, water supplies, backflow protection, commissioning, maintenance, and testing.
- Earlier inspected BSI pages were withdrawn editions. They remain useful as history/metadata, but current task variants should cite the 2026 EN 12845 and 2021 BS 9251 pages where possible.

## Standards Australia Fire Metadata

- Standards Australia lists AS 2118.1:2017 as current, with the title "Automatic fire sprinkler systems, Part 1: General systems."
- The public AS 2118.1 payload says the standard specifies general requirements for design, installation, and commissioning of automatic fire sprinkler systems in buildings.
- The AS 2118.1 page lists latest version designation AS 2118.1:2017 Amd 3:2024, page count 457, and visible contents including classification of sprinkler systems and design data.
- Standards Australia lists AS 2419.1:2021 as current, with the title "Fire hydrant installations, Part 1: System design, installation and commissioning."
- The public AS 2419.1 payload says the standard specifies design, installation, commissioning, and testing requirements for fire hydrant installations used to protect buildings, structures, storage yards, marinas, wharves, and plant.
- Visible AS 2419.1 contents include system performance/design, hydrant classification/location/coverage, water sources and supply, water storage tanks, pumpsets, fire brigade booster assembly, and pipework design/installation.
- These pages improve Australian authority metadata, but do not expose the full detailed design criteria needed for deterministic grading.

## South East Water Street Hydrant Testing

- South East Water says Pressure and Flow Information (PFI) informs internal fire-service design and presents static and residual pressure in the relevant tapping main at different flow steps.
- The guidance says field hydrant tests may be needed when PFI is unavailable or to validate hydraulic-model PFI information.
- South East Water ties its approved field test method to AS 2419.1:2021 Appendix L Section L5.2.
- The method separates pressure and flow measurement: Hydrant A measures pressure and Hydrant B measures flow.
- Required equipment includes a pressure gauge or pressure-tapping cap for Hydrant A, plus standpipe, calibrated flow measuring device, flow-regulating valve, and diffuser for Hydrant B.
- The method records stabilized flow and pressure at increments such as 5, 10, 15, and 20 L/s, with safety, flushing, approval, and demobilisation steps.
- The guide warns not to exceed the maximum flow on the PFI statement and gives example maximum flow limits for cast iron/cement-lined mains.

## USFA Commercial Fire Sprinkler System Plans Review

- The USFA PDF is a United States Fire Administration student manual titled "Commercial Fire Sprinkler System Plans Review-Student Manual", with subject date May 2023, 562 pages, and open PDF access at the inspected URL.
- The manual frames plan review as evaluating fire sprinkler calculations against nationally recognized design and installation standards.
- The course scope explicitly includes water supplies, sprinkler components, remote areas, and hydraulic calculations.
- The manual uses sample submittal packages, water-flow test data, density/area curve exercises, adjusted remote-area exercises, and evaluation of supplied hydraulic calculations.
- It gives a useful verifier checklist shape: compare plans and calculations, verify remote-area shape/dimensions, check hydraulic reference points/nodes, validate sprinkler data, verify pressure losses, check hose-stream treatment, and validate water supplies from calculation and water-supply data.
- This is strong public review-workflow evidence. It is not a substitute for licensed NFPA text or an AHJ-approved project package.

## San Francisco Fire Department Sprinkler Submittals

- SFFD Administrative Bulletin 2.04 is available as a current 2025 PDF and as an HTML page.
- The bulletin is an AHJ submittal checklist for installing or modifying sprinkler systems and references the locally adopted building/fire codes and NFPA 13/13R/13D basis.
- It requires current water-flow information from SFFD and says water-flow test information is valid for a maximum of 12 months from test date to permit application date.
- The submittal package includes stamped drawings/calculations, manufacturer specification sheets, processed water-flow request form, and sufficient architectural/mechanical reference plans where applicable.
- Water-source details include city-main size, dead-end or circulating status, direction/distance to circulating main, system elevation relative to test hydrant, and other water supplies with pressure or elevation.
- Supporting hydraulic artifacts include backflow preventer friction loss graph, fire pump curve, hydraulic calculations, supply/demand curve graph, matching hydraulic reference points, highlighted remote area, minimum density, design area, in-rack demand, hose-stream demand, and total water/pressure at a common reference point.
- The bulletin also records AHJ-specific branch logic, such as when modifications require new hydraulic calculations, parking-garage OH2 handling, EV/power-wall conditions, exposure sprinkler flow, and booster-pump use for some 13D cases.

## Mason County And GMU Submittal Checklists

- Mason County Fire Marshal's August 2023 standard gives a compact NFPA 13/13R plan-submittal checklist with designer certification, plan fields, system type, code edition, pipe/fitting/valve fields, backflow assembly, and inspection requirements.
- Mason County requires hydraulic data nameplate information for hydraulically designed systems, plan reference points that correspond to calculation-sheet reference points, density/flow/discharge pressure, design area, in-rack and hose-stream demand, total water and pressure at a common reference point, and current purveyor waterflow information.
- Mason County states that if waterflow information is not current, a flow test conforming to NFPA 291 must be performed by an approved firm or individual.
- GMU OUBO's January 2025 shop-submission guideline requires plans, equipment specification sheets, and hydraulic calculations in the permit package.
- GMU requires water-supply information including static pressure, residual pressure, flow, test date, test organization, and accepted hydrant locations; design-review fire-flow testing must be no more than 12 months old.
- GMU requires a water-supply graph on semi-log paper with actual water-flow information and a distinguishable safety-factor reduction curve where applicable.
- GMU's drawing checklist is useful for multimodal extraction: owner certificate, site plan, ceiling construction, cross-section, walls/partitions, room occupancy, water-main size, alternate/additional water supply, sprinkler orifice/temperature fields, pipe materials, underground pipe fields, design criteria, and FDC/pressure-device fields.

## HFSC Residential NFPA 13D Branch

- HFSC identifies NFPA 13D as the national installation standard for one- and two-family dwellings and manufactured homes.
- HFSC frames the 13D objective around life safety and early fire control, including a minimum water-duration concept for the initial fire stage.
- The NFPA 13D orientation page says local building authorities may impose requirements beyond 13D, so residential tasks need an explicit local-authority field.
- HFSC identifies two common residential layout families: stand-alone/independent and multipurpose/combined systems.
- The residential water-supply page describes a typical stand-alone system supplied from the household water main through a riser with pressure gauge, flow switch, backflow valve where required, and test/drain assembly.
- HFSC notes that backflow prevention devices and water meters reduce available pressure, which can drive larger taps and meters.
- This supports a residential source-pack branch separate from commercial NFPA 13/13R AHJ review packets.

## Australian NCC And NSW Regional Branches

- NCC 2022 Specification 17 publicly exposes a regional branching structure for automatic sprinkler systems in Australia, including AS 2118.1, AS 2118.4, AS 2118.6, FPAA101D/H limitations, building class, carpark conditions, and warning-system connections.
- The NCC page explains that AS 2118.1 applies broadly, AS 2118.4 is used for low-rise residential-type building classes as applicable, and AS 2118.6 applies to combined sprinkler and hydrant systems.
- The NSW Fire Sprinkler Standard is an older state source but remains useful for regional artifact shape. It separates deemed-to-satisfy compliance from alternative solution routes and requires fire-safety-engineer certificates or reports for alternative solutions.
- The NSW standard records AS 2118.4 and AS 2118.6 edition handling, residential sprinkler requirements when resident areas are served by AS 2118.1/2118.6 designs, monitored stop valves, and Fire and Rescue NSW alarm-monitoring connection.
- These Australian sources strengthen branch logic and approval artifacts, but detailed hydraulic criteria still need Standards Australia access or task-provided excerpts.

## Sample Sprinkler Hydraulic Calculation Report

- The SCI-HYDRAULIC CALCULATIONS-2 sample report shows the common document chain: sprinkler plan, spacing plan, hydraulic calculations, descriptive report, metric calculations, and technical report.
- The report says software hydraulic runs divide the network into nodes/references, with pipe material/schedule, diameter, fittings/accessories, length, Hazen-Williams coefficient, and elevation change between nodes.
- The sample scenario uses the hydraulically remote sprinklers, K-factor, minimum sprinkler pressure, water reserve duration, sprinkler coverage, pump pressure/flow, and available versus required pressure.
- The output sheets include sprinkler reference point, K-factor, elevation, flow, pressure, static pressure, residual pressure, total system flow, available pressure, operating pressure, pressure remaining, equivalent fitting length, Hazen-Williams coefficient, pipe diameter, friction, elevation, and pressure differences.
- This is a strong output-shape artifact, but the source should be treated as an example report rather than an official AHJ-approved or standards-published worked example.

## Targeted Search Dead End

- Generic public search for filled hydrant-flow-test forms, official fire-flow-test reports, AHJ-approved sprinkler hydraulic calculations, and EPANET fire-flow fixtures did not produce a clean reusable accepted-project artifact.
- Follow-up inspection of the official USEPA WNTR route did produce a redistributable open modelling fixture path with network files, fire-flow examples, and small output CSVs. Later raw-file and GitHub API inspections pinned the source commit, latest release context, license route, file sizes, hashes, CSV row counts, nonzero keys, and aggregate totals; a temporary WNTR 1.4.0 run then reproduced both CSV outputs exactly. Treat this as strong open-model fixture evidence, not as accepted project evidence.
- Targeted AHJ/owner routes did produce useful submittal checklists from SFFD, Mason County, and GMU, but those are mostly required-field and review-process artifacts rather than filled calculations.
- FM, FUS, and HFSC routes improved review-authority and regional branch evidence, but they still did not recover accepted commercial hydraulic calculations, filled water-flow request forms, or anonymized hydrant-flow reports.
- FM code-support report inspection did recover public EN 12845 and NFPA 13 sprinkler-demand research reports with test tables, figures, criteria, and recommendations. This narrows the FM gap from "no specific FM report route" to "specific public report route found, but full data sheets and filled project review artifacts still missing."
- Some candidate public routes were blocked, stale, or unusable in this pass, including WSSC Cloudflare-blocked access and candidate municipal PDF links that returned 404 or empty content.
- The FUS downloads page and direct PDF route now expose the blank WS4 form content. The unresolved FUS gap is filled submissions and the attachment bundle: flow-test results, hydrant maps, engineering reports, hydraulic-model fire-flow plus maximum-day-demand results, flow schematics, pressure-zone detail, pump capacities, and dry-hydrant maps.
- Direct FM data-sheet fetching from this environment returned a Cloudflare block page, so specific FM sprinkler data sheets or worked review examples remain uncaptured.
- This is not evidence that accepted artifacts do not exist. It means the next pass should use specific utility/AHJ portals, municipal permit records, FOI/open-data paths, vendor sample submittal packs, or licensed standards/worked-example material rather than generic web search.

## Source Quality Note

- The chain is confident from practice and now has clearer US AHJ-review evidence, federal training/review evidence, current UK/EU metadata, Australian metadata, open water-network modelling, utility hydrant-testing, and sample hydraulic-report evidence. Detailed sprinkler criteria still must come from an explicit code/AHJ basis supplied in the task or from licensed/public-view standard access.
