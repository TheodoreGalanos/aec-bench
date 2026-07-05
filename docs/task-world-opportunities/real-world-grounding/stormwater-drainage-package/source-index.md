# ABOUTME: Source index for grounding the stormwater drainage composite template.
# ABOUTME: Records real standards, manuals, artifacts, and regional differences for later task design.

# Stormwater Drainage Package Source Index

## Current Chain Confidence

The current chain is well supported by public engineering guidance:

catchment/rainfall evidence -> peak runoff -> detention storage -> outlet control -> pipe/conveyance/HGL -> outfall/tailwater/freeboard compliance memo.

The strongest evidence is from FHWA HEC-22 and EPA SWMM. HEC-22 covers peak-flow estimation, storm-drain design, HGL/outfall evaluation, detention, and outlet devices. EPA SWMM confirms the richer real-world version: subcatchments, rainfall, drainage network routing, storage, pumps, weirs, orifices, outfalls, and reporting. The EPA SWMM Applications Manual zip now closes a major fixture gap by exposing worked example `.inp` files, site images, and a rainfall record.

The current hardening pass promotes Example 3, "Detention Pond Design," into a docs-only source-pack plan under `swmm_example3_detention_source_pack/`. It pins the official EPA zip hash, nested `files.zip` hash, `Example3.inp`/`.ini`/`Site-Post.jpg` hashes, parsed model section counts, storage/orifice/weir rows, manual design targets, expected answer shape, future verifier rules, negative verification cases, and a verifier implementation brief. This moves stormwater from broad fixture discovery to a concrete executable-fixture contract, while preserving the boundary that no EPA files are vendored here, no SWMM report-output evidence has been generated in this checkout, and no municipal approval package has been captured.

## Sources

| Source | Type | Region | Relevance |
| --- | --- | --- | --- |
| FHWA HEC-22, *Urban Drainage Design Manual*, 3rd ed., archived PDF. https://www.fhwa.dot.gov/engineering/hydraulics/pubs/10009/10009.pdf | government-manual | US | End-to-end urban drainage design. It covers Rational Method peak flows, storm-drain HGL, outfalls/tailwater, detention, and orifice/weir outlet structures. Superseded by a 2024 edition, so use as accessible evidence while locating current HEC-22. |
| US EPA, Storm Water Management Model (SWMM). https://www.epa.gov/water-research/storm-water-management-model-swmm | primary-open | US/global | Confirms real modelling inputs/outputs: subcatchments, rainfall, conduits, storage units, pumps, weirs, orifices, outfalls, profile plots, time-series graphs, and tabular results. |
| US EPA, SWMM Applications Manual zip. https://www.epa.gov/sites/default/files/2014-05/epaswmm5_apps_manual.zip | primary-open worked examples and model files | US/global | Contains the SWMM Applications Manual PDF plus `files.zip` with Example1-9 `.inp` model files, `.ini` files, `Record.dat`, and site images. Strong fixture source for pre/post development runoff, hydraulic routing, detention pond design, LID controls, water quality, dual drainage, combined sewer regulators, and continuous simulation. |
| Local docs-only SWMM Example 3 source-pack plan. `swmm_example3_detention_source_pack/` | local research packet | US/global | Converts EPA Example 3 into a future benchmark fixture contract: source hashes, selected files, model options, object counts, storage curve, outlet structure, manual target values, expected output, verifier rules, negative cases, source-boundary mismatches, and a verifier implementation brief for future report-output checks. |
| USEPA Stormwater-Management-Model repository. https://github.com/USEPA/Stormwater-Management-Model | primary-open/tool | US/global | Official EPA SWMM solver repository with source, documentation, and tests. Useful for solver authority and model I/O expectations, but current inspection did not find obvious reusable `.inp` example fixtures. |
| USEPA SWMM unit-testing note. https://github.com/USEPA/Stormwater-Management-Model/blob/develop/tests/Unit_Testing.md | primary-open/tooling-note | US/global | Describes Windows build/unit-test dependencies and `tools\make.cmd /t`; it does not provide hydrology/hydraulic `.inp` example models. |
| Australian Rainfall and Runoff. https://arr.ga.gov.au/ | primary-open/primary-gated mix | Australia | Regional hydrology authority for Australian rainfall-runoff practice. The public site identifies ARR 2019 as a national guideline, data, and software suite for design flood characteristics. |
| ARR Guidebook and Book 9, Runoff in Urban Areas, v4.2. https://www.arr-software.org/arrdocs.html and https://www.arr-software.org/pdfs/ARR_190514_Book9_V4.2.pdf | primary-open regional guidebook | Australia | Public guidebook download page and urban-runoff book. Book 9 strengthens Australian urban stormwater branch evidence: urban water cycle framing, volume management, conveyance, minor/major systems, data/model dependence, and urban modelling process. |
| ARR Data Hub. https://data.arr-software.org/ | primary-open data portal | Australia | Public data hub fields include river region, ARF parameters, storm losses, temporal patterns, area temporal patterns, BOM IFD depths, preburst depths/ratios, and climate change factors. Useful source-pack surface for Australian design-rainfall inputs. |
| Bureau of Meteorology IFD Data System. https://www.bom.gov.au/water/designRainfalls/revised-ifd/?year=2016 | primary-open data portal | Australia | Public design rainfall system for single-point, multi-point, and extent-based IFD requests. The page states the 2016 design rainfalls use expanded station data and replace ARR87 and interim 2013 IFDs. |
| USGS SELDM support/source. https://www.usgs.gov/software/stochastic-empirical-loading-and-dilution-model-seldm | primary-open | US | Relevant to highway stormwater quality/load outputs, not the core hydraulic chain. Useful if pollutant-load stages are composed later. |
| Caltrans Highway Design Manual. https://dot.ca.gov/programs/design/manual-highway-design-manual-hdm | government-manual | US/California | Current public drainage chapters include hydrology, cross drainage, transportation-facility drainage, open channels, bank protection, and stormwater management. |

