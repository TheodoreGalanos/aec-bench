# ABOUTME: Source-bounded notes for the road rail alignment package.
# ABOUTME: Preserves short evidence notes without copying full manuals or standards.

# Road Rail Alignment Package Scraped Notes

## Caltrans Highway Design Manual

- Caltrans publishes a public Highway Design Manual with current chapter PDFs.
- Relevant public chapter topics include geometric design and drainage-related chapters.
- This supports road geometry as a real manual-driven workflow rather than a free-floating formula task.

## WSDOT Design Documentation And Road Geometry Chapters

- WSDOT Chapter 300 frames design as a documented project-delivery workflow, not just calculation. It records design documentation, approvals, FHWA coordination, design analysis, Project File, Design Documentation Package, PS&E, and design-to-construction turnover evidence.
- Chapter 300 distinguishes levels of design-decision documentation: consider, document, justify, and Design Analysis. A Design Analysis summarizes information an approving authority needs and is required when selected dimensions fall outside the Design Manual range.
- Chapter 300 says the Design Documentation Package preserves decision documents, design criteria, and the design process; the Project File includes planning, scoping, programming, design, contract assembly, utility relocation, right-of-way, advertisement, award, constructability, traffic management, and maintenance-review comments.
- WSDOT Chapter 1210 says horizontal and vertical alignments are primary controlling elements for highway design, and they must be coordinated with design speed, drainage, intersection design, and aesthetics early in design.
- Chapter 1210 records high-speed alignment practices: make alignment direct while blending with topography, use consistent curvature, avoid abrupt alignment changes, provide tangent length for reverse-curve superelevation transitions, avoid broken-back curves, and use tangent sections for bridges/interchanges/intersections where possible.
- Chapter 1210 ties curve radii to design speed and target speed, with sight obstruction, superelevation, and vertical alignment as factors in radius selection.
- WSDOT Chapter 1220 defines vertical alignment or roadway profile as gradients connected by vertical curves. It lists controls including topography, highway class, horizontal alignment, safety, sight distance, construction cost, drainage, adjacent land use, vehicular characteristics, and aesthetics.
- Chapter 1220 covers maximum grades, minimum grades for drainage, grade length, vertical-curve length, horizontal/vertical alignment coordination, and railroad-crossing grading.
- WSDOT Chapter 1250 covers cross slope and superelevation. It states cross slope drains water away from the roadway and that highway/ramp curves are usually superelevated to offset part of centrifugal force.
- Chapter 1250 gives a strong source-pack shape for superelevation: normal crown, max superelevation choice, minimum radius tables, side-friction factor, runoff transitions, pivot-point configuration, lane width, and drainage/comfort tradeoffs.
- WSDOT Chapter 1260 covers stopping, passing, and decision sight distance. It gives design assumptions for driver eye height, object height, perception-reaction time, deceleration, grade effects, crest/sag vertical curves, and horizontal-curve sight obstructions.
- These WSDOT chapters make a staged verifier natural: design documentation -> horizontal plan -> vertical profile -> superelevation/cross slope -> sight distance -> design analysis/justification.

## Austroads Guide To Road Design Part 3

- Austroads identifies Part 3 as geometric design guidance; the inspected page lists Edition 4.0 published June 2026.
- The public abstract includes design parameters, horizontal and vertical alignment, superelevation, grades, and sight distance.
- This is a strong Australia/NZ source for road alignment variants.

## Current Rail Metadata And Route Profile Artifacts

- RSSB RIS-0703-CCS Issue 2 is live and covers signalling layout and signal aspect sequence requirements for lineside signalling compatibility with train operations.
- RSSB GKRT0075 Issue 5 is live and covers minimum signalling braking and deceleration distance parameters for signal spacing and permissible speed changes.
- ERA's braking-curve page supplies a real rail calculation artifact family: simulation tool, handbook, train data, trackside data, and graphical braking-distance outputs.
- ARTC publishes curve and gradient diagrams by corridor, with the S00 Main South PDF documenting data provenance and how to interpret grade, curvature, platforms, tunnels, turnouts, level crossings, elevation profile, gradients, radius labels, and curve direction.
- This gives the road-rail composite a stronger real drawing/PDF extraction path: chainage, profile, curvature, and route-feature evidence can be treated as source artifacts rather than invented tables.

## WSDOT Railroad Grade Crossings And MUTCD

- WSDOT Chapter 1350 identifies railroad grade crossings as a road/rail interface requiring warning-device selection, sight distance, highway and railway geometry, train/highway speeds and volumes, pedestrian volume, accident history, and railroad/WUTC input.
- Active warning elements include flashing light signals and gates, railroad preemption, pre-signals, active advance warning systems, and supplemental safety devices.
- For nearby roadway intersections, WSDOT highlights queue spillback risk onto tracks and says railroad preemption analysis considers the distance between roadway intersection and grade crossing, queue clearance times, train speeds, active-warning device capabilities, and other traffic signal phases.
- Chapter 1350 is especially useful because it names plan/profile inputs. For road-alignment alterations at crossings, it requires roadway plan and profile for each leg at least 500 feet from the crossing; railway plan and profile at least 500 feet from the crossing; crossing angle; signal locations; profiles of driveways/roads/other facilities affected; and sight-distance requirements.
- FHWA's MUTCD page identifies the current official MUTCD as the 11th Edition with Revision 1, dated December 2025. The current edition is PDF-only, and Part 8 covers traffic control for railroad and light-rail transit grade crossings.
- MUTCD should be treated as traffic-control authority; WSDOT Chapter 1350 gives a richer owner-specific source-pack shape for crossing geometry and coordination.

## Rail Signalling Orientation

- Public rail signalling summaries support the concepts of braking distance, sighting distance, overlap, signal spacing, and headway.
- These remain orientation sources only until current official rail standards are captured.

## ERA Braking Curves

- ERA's braking-curve page supplies a real rail calculation artifact family: simulation tool, handbook, train data, trackside data, and graphical braking-distance outputs.
- This gives the rail side a better fixture path than a generic kinematic equation.

## Public Plan-Set Search Limits

- A direct static fetch of the Caltrans public advertised-project shell returned a ServiceNow/Angular application shell rather than clean plan metadata or plan/profile PDFs.
- A broader public search route for roadway plan/profile sheets hit bot-protection rather than yielding a stable, citable plan set.
- This does not mean public plan/profile sets are unavailable; it means this pass did not recover a clean accepted roadway plan set suitable for immediate benchmark fixture use.
- The correct gap is narrower now: use WSDOT/Caltrans/Austroads manuals to define source-pack requirements, then keep searching agency bid portals, public records, sample-plan libraries, or authorised/redrawn project packs for actual plan/profile media.
