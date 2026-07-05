# ABOUTME: Source-bounded notes for the rail braking signalling package.
# ABOUTME: Preserves short evidence notes without copying full manuals or standards.

# Rail Braking Signalling Package Scraped Notes

## IRSE Introduction To Railway Signalling

- IRSE frames two physical reasons for signalling: trains must be routed to avoid collisions, and trains cannot stop within the distance the driver can see.
- It describes the block system as the basis of UK signalling: lines are divided into block sections, and only one train is normally permitted in a block section at a time.
- It lists safety functions: preventing conflicting routes, maintaining safe separation, protecting against driver malfunction, and ensuring trains do not exceed permitted speed.
- For mechanical signalling, the IRSE notes that distant signals are positioned at least braking distance from the next stop signal.
- It describes multiple-aspect signalling as a capacity-increasing development with red, yellow, double-yellow, and green aspects.
- It identifies train detection by track circuits and axle counters, point mechanisms with move/lock/detect functions, and interlocking as the function that decides whether requested routes or point movements are safe.
- It describes AWS and TPWS as protection layers, including warning equipment before signals and overspeed/train-stop functions near signals.
- This source strengthens the workflow chain but still does not replace railway-owner design standards for exact signal spacing, overlap, or sighting acceptance.

## RSSB GKRT0075 Issue 4

- The public synopsis says the document specifies minimum distances between the first cautionary aspect and the stop signal it applies to.
- It also addresses signing for permissible speeds and speed restrictions.
- The item is withdrawn and partly superseded, so it is useful as source lineage but not a current authority by itself.

## Current RSSB Control, Command And Signalling Metadata

- RIS-0703-CCS Issue 2 is live and covers lineside signalling system compatibility with train operations plus guidance on application.
- GKRT0075 Issue 5 is live and covers Minimum Signalling Braking Distance and Minimum Deceleration Distance as compatibility parameters for lineside signal spacing and permissible speed changes.
- The GKRT0075 Issue 5 public change notes mention methodology for steep falling gradients, which is important because gradient is one of the major ways a generic braking calculation becomes misleading.
- RIS-0737-CCS Issue 1 is live and sets out the signal sighting assessment process used to confirm compatibility of lineside signalling assets with train operations.
- RIS-0737's public change notes say it was developed from first principles and covers route compatibility of lineside assets and vehicles in operational context.
- GKRT0057 Issue 2 is live and sets out lineside signal and indicator product design/assessment requirements and guidance for managing the risk of trains exceeding the end of their movement authority.
- GKRT0057 Issue 2 supersedes Issue 1, which was withdrawn on 2024-09-07; Issue 2 was issued and published on 2024-06-01 and came into force on 2024-09-07.
- RIS-0734-CCS Issue 2.1 is live and covers permissible speed signing on the GB mainline, including newer acceleration-indicator material and warning-indicator clarity.
- RIS-0735-CCS Issue 1.1 is live and covers temporary and emergency speed restriction signing, including clarification of warning-board position at diverging junctions.
- Together these sources reduce the current-UK-standard gap for layout, braking/deceleration distance, signal sighting, signal/indicator product assessment, and speed-signing metadata. They still do not provide filled signal sighting records or full route design packs.

## RSSB GIRT7033 Issue 1

- The public synopsis covers management and specification of lineside operational safety signs to provide consistency of form and presentation.
- This supports multimodal sign/sighting variants but not braking-distance computation directly.

## ERA ERTMS And Braking Curves

- ERA describes ERTMS as a European signalling and speed-control system intended to support interoperability, speed, capacity, and safety.
- ERA describes ETCS as cab signalling with automatic train protection.
- ERA states that ETCS supervises position and speed and can command braking intervention to avoid exceeding allowed speed and distance limits.
- ERA defines a braking curve as the prediction of speed decrease versus distance from the train braking dynamics and track characteristics ahead.
- ERA provides braking-curve simulation tools and handbooks, including train and trackside data relevant to calculation and graphical braking-distance outputs.

## ARTC Curve And Gradient Details

- ARTC publishes public curve and gradient diagrams by corridor.
- The S00 Main South diagram set records source/provenance notes for grade, curvature, platforms, tunnels, turnouts, and level crossings.
- The diagrams define how to read elevation profile, gradient, radius, curve direction, platforms, turnouts, tunnels, and level crossings.
- This is strong real artifact evidence for extracting chainage, grade, curvature, and route features into braking/signalling tasks.
- It is not a signalling design standard, so it should feed the geometry/profile side of the task rather than owner acceptance criteria.

## ARTC Signalling Procedures And Design Principles

- ARTC's public signalling procedures page exposes design, construction, maintenance, forms, drawings, design tools, and competency material with state applicability. This is a strong owner-standard source family for Australian rail variants.
- The public index identifies design documents for Signal Design and Standards Applicability, Common Signal Design Principles, Train Braking Application Design, Signals, Overlaps, Signal Design Process, Signalling Documentation and Drawings, Signal Sighting and Position, and Rolling Stock Signalling Interface.
- ESD-05-01 states that the common design principles address route holding, interlocking between routes/points/ground frames, approach locking, time releases, point concepts, overlap concepts, headway, and braking-distance effects on signalling-system design.
- ESD-05-01 ties main routes to running moves where speed is dictated by track geometry and speed boards, while subsidiary/shunt routes rely on lower-speed, obstruction-aware movement rules. This matters because a benchmark must identify the route class before scoring a signal-spacing or overlap decision.
- ESD-05-01 treats locking across routes, points, level crossings, ground frames, and overlaps as part of the safe-clearance condition for a signal. A model that only calculates braking distance but ignores route/overlap locking would be solving a simplified physics task, not a signalling package.

