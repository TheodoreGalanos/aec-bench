# ABOUTME: Short extracted notes for stormwater drainage sources.
# ABOUTME: Keeps source-bounded observations without copying full standards or manuals.

# Stormwater Scraped Notes

## FHWA HEC-22

- The accessible FHWA HEC-22 PDF is the 3rd edition and marks itself as superseded by the 4th edition in February 2024.
- HEC-22 includes Rational Method material and notes that IDF curves are needed to use it.
- HEC-22 defines HGL as the water level/pressure head line used to judge storm-drain acceptability.
- HEC-22 says HGL evaluation starts at the outfall with the tailwater elevation or a critical-depth/crown basis.
- Detention is framed as limiting peak outflow relative to pre-development conditions for selected flood frequencies.
- Orifice outlet design includes discharge coefficient, orifice area, effective head, and free/submerged discharge branches.

## EPA SWMM

- SWMM is used for planning, analysis, design, and emergency response for stormwater, combined, and sanitary drainage systems.
- Public EPA documentation lists manuals for hydrology, hydraulics, water quality, applications, and the user manual.
- SWMM outputs include maps, time-series graphs/tables, profile plots, and statistical frequency analyses.
- Hydraulic elements include conduits, channels, storage/treatment units, pumps, weirs, orifices, and outfalls.

## EPA SWMM Applications Manual And Example Files

- EPA's SWMM page lists the SWMM Applications Manual zip under Manuals and Guides. The inspected URL redirects to `https://www.epa.gov/sites/default/files/2014-05/epaswmm5_apps_manual.zip`.
- The zip contains `Swmm_Apps_Manual.pdf` and a nested `files.zip`.
- The nested example bundle contains `.inp` and `.ini` files for Example 1 through Example 9, plus `Record.dat` and site images (`Site-Pre.jpg`, `Site-Post.jpg`, and `Site-Post-LID.jpg`).
- The manual is a 180-page worked-example document. Its introduction says it contains nine worked examples for hydrology, hydraulics, multi-purpose detention pond design, LID controls, water quality, runoff treatment, dual drainage systems, combined sewer systems, and continuous simulation.
- Example 1 compares pre-development and post-development runoff. The associated files include `Example1-Pre.inp` and `Example1-Post.inp`.
- Example 2 adds a surface conveyance system and compares hydraulic routing methods. The associated post-development file includes subcatchments, junctions, outfalls, conduits, time series, and report settings.
- Example 3 designs a detention pond and outlet structure using storage units, orifices, and weirs to control post-development peak release rates. The associated `Example3.inp` includes `[STORAGE]`, `[ORIFICES]`, `[WEIRS]`, `[CURVES]`, `[TIMESERIES]`, and reporting sections.
- Example 4 adds filter-strip and infiltration-trench LID controls; `Example4.inp` includes LID-related model sections and uses the post-development site/LID image context.
- Example 6 combines LIDs and a detention pond with treatment logic; `Example6-Final.inp` includes storage, orifice, weir, curve, timeseries, and report sections.
- Example 7 builds a dual drainage system. Example 8 extends the task into combined sewer regulators using weirs, orifices, pipes, and a hypothetical treatment-plant outfall. Example 9 converts the detention pond case into continuous simulation using a rainfall record.
- This source family materially improves fixture readiness because it includes executable `.inp` files and real model-file structure. It is still a teaching/example package rather than a public authority-approved project report.

## EPA SWMM Example 3 Detention Hardening Pass

