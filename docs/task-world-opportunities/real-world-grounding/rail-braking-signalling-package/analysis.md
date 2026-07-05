# ABOUTME: Analysis for grounding the rail braking signalling package in real workflows.
# ABOUTME: Summarizes workflow chain, inputs, outputs, benchmark implications, and multimodal scope.

# Rail Braking Signalling Package Analysis

## Real Workflow Chain

The chain is now medium-high confidence:

rolling stock and braking model -> line speed and gradient profile -> service/emergency braking distance -> signal sighting and warning time -> overlap/conflict protection -> headway/capacity implication -> signalling layout note.

Current RSSB metadata confirms that GB standards cover lineside signalling layout/aspect-sequence compatibility, minimum signalling braking/deceleration distances, and speed restriction signing. Public summaries also align with the idea that braking distance, sighting, overlap, and train length drive signal layout and headway. Regional practice varies sharply, so this template must be explicit about jurisdiction and signalling philosophy.

RSSB RIS-0737-CCS adds a current GB signal-sighting assessment authority path. Its public synopsis frames signal sighting as the assessment process for confirming compatibility of lineside signalling assets with train operations, including route compatibility between lineside assets and vehicles in operational context. That matters because signal sighting is not only "can I see the light?" but a compatibility and operating-context record.

RSSB GKRT0057 Issue 2 adds a current GB lineside signal and indicator product-design path. Its public synopsis reframes the source family around managing the risk of trains exceeding the end of their movement authority. This gives us a separate verifier surface for lineside signal/indicator readability and end-of-authority risk, distinct from signal-spacing calculations and from sighting committee records.

IRSE training material strengthens the real-world chain by tying the physical reasons for signalling to blocks, aspect sequences, train detection, interlocking, and AWS/TPWS protection layers. It still leaves exact owner design criteria open.

ARTC now strengthens the owner-standard side, not only the geometry side. ESD-05-01 connects route locking, approach locking, headway, braking distance, signal spacing, sighting point/distance, and overlaps. ESD-05-03 makes braking distance a design-record workflow: choose applicable train types and brake tables, run STOPDIST for the relevant train/gradient cases, retain start/results reports, summarize the final distances, and have the design checked and verified against the signal arrangement plan. ESS-04-01 makes signal sighting a working-group and design-authority record with explicit form fields, not merely a geometric visibility check. ARTC curve and gradient diagrams strengthen the route-profile input side, while ERA braking-curve tools strengthen the cab-signalling/braking computation side. The railway signal detection paper adds a realistic multimodal asset-inventory path: sighted signals must be associated with the track they govern, not merely detected in an image.

US eCFR Part 236 and FRA PTC material add a useful regulatory/documentation contrast. Part 236 confirms that US signal/train-control rules also depend on stopping distance, roadway signal spacing, interlocking, track circuits, cab-signal control, automatic braking, PTC plans, and testing records. FRA's PTC overview and docket index expose a real document-package surface: PTC Implementation Plans, testing requests, safety plans, decision letters, annual or quarterly progress reports, and interoperability/certification evidence. These are not substitutes for a railroad owner's signal-layout manual, but they define a credible US compliance/reporting variant.

## Real Inputs

- Train type, length, mass, braking rate/curve, wheel-rail adhesion assumptions, and safety margin.
- Alignment and profile: chainage, gradient, curves, sighting obstructions, tunnels/platforms/junctions.
- Permissible speed profile, speed restrictions, approach control, and station stop pattern.
- Signal/aspect system, train detection sections, overlaps, route conflicts, and interlocking constraints.
- Protection overlays such as AWS/TPWS or cab signalling/ETCS where the scenario includes them.
- ARTC-style train-type/brake-table basis, STOPDIST input reports, STOPDIST output reports, and braking-distance summary record.
- Signal arrangement plan reference, signal number, design location, actual sighted location, signal/track relationship, lens/background choices, line speed, sighting distance, signage, interference/read-through notes, and access/special requirements.
- GB signal-sighting and product-readability metadata: sighting assessment basis, operational-context/route compatibility note, signal or indicator product/readability basis, end-of-movement-authority risk basis, and registered-standard references where exact clauses are gated.
- US train-control compliance artifacts: PTC Implementation Plan or Safety Plan reference, host/tenant interoperability context, route-mile or subdivision scope, train-control technology, test or revenue-service demonstration status, FRA decision letter, and periodic report fields.
- Regional rules: UK RSSB/Network Rail, Australian rail authority standards, AREMA/US railroad rules, ETCS/ERA.
- Real route artifacts: curve/gradient diagrams, signal asset inventories, route tables, video/photo sighting evidence, and speed restriction signs.