## ARTC Train Braking Application Design

- ESD-05-03 says the first step in determining signalling braking distances is establishing which train types use the network section and which brake tables apply.
- It requires STOPDIST calculations for specified train types when multiple train types use a line section, because the critical train can change by speed band.
- It explicitly rejects averaging multiple gradients on approach to a signal; STOPDIST is used for progressive braking distance across each gradient section.
- For trains longer than 200 m, it notes that the train's position relative to changing gradients affects braking distance, and the STOPDIST tool allows for long trains and changing gradients.
- The standard requires calculation records, STOPDIST start/results reports, a summary record, design checker review, and design verifier review of inputs, outputs, and application to signal spacing.
- ESD0503F-01 gives a clean fixture shape: entry signal, position kilometre, stop signal, train type, line speed, and braking distance, with designer/project/signal-arrangement-plan metadata.
- This source significantly reduces the rolling-stock/braking workflow gap for Australian variants, but it does not by itself provide filled STOPDIST reports or a reusable product-grade dataset.

## ARTC Signal Sighting And Forms

- ESS-04-01 records signal sighting as a working-group/design-authority process, not just a visibility calculation.
- It requires final signal sighting forms to contain site-inspection information and be signed by working-group representatives.
- It says the working-group decisions are recorded on ESS0401F-01 Signal Sighting form and that complete forms are returned to the design engineer as part of the design reports.
- The required sighting-form fields include drawing number, project, location, signal number, design location, actual location, lateral distance to running rail, red indication height, rail/ground height, signal sketch, location sketch relative to lines and direction, lens, side of track, background, line speed, sighting distance, signage, background/foreground interference, other-signal read-through, and special requirements.
- The same appendix says the signal sighting working group should include competent representatives for engineering and train-driver requirements, plus maintenance, operations, operator representatives, and others as appropriate.
- This is the strongest public signal-sighting fixture source found so far: it gives the expected record fields even though filled forms and real sighting photos remain missing.

## ARTC Drawings And Controlled Configuration

- ARTC describes its Drawing Management System as a central repository of controlled up-to-date as-built and historic infrastructure drawings, managed on Aconex.
- Access is limited to ARTC staff and authorised users, and drawings needed for projects are requested through relevant ARTC project managers.
- This explains why public full signal arrangement plans remain a gap, while still giving a realistic workflow: source drawings exist, are controlled, and are part of the design/configuration-management chain.

## US eCFR 49 CFR Part 236

- eCFR Part 236 is a public US regulatory floor for signal/train-control systems, devices, and appliances.
- The table of contents covers roadway signal location and spacing, track circuits, automatic block systems, interlocking, traffic control systems, automatic train stop/train control/cab signal systems, PTC, testing, and records.
- Section 236.502 requires automatic train-stop or train-control systems to initiate automatic braking at least stopping distance before a restrictive block condition or speed-reduction signal.
- Section 236.511 similarly requires cab signals to be controlled according to conditions at least stopping distance in advance.
- This is useful regional contrast: it validates the stopping-distance/control-system dependency but does not replace railroad-specific signal layout, sighting, or brake-table procedures.

## FRA Positive Train Control Document Surface

- FRA describes PTC systems as designed to prevent train-to-train collisions, over-speed derailments, incursions into work zones, and movements through switches left in the wrong position.
- FRA states that PTC was in operation on all 57,536 required freight and passenger railroad route miles by 2020-12-29, with interoperability achieved between applicable host and tenant railroads on PTC-governed main lines.
- FRA describes required PTC document submissions including PTC Implementation Plans, requests to test uncertified PTC systems on the general rail network, PTC Safety Plans, and FRA decision letters.
- FRA's railroad PTC docket page lists public regulations.gov docket numbers by railroad, including Amtrak, BNSF, CSX, Caltrain, Metrolink, Metro-North, NJ Transit, SEPTA, Union Pacific, and others.
- FRA publishes PTC quarterly and annual progress report forms and form guides.
- This source family is strong for US report-package and compliance-document variants. It does not provide railroad-specific signal sighting, signal-spacing, or brake-table design criteria.

## Multimodal Signal Asset Extraction

- Ritika et al. describe detecting railway signals from a camera mounted on a moving locomotive and tracking their locations.
- The paper frames the use case as maintaining accurate inventories of wayside assets such as signals, crossings, switches, and mileposts for safety rule enforcement.
- It highlights a rail-specific multimodal issue: signals must be associated with the track they govern, especially in dense multi-track urban environments where placement is constrained.
- This supports benchmark variants where signal photos/video, route geometry, and asset-location tables are checked together.

## Public Artifact Search Boundary

- Targeted public discovery improved source surfaces for GB signal sighting/product assessment and US PTC report packages, but did not recover filled signal sighting records, actual STOPDIST bundles, or live signal arrangement plans suitable for redistribution.
- The most practical benchmark path is still task-supplied or redrawn project artifacts with public standards/forms defining expected fields and review gates.

## Public Signalling Summaries

- Public signalling summaries align on the basic concepts of braking distance, sighting distance, overlap, route conflict protection, and headway.
- These are useful for orientation only; final benchmark authority needs standards or railway-owner rules.
- Public signalling summaries identify line speed, train speed, gradient, braking characteristics, sighting, and driver reaction time as inputs to signal spacing.
- Public summaries also reinforce that overlaps and signal block lengths vary by country and signalling philosophy, so regional metadata cannot be decorative.