- The official Applications Manual zip inspected for this pass has SHA-256 `889dd60a53ac85f00ee90db947a67ddc6d0737f46acf818bf7c7c08ac272f0ea`; the nested `files.zip` has SHA-256 `99ef5eb1ec7995fa2db3cc797d75080ab26843a7b523e2bc227717e2d047c9a8`; and `Swmm_Apps_Manual.pdf` has SHA-256 `c40f7afea62b8b8b5d97b337e56db19320cfe478354b5e99c8618568b6da5feb`.
- The selected source files are `Example3.inp` (`ece140eda259a9e68631a7c9d25d5060f9b3e69f133aec308d19ad339c9b0a1a`), `Example3.ini` (`9241ec0d997c0c291a5d192775e654e215093249b9bb28740a9a2ebb83616432`), and `Site-Post.jpg` (`a1effb2859ed2c693cb8143cb431dd2b0ea5d081156ab9f5e7ef0a0da06a44a3`).
- `Example3.inp` uses CFS units, Horton infiltration, Dynamic Wave routing, a 2007-01-01 to 2007-01-04 run window, 1-minute report and wet steps, a 1-hour dry step, and a 15-second routing step.
- The parsed model has 7 subcatchments, 12 junctions, 1 outfall, 1 storage unit, 12 conduits, 3 orifices, 1 weir, 16 xsection rows, 4 storage-curve points, 72 rainfall time-series rows, 14 coordinates, 26 vertices, 145 polygon coordinate rows, and 1 backdrop reference.
- The storage unit `SU1` has invert 4956 ft, maximum depth 6 ft, and tabular storage-curve points `(0, 14706)`, `(2.22, 19659)`, `(2.3, 39317)`, and `(6, 52644)`.
- The final staged outlet structure is `Or1` at 0 ft offset with 0.3 ft by 0.25 ft rectangular opening, `Or2` at 1.5 ft offset with 0.5 ft by 2 ft opening, `Or3` at 2.22 ft offset with 0.25 ft by 0.35 ft opening, and transverse weir `W1` at 3.17 ft offset with 2.83 ft height and 1.75 ft width.
- The manual target table gives 2-year, 10-year, and 100-year pre-development peak releases of 4.14, 7.34, and 31.6 cfs, with uncontrolled post-development peaks of 33.5, 62.3, and 163.8 cfs.
- The manual reports WQCV depth 0.23 in, WQCV volume 24,162 ft3, and final `Or1` drainage time 40:12 hr:min; final controlled peaks are 4.11 cfs, 7.32 cfs, and 31.2 cfs for the 2-year, 10-year, and 100-year storms, respectively.
- Two source-boundary mismatches should be preserved in verifier work: the manual narrative says final comparison runs used 15-second report/wet/routing steps while `Example3.inp` uses 1-minute report and wet steps with 15-second routing; and the manual uses 28.94 acres for WQCV arithmetic while rounded `Example3.inp` subcatchment rows sum to 28.92 acres.
- The local docs-only packet `swmm_example3_detention_source_pack/` records these findings as a source manifest, model summary, expected output, verifier rules, verification cases, and verifier implementation brief. It does not include EPA source files or executable verifier code.
- A temporary `swmm-toolkit` route was attempted for generated report-output evidence. `swmm.toolkit` imported and package metadata showed version `0.17.0`, but native `swmm.toolkit.solver` and `swmm.toolkit.output` imports exited with code 1 and no Python traceback; no local `swmm5` or `runswmm` binary was available. Therefore continuity summaries, node/link summary rows, and binary-output time series remain ungenerated in this pass.

## USEPA SWMM GitHub Repository

- The repository identifies itself as the official SWMM source-code repository maintained by US EPA Office of Research and Development.
- The readme describes SWMM as a dynamic hydrology-hydraulic water quality simulation model for stormwater, wastewater, and combined sewer collection systems.
- The repository includes a `tests` folder and `outfile` folder, making it a useful place to find solver and report conventions.
- A GitHub API tree inspection found no `.inp` files in the official solver repository. It did find `tests/outfile/data/Example1.out`, which is useful as output/report convention evidence but not a full hydrology/hydraulic input model.
- `tests/Unit_Testing.md` documents Windows build dependencies and running `tools\make.cmd /t`; it is useful for solver development context but not for benchmark source-pack fixtures.
- Implication: official SWMM is strong authority for executable model semantics; the EPA Applications Manual zip is the better EPA-owned source for reusable example `.inp` fixtures.

## Australian Rainfall And Runoff

- ARR's public home page identifies ARR as a national guideline document, data, and software suite for estimating design flood characteristics in Australia.
- The public ARR guideline page says ARR 2019 consists of the guideline, software, and data, and links to guidebook downloads, software, design rainfalls, and the ARR Data Hub.
- The ARR documents page exposes version 4.2 PDFs and individual books, including Book 3 Peak Flow Estimation, Book 6 Flood Hydraulics, and Book 9 Runoff in Urban Areas.
- ARR Book 9 v4.2 is a 237-page public PDF. Its inspected text frames modern urban runoff as a linked urban water-cycle problem rather than only pipe conveyance.
- Book 9 identifies volume management and conveyance systems, minor and major drainage philosophy, data/model dependence, and urban modelling as key parts of urban stormwater design.
- The ARR Data Hub public page exposes source-pack fields such as river region, ARF parameters, storm losses, temporal patterns, area temporal patterns, BOM IFD depths, preburst depths/ratios, and climate change factors.
- BOM's IFD Data System exposes single-point, multiple-point, and extent-based design rainfall request modes. Its public page states that the 2016 IFDs use expanded rainfall data and replace ARR87 and interim 2013 IFDs.
- These sources strengthen Australian regional variants, especially rainfall-source provenance and urban-runoff modelling assumptions. They do not by themselves provide a complete council-approved drainage report or SWMM/MUSIC project model.