## Real Outputs

- Braking distance table or curve by speed/gradient/train type.
- ARTC-style braking summary record: entry signal, position km, stop signal, train type, line speed, final braking distance, and linked STOPDIST reports.
- Signal spacing and sighting table.
- Signal sighting form: design/actual location, lateral/height dimensions, sketch references, track side, lens/background, sighting distance, signage, interference, read-through, working-group signatures, and design-authority review.
- GB-style compatibility note covering signal-sighting assessment, lineside asset/vehicle compatibility, and end-of-movement-authority risk evidence.
- US PTC compliance/reporting packet: plan reference, implementation or safety-plan findings, testing/decision-letter status, report-period metrics, interoperability note, and exceptions or remaining actions.
- Overlap and conflict-point protection note.
- Headway/capacity implication.
- Annotated track plan or chainage diagram.
- Block/aspect/interlocking explanation showing how the proposed layout prevents conflicting moves.
- Asset/sighting output for multimodal variants: signal location, governing track, visible aspect/signage, sighting concern, and chainage alignment.

## Harness Implications

- The task should not be a generic kinematics problem unless explicitly simplified. Real signalling tasks depend on standards, aspect philosophy, and operational context.
- Strong failure modes include using the wrong train type/brake table, averaging gradients when the owner procedure requires progressive calculation, ignoring long-train gradient effects, using emergency braking where service braking is required, ignoring sighting/warning time, omitting overlap, omitting route/point locking implications, and transferring assumptions between regions.
- Verification likely needs a mix of numeric checks and rubric checks for standards traceability.
- ARTC-style variants can now have deterministic verifier gates for: applicable train types selected, braking records present, STOPDIST report references present, summary record fields complete, sighting-form fields complete, design report assembled, overlap/route-locking evidence present, and controlled drawing references named even if the drawing itself is task-supplied or redrawn.
- GB-style variants can now be split into layout/aspect-sequence compatibility, braking/deceleration distance compatibility, signal sighting assessment, speed-signing, and signal/indicator product-readability gates. Exact clause grading should remain task-supplied or licensed where RSSB full standard text is registered/gated.
- US PTC variants should be treated as train-control compliance/reporting packages unless an owner signal-layout standard is provided. A verifier can check that PTC purpose, route scope, interoperability, plan/safety-plan references, decision letters, and reporting forms are present without pretending this is equivalent to an AREMA or railroad signal-layout design package.
- Multimodal variants need track association checks: detecting a signal is not enough if the model assigns it to the wrong line or route.

## Multimodal Extension

- Inputs: track plan, gradient profile, signal sighting photo, route table, rolling-stock braking curve, speed profile diagram.
- Inputs for the strongest first fixture: ARTC curve/gradient excerpt, simplified signal arrangement plan, train-type/brake-table excerpt, STOPDIST-like report, blank sighting-form fields, and a sighting photo or redrawn field sketch.
- Inputs for a GB sighting/product variant: simplified route diagram, signal/indicator product metadata, driver approach photo or video frame, asset/vehicle compatibility note, and task-supplied RIS-0737/GKRT0057 criteria excerpt.
- Inputs for a US PTC variant: public docket document excerpts, route/subdivision scope, host/tenant relationship, PTC technology description, and quarterly/annual report form fields.
- Outputs: annotated chainage plan, braking/signal-spacing table, braking summary record, sighting form, overlap mark-up, signal asset table, and signalling note.
- Interesting checks: reading chainage and gradients from diagrams, detecting sighting obstructions from photos, associating signals with the correct track, and ensuring signal placement aligns with route conflicts.

## Meta-Harness Opportunities

- Reconfigure jurisdiction and signalling philosophy.
- Mutate rolling-stock braking performance, gradient, speed profile, and headway target.
- Combine with road-rail alignment package by passing geometry/profile into signalling.
- Combine with accessibility/safety tasks by requiring sighting, human factors, and operational rules.