## Real Inputs

- Catchment plan or GIS layer: subcatchment areas, impervious fraction, slope, flow path.
- Rainfall source: IDF table, design storm, hyetograph, climate-change factor.
- Drainage network: pipe schedule, inlets/pits, invert levels, pipe diameter, roughness, grade.
- Detention geometry: basin/pond/storage curve, permissible water levels, freeboard.
- Outlet structure: orifice/weir dimensions, discharge coefficients, control branch.
- Tailwater/outfall: receiving-water level, critical depth, outlet invert, erosion protection.
- SWMM model package: `.inp` model file, `.ini` view/config file, rainfall time-series file, site/backdrop images, and report/output settings.
- Australian source-pack data: ARR/BOM design rainfall, temporal pattern, storm losses, climate-change factor, catchment model assumptions, minor/major drainage path, and receiving-water constraints.

## Real Outputs

- Peak runoff or hydrograph at nodes/subcatchments.
- Detention volume and stage-storage-discharge relationship.
- Outlet rating curve and controlled discharge.
- Pipe velocity, capacity, surcharge status, HGL/EGL profile.
- Outfall/tailwater/freeboard compliance statement.
- Drawings/tables: drainage long section, pit schedule, detention outlet detail, calculation report.
- SWMM report outputs: runoff summary, node/link flow and depth results, profile plots, time-series tables, continuity checks, LID summaries, storage depth/inflow/outflow, and comparative pre/post development discharge results.

## Regional Differences To Track

- US practice often references FHWA HEC/HDS manuals, NOAA Atlas rainfall, and SWMM for model-based drainage.
- Australian practice should reference Australian Rainfall and Runoff, ARR Data Hub/BOM IFD design rainfall, local council drainage manuals, and state water-sensitive urban design guidance.
- UK/EU practice may use Sewers for Adoption, CIRIA SuDS manuals, Eurocodes for structures, and local LLFA requirements.

## Task Implications

- The current formula chain is directionally correct.
- The richer benchmark should represent both scalar and model-based paths: Rational Method/simple detention versus SWMM-style network routing.
- The key branch decisions are rainfall event/return period, runoff method, outlet control, tailwater basis, pipe-flow regime, and HGL acceptance threshold.
- Verifier should check source provenance and handoff continuity, not just final numbers.
- The EPA Example 3 detention packet now gives a realistic executable fixture path with explicit expected outputs and provenance notes. Benchmark-ready instances still need runtime packaging, approved source-file inclusion/download policy, and an executable SWMM/report parser or equivalent source-pack verifier. A temporary `swmm-toolkit` route did not produce report evidence because native solver/output binding imports exited without traceback in this environment.
