# ABOUTME: Analysis for grounding the road rail alignment package in real workflows.
# ABOUTME: Summarizes workflow chain, inputs, outputs, benchmark implications, and multimodal scope.

# Road Rail Alignment Package Analysis

## Real Workflow Chain

The road side is high-confidence:

project/design basis -> documented design criteria and approvals -> horizontal alignment -> vertical profile -> superelevation/crossfall -> sight distance -> drainage/clearance interfaces -> design analysis/justification where needed -> alignment design note or PS&E/DDP handoff.

The rail side is now better grounded but still artifact-limited:

track geometry and speed profile -> cant/cant deficiency or equivalent speed checks -> braking/sighting assumptions -> signal/warning/overlap constraints -> rail interface note.

The road-rail interface is now better grounded:

roadway and railroad plan/profile around the crossing -> crossing angle and warning-device context -> sight distance and queue-clearance/preemption assessment -> grade-crossing interface note.

This composite is useful because road and rail both use chainage, profiles, curves, sight distance, and safety margins, but their design conventions and regulatory sources differ materially.

ARTC curve and gradient diagrams are especially useful because they expose a real owner artifact with chainage, elevation, grades, curvature, platforms, tunnels, turnouts, and level crossings. They can feed rail braking/signalling checks in the same way road plan/profile drawings feed sight-distance and curve checks.

WSDOT is useful because it exposes the shape of the project documentation layer as well as the geometry layer. A realistic task should not only calculate radius, grade, or sight distance; it should also know whether the design value is inside the authority's normal range, whether a design analysis/justification is required, and which source artifact carries the decision.

## Real Inputs

- Design documentation basis: authority/manual version, design approval or project stage, design analysis/justification notes, design criteria, project file/DDP/PS&E references, and approval milestone.
- Alignment plan with stationing/chainage, curve radii, transitions, intersections/crossings, and design control points.
- Long section/profile with grades, vertical curves, crest/sag locations, drainage low points, clearance constraints, and profile-grade control.
- Cross-section/crossfall data: lane/shoulder widths, normal crown, cross slope, superelevation rate, runoff length, pivot point, number of lanes, lane width, shoulder slope, and drainage notes.
- Design criteria: road design speed, operating speed, friction/superelevation limits, sight-distance basis, and design vehicle.
- Rail criteria: train type, speed, braking basis, gradient, cant/cant deficiency, signal chainage, sighting and overlap rules.
- Route-profile artifacts: ARTC-style curve/gradient PDFs, plan/profile sheets, chainage tables, speed restriction signs, and signal asset inventories.
- Grade-crossing interface data: roadway plan/profile for each leg, railway plan/profile, crossing angle, tracks, warning-device type, signal/pre-signal/preemption context, queue-storage distance, train and highway speeds/volumes, pedestrian volume, accident history, and sight distance.
- Regional standard basis: Caltrans/AASHTO, Austroads, rail owner standards, RSSB/Network Rail, ERA/ETCS, AREMA.

## Real Outputs

- Horizontal curve and minimum-radius checks.
- Superelevation/crossfall or cant checks.
- Vertical curve and sight-distance table.
- Design-analysis/justification flag for design elements outside normal criteria.
- Chainage-based interface memo.
- Grade-crossing geometry/warning/preemption/queue-clearance note.
- For rail variants, signal sighting/warning/overlap table or note.
- Route-feature extraction table for multimodal variants: platforms, turnouts, tunnels, level crossings, curves, and gradient changes by chainage.

## Harness Implications

- The verifier should be chainage-aware. Many wrong answers are numerically plausible but attached to the wrong curve, grade, or signal.
- Strong failure modes include mixing road and rail sign conventions, ignoring units, applying US road criteria to Austroads tasks, using road stopping-sight logic for rail braking, or losing chainage identity across handoffs.
- Add a documentation gate: if the model selects a value outside the task's source criteria, it must identify whether a design analysis/justification is required and preserve the reason.
- Add a crossing gate for road-rail variants: check that the model uses both roadway and railway plan/profile evidence around the crossing, not only a road centerline or only a rail chainage diagram.
- Composite tasks can pipe road profile outputs into drainage or retaining-wall tasks and pipe rail profile outputs into braking/signalling tasks.
- ARTC-style diagrams make a good verifier target because the model must preserve chainage identity while translating visual profile/curve evidence into downstream rail braking/signalling assumptions.

## Multimodal Extension

- Inputs: plan/profile sheets, alignment tables, curve diagrams, speed profile, cross-section/crossfall tables, superelevation diagrams, signal layout, grade-crossing plans, sight-distance obstruction photos, and design-decision notes.
- Outputs: annotated plan/profile, curve table, vertical-curve table, superelevation/runoff table, sight-distance flags, design-analysis requirement flag, crossing/preemption note, chainage-based issue register, and route-feature extraction table.
- Interesting checks: reading station/chainage ticks, extracting curve geometry from drawings, matching long-section gradients to tabular calculations, preserving feature chainages, reconciling road and railway stationing near a crossing, and verifying that annotations land on the correct chainage.

## Meta-Harness Opportunities

- Reconfigure region: Caltrans/AASHTO, Austroads, UK rail, Australian rail owner, ERA/ETCS.
- Mutate speed, radius, grade, sight obstruction, signal spacing, or crossing position.
- Toggle project stage: concept, design approval, PS&E, DDP, design analysis, or construction handoff.
- Combine with stormwater by passing low points, grades, and catchments into drainage.
- Combine with retaining-wall by passing cut/fill slopes and wall heights.
- Combine with rail-braking/signalling for a more standards-heavy rail package.
- Combine with road-safety/traffic-signal tasks by passing grade-crossing preemption, queue clearance, warning-device selection, and sight-distance evidence downstream.
