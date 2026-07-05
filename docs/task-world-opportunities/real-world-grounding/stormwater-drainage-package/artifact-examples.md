# ABOUTME: Real and near-real artifact examples for stormwater drainage task grounding.
# ABOUTME: Identifies public inputs, outputs, reports, and fixture candidates for benchmark design.

# Stormwater Drainage Artifact Examples

## Public Artifacts Found

| Artifact | Source | Input/Output Shape | Benchmark Use |
| --- | --- | --- | --- |
| EPA SWMM official source repository | https://github.com/USEPA/Stormwater-Management-Model | Solver source, docs, tests, and output-test folder. Current inspection did not expose obvious reusable `.inp` example files. | Anchor for solver semantics and report conventions; not sufficient by itself for benchmark source-pack fixtures. |
| EPA SWMM unit-testing note | https://github.com/USEPA/Stormwater-Management-Model/blob/develop/tests/Unit_Testing.md | Windows build/test dependencies and `tools\make.cmd /t` workflow. | Tooling evidence only; helps classify the official repo as solver authority rather than example-project source. |
| EPA SWMM official page/manuals | https://www.epa.gov/water-research/storm-water-management-model-swmm | Manuals, downloads, model capability descriptions. | Source of supported object types and workflow chain. |
| EPA SWMM Applications Manual zip | https://www.epa.gov/sites/default/files/2014-05/epaswmm5_apps_manual.zip | Official worked-example bundle with `Swmm_Apps_Manual.pdf`, Example1-9 `.inp` files, `.ini` files, rainfall record, and site images. Examples include pre/post runoff, surface hydraulics, detention pond with storage/orifice/weir controls, LID controls, treatment, dual drainage, combined sewer regulators, and continuous simulation. | Strong executable fixture source. Candidate basis for model-reading, model-repair, report-reconciliation, and multimodal site-image/source-pack tasks. |
| Local SWMM Example 3 detention source-pack plan | `swmm_example3_detention_source_pack/source-pack-plan.md`, `source-manifest.yaml`, `model-summary.yaml`, `expected-output.md`, `verification-rules.yaml`, `verification-cases.yaml`, `verifier-implementation-brief.md` | Docs-only local packet pinned to EPA Example 3. It records the outer EPA zip hash, nested `files.zip` hash, selected `Example3.inp`/`.ini`/`Site-Post.jpg` hashes, model options, object counts, storage curve, outlet structure, manual target values, known manual/model mismatches, expected design-check memo shape, future verifier rules, negative cases, report-output verifier stages, and the failed local native-toolkit route. | Strongest current stormwater fixture contract. It is ready to drive future runtime/source-pack implementation, subject to source-file inclusion policy, controlled SWMM engine availability, and executable verifier work. |
| FHWA HEC-22 Urban Drainage Design Manual | https://www.fhwa.dot.gov/engineering/hydraulics/pubs/10009/10009.pdf | Design equations, hydraulic structure checks, drainage design procedure. | Source for deterministic calculation subchains and verifier checks. |
| Australian Rainfall and Runoff | https://arr.ga.gov.au/ | Regional hydrology guidance and data portal entry point. | Regional reconfiguration source for Australian hydrology variants. |
| ARR Book 9 and data tools | https://www.arr-software.org/pdfs/ARR_190514_Book9_V4.2.pdf, https://data.arr-software.org/, https://www.bom.gov.au/water/designRainfalls/revised-ifd/?year=2016 | Public urban-runoff guidebook plus rainfall/data surfaces for river region, ARF, storm losses, temporal patterns, area temporal patterns, BOM IFD depths, preburst, and climate factors. | Strong Australian regional source-pack path for rainfall provenance and urban-runoff modelling assumptions. |

## Fixture Candidates

- EPA SWMM Applications Manual Example 3, with `Example3.inp`, `Example3.ini`, `Site-Post.jpg`, official zip hashes, selected model summary, expected output table, and source-boundary mismatch notes.
- SWMM `.inp` model with subcatchments, rain gage, junctions, conduits, storage, outfall, regulator, and report settings.
- HEC-22 culvert/orifice/weir calculation sheet.
- Drainage plan/profile PDF with pits, pipes, invert levels, catchments, and outfalls.
- ARR-style rainfall intensity/source data plus a small catchment delineation.
- Australian ARR/BOM source pack with coordinates/extent, IFD, storm losses, temporal patterns, climate factor, catchment assumptions, and local council acceptance criteria.

## Remaining Artifact Need

- Runtime-packaged version of the docs-only Example 3 source-pack contract, including either approved vendored source files or deterministic official-download verification plus controlled SWMM execution, report parsing, continuity checks, node/link summaries, and optional binary-output checks.
- Public drainage design report with plan/profile and calculation appendix.
- Regional Australian worked examples with ARR rainfall and pit/pipe sizing.
