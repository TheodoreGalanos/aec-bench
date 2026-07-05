# ABOUTME: Analysis for grounding the civil-ground retaining interface in real workflows.
# ABOUTME: Summarizes workflow chain, inputs, outputs, benchmark implications, and multimodal scope.

# Civil Ground Retaining Interface Analysis

## Real Workflow Chain

The chain is realistic:

survey and civil geometry -> ground investigation and groundwater model -> interpreted soil parameters -> wall type and load cases -> lateral earth pressures -> global and external stability -> bearing/settlement -> drainage and durability -> civil/ground interface memo.

The key realism point is that the "calculation" is not just active earth pressure. Real retaining design is an interface negotiation between civil geometry, geotechnical uncertainty, groundwater/drainage, construction staging, and structural wall capacity.

The stronger framing is wall-family selection plus evidence traceability. A WSDOT-style owner workflow asks whether the wall exists because of right-of-way, wetlands, widening, abutment modification, adjacent assets, or construction staging. FHWA then gives different source chains for MSE/RSS, soil nail, and anchored soldier-beam/lagging systems. That means a benchmark should not force every retaining problem through the same active-pressure formula; it should make the model identify the wall family, the evidence required for that family, and the checks that follow.

## Real Inputs

- Site survey, wall alignment, retained height, excavation/fill sequence, nearby assets, and surcharge loads.
- Borehole logs, lab results, groundwater observations, and interpreted design parameters.
- Wall type: gravity, cantilever, embedded pile, anchored, MSE/RSS, soil nail, gabion, or proprietary system.
- Drainage assumptions, hydrostatic pressure basis, filter/drain details, and maintenance assumptions.
- Design code/standard, load combinations, durability life, corrosion/degradation assumptions, and construction constraints.
- Owner/DOT context: right-of-way or easement limits, utilities, adjacent structures, construction access, environmental constraints, and temporary staging.
- Exploration plan: boring/test-pit locations relative to wall face, maximum height, backslope/toe slope, nail zone or anchor zone, and long-wall spacing.
- Submittal/source-pack fields: plan/profile/section views, wall stationing, top/base elevations, grade profiles front and behind the wall, exploration locations, groundwater/piezometric levels, design loads, displacement or settlement limits, construction sequence, drainage outlets, and wall-system component details.

## Real Outputs

- Ground model summary and selected design parameter table.
- Earth pressure diagram and load cases.
- Sliding, overturning, bearing, settlement, and global stability utilization.
- Drainage and durability requirements.
- Interface memo identifying civil geometry constraints, geotechnical risks, and required drawing notes.
- Wall-type recommendation or review note explaining why MSE/RSS, soil nail, anchored wall, cantilever, or temporary shoring logic applies.
- Exploration adequacy note comparing boring/test-pit coverage to wall height, length, maximum-height station, backslope/toe slope, nail zone, or anchor/deadman zone.
- Submittal review checklist for contractor-designed wall or shoring systems: geometry, constraints, stratigraphy, groundwater, loads, limit states, drainage, and drawing completeness.
- Testing/QC artifacts where relevant: soil nail proof/verification load test summary, anchor proof/performance test summary, monitoring points, and inspection notes.

## Harness Implications

- Verifiers should reward traceability from ground evidence to parameters, not just correct equations.
- The task should preserve uncertain inputs: groundwater level, surcharge, soil strength, wall type, construction stage, and drainage condition.
- Strong failure modes include using drained parameters for undrained cases, omitting groundwater, assuming active earth pressure for restrained/non-yielding cases, checking only stem strength, or ignoring global stability and settlement.
- Wall-family gates matter. MSE/RSS needs reinforcement, backfill, drainage, settlement, and durability checks; soil nail walls need nail-zone exploration, stand-up time, bond/pullout, facing, drainage, corrosion, and proof/verification testing; anchored walls need anchor-zone exploration, apparent earth pressures, anchor loads, soldier-beam/lagging or sheet-pile components, drainage, and performance/proof testing.
- Multimodal verifiers should reconcile boring locations and wall sections, not just parse numbers. A model can be wrong if it computes a pressure correctly for a wall height that contradicts the drawing.
- Submittal review is a valuable harness mode: instead of asking for one final number, ask whether a proposed wall/shoring package is complete and internally consistent against the owner-provided geotechnical data and drawings.

## Multimodal Extension

- Inputs: borehole log PDF/image, cross-section drawing, wall alignment plan, lab summary table, retaining wall detail.
- Outputs: interpreted ground model table, annotated section, pressure diagram, and interface memo.
- Interesting checks: borehole-to-section mapping, layer interpolation, surcharge extraction from drawings, and consistency between wall height in drawing and calculation.
- Additional inputs: plan/profile/section sheet, boring location plan, test-pit photo/log, groundwater or piezometer table, wall-system submittal, soil nail/anchor testing sheet, drainage outlet detail, utility/easement plan, and adjacent-structure monitoring notes.
- Additional outputs: exploration adequacy map, wall-family selection memo, drawing completeness checklist, drainage assumption note, and proof/performance test review.

## Meta-Harness Opportunities

- Reconfigure wall type while holding the same ground model.
- Mutate groundwater, surcharge, backfill friction, or retained height.
- Combine with road/rail alignment tasks by passing cut/fill geometry into retaining design.
- Combine with stormwater by requiring drainage/outfall implications for retaining walls.
- Compose a long-horizon review packet: preliminary wall alignment -> investigation plan -> interpreted ground model -> wall-family selection -> design/submittal review -> construction testing/monitoring acceptance.
- Reconfigure authority overlays: FHWA/WSDOT/AASHTO, Eurocode 7, or AS 4678/road-authority basis, with task-supplied criteria where standards are gated.
