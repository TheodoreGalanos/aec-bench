# ABOUTME: Analysis for grounding the stormwater drainage composite template.
# ABOUTME: Maps real workflow expectations to current task chain, verifier needs, and gaps.

# Stormwater Drainage Package Analysis

## Real Workflow Chain

Real stormwater design is not just a calculation chain; it is a source-controlled design package. The designer usually starts from survey, catchment plans, rainfall data, road/civil grading, local drainage criteria, and receiving-water constraints. They then establish design events, convert catchments to peak flows or hydrographs, size detention and outlets where required, route flows through pipes/open channels, evaluate HGL/EGL and tailwater, and issue a calculation memo plus drawings or model outputs.

The EPA SWMM Applications Manual makes the executable version concrete. It includes sequential worked examples and `.inp` model files that move from pre/post development runoff to surface drainage hydraulics, detention pond design, LID controls, treatment, dual drainage, combined sewer regulators, and continuous simulation. For benchmark purposes, this gives a credible source-pack spine: model file, site image, rainfall record, design objective, run outputs, and interpretation.

ARR Book 9 sharpens the Australian branch. It makes urban runoff a linked water-cycle and urban-planning problem with volume management, conveyance, minor/major drainage, model selection, and stormwater-quality/resource considerations. The ARR Data Hub and BOM IFD system also expose the kind of source provenance an Australian benchmark must carry.

The Example 3 hardening pass narrows the executable path further. The selected EPA fixture is a detention-pond design with `Example3.inp`, `Example3.ini`, and `Site-Post.jpg` as the source-file spine. It has 7 subcatchments, 12 junctions, 12 conduits, 1 storage unit, 3 side orifices, 1 transverse weir, 72 rainfall time-series rows, a tabular storage curve, and manual targets for WQCV drawdown plus 2-year, 10-year, and 100-year release control. This is enough to specify a source-pack verifier contract without needing private data, though it still remains a teaching example rather than an accepted project report. Dynamic report-output checks remain open because the temporary local SWMM toolkit route failed at native binding import.

## Chain Check Against Template

| Template Stage | Real-world equivalent | Confidence |
| --- | --- | --- |
| Hydrology | Catchment delineation plus rainfall-runoff method. | High |
| Detention | Storage and discharge control, often via stage-storage-discharge curves. | High |
| Outlet | Orifice/weir/pipe outlet control, with free/submerged branch. | High |
| Conveyance | Pipe/channel capacity, velocity, headloss, HGL profile. | High |
| Compliance | Freeboard, tailwater, flood/surcharge, and authority criteria. | High |
| Executable model | SWMM `.inp` package with subcatchments, rainfall, nodes, links, storage, controls, output sections, and optional site images/records. | High |

## Real Inputs

Inputs should include a source pack rather than direct scalar values: catchment plan, IDF/design storm, network long section, detention geometry, outlet detail, tailwater basis, and optionally an executable SWMM `.inp` package. For Australia, the source pack should also identify ARR/BOM data provenance, temporal patterns, storm losses, and climate-change factors where applicable.

## Real Outputs

Outputs should be staged: hydrology table, detention sizing table, outlet rating, pipe/HGL table, model run report, continuity checks, node/link summaries, hydrographs/profile plots, compliance memo, and machine-readable handoff ledger.

## Harness Implications

- Check that rainfall event and rainfall source are consistent across hydrology and detention.
- Check catchment areas and imperviousness against source artifact IDs.
- Check `peak_runoff_m3_s` flows into detention and conveyance unchanged unless explicitly routed.
- Check outlet branch: orifice, weir, compound, or pipe/tailwater controlled.
- Check HGL starts from tailwater/outfall basis and moves through the network.
- Check final memo records unresolved data gaps such as climate factors, survey uncertainty, and tailwater data.
- For SWMM-backed tasks, check that the model sections used by the answer exist in the `.inp`, that the cited output came from the relevant run/report, and that pre/post development or controlled/uncontrolled comparisons use the correct scenario files.
- For ARR-backed tasks, check that the rainfall source, temporal pattern, losses, and climate factor are traceable to the source pack rather than invented or mixed across regions.
- For the Example 3 detention fixture, check EPA source hashes, `Example3.inp` object counts, storage curve points, orifice/weir rows, WQCV and peak-release target values, and answer disclosure of the known manual/model mismatches around time-step settings and area rounding.
- When a controlled SWMM engine is available, extend checks to generated report-output evidence: runoff continuity, flow-routing continuity, node flooding/surcharge status, `SU1`/`J_out` node summaries, `Or1`/`Or2`/`Or3`/`W1`/`C11`/`C_out` link summaries, engine warnings, and binary-output time series if in scope.

## Multimodal Extension

- Inputs: catchment plan, drainage long section, pit/pipe schedule, detention outlet detail, rainfall table, SWMM model file, SWMM status report, site/backdrop image, and ARR/BOM rainfall extract.
- Outputs: annotated catchment plan, extracted network table, stage-storage-discharge curve, HGL profile, hydrograph comparison, model-output reconciliation, and compliance memo.
- Interesting checks: catchment area extraction, chainage/invert consistency, outlet-control branch detection, storage curve interpretation, manual-target reconciliation, source-boundary disclosure, model-output reconciliation, and whether visual site/catchment evidence matches SWMM object IDs.

## Meta-Harness Opportunities

- Reconfigure method: Rational Method, hydrograph routing, SWMM model, ARR-based Australian workflow.
- Mutate rainfall event, climate factor, tailwater, outlet geometry, imperviousness, and freeboard criteria.
- Combine with road alignment by passing low points and catchments into drainage.
- Combine with pump-station tasks when gravity outfall is constrained.
- Compose an executable-model repair task where the meta-harness changes outlet geometry, rainfall, or catchment imperviousness, re-runs/compares expected reports, and emits a design memo.

## Remaining Gaps

- Need current HEC-22 4th edition public access or metadata; the accessible FHWA PDF is archived.
- Need deeper Australian state/local drainage manuals and worked council examples, even though ARR Book 9/Data Hub/BOM IFD now strengthen national rainfall/runoff evidence.
- Need real public stormwater calculation reports with enough open content to model deliverable structure.
- Need to convert the docs-only `swmm_example3_detention_source_pack/` contract into runtime packaging when task changes are allowed: approved source-file inclusion or download policy, a controlled SWMM engine path, executable SWMM/report parsing, and generated acceptance artifacts.
