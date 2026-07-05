# ABOUTME: Source index for grounding the road rail alignment composite template.
# ABOUTME: Records road geometry and rail signalling sources for alignment, sighting, and warning chains.

# Road Rail Alignment Package Source Index

## Current Chain Confidence

The road-geometry side is well supported by public road design sources: alignment, profile, horizontal curves, superelevation, vertical curves, sight distance, and design documentation are standard manual-driven design concepts. WSDOT public chapters now make the source-pack chain more concrete: design documentation/PS&E, horizontal plan elements, vertical profile elements, cross slope/superelevation, sight distance, and railroad grade-crossing interfaces. The rail side is stronger after adding current RSSB metadata and ARTC curve/gradient diagrams, but public accepted road plan/profile sets, signal sighting forms, and full signalling layout examples still need more evidence before hardening.

## Sources

| Source | Type | Region | Relevance |
| --- | --- | --- | --- |
| Caltrans Highway Design Manual. https://dot.ca.gov/programs/design/manual-highway-design-manual-hdm | government-manual | US/California | Public manual with geometric design, hydrology/drainage, and current chapter PDFs. Confirms that official road design manuals package geometry and drainage requirements into chaptered design criteria. |
| Austroads Guide to Road Design Part 3: Geometric Design. https://austroads.gov.au/publications/road-design/agrd03 | primary-open/current | Australia/NZ | Current 2026 edition metadata. Direct regional source for road alignment, design speed, operating speed, horizontal/vertical alignment, superelevation, grades, and sight distances. |
| WSDOT Design Manual Chapter 300: Design Documentation, Approval, and Process Review. https://wsdot.wa.gov/publications/manuals/fulltext/M22-01/300.pdf | government-manual/current | US/Washington | Public owner workflow source for design documentation, design analysis, design approval, project development approval, PS&E, DDP, project file, and design-to-construction turnover evidence. |
| WSDOT Design Manual Chapter 1210: Geometric Plan Elements. https://wsdot.wa.gov/publications/manuals/fulltext/M22-01/1210.pdf | government-manual/current | US/Washington | Public road horizontal-alignment source covering plan elements, design-speed coordination, horizontal curve radii, alignment consistency, frontage roads, lane arrangement, pavement transitions, and references to superelevation/sight-distance chapters. |
| WSDOT Design Manual Chapter 1220: Geometric Profile Elements. https://wsdot.wa.gov/publications/manuals/fulltext/M22-01/1220.pdf | government-manual/current | US/Washington | Public vertical-profile source covering roadway profiles as gradients connected by vertical curves, profile controls, maximum/minimum grades, vertical-curve lengths, drainage, railroad crossings, and coordination of horizontal/vertical alignment. |
| WSDOT Design Manual Chapter 1250: Cross Slope and Superelevation. https://wsdot.wa.gov/publications/manuals/fulltext/M22-01/1250.pdf | government-manual/current | US/Washington | Public source for roadway cross slope, normal crown, superelevation rate selection, minimum radius/superelevation tables, side-friction factor, runoff transitions, and drainage/comfort tradeoffs. |
| WSDOT Design Manual Chapter 1260: Sight Distance. https://wsdot.wa.gov/publications/manuals/fulltext/M22-01/1260.pdf | government-manual/current | US/Washington | Public source for stopping, passing, and decision sight distance; includes eye/object-height assumptions, perception-reaction time, deceleration, grade effects, crest/sag/horizontal sight checks, and design-speed tables. |
| WSDOT Design Manual Chapter 1350: Railroad Grade Crossings. https://wsdot.wa.gov/publications/manuals/fulltext/M22-01/1350.pdf | government-manual/current | US/Washington | Public road-rail interface source covering grade-crossing warning devices, preemption, queue clearance, crossing geometry, sight distance, plan/profile requirements for roadway and railroad alignment, and coordination with railroads. |
| FHWA MUTCD 11th Edition with Revision 1. https://mutcd.fhwa.dot.gov/kno_11th_Editionr1.htm | government-manual/current | US | Current official traffic-control manual metadata, dated December 2025. Part 8 is the relevant railroad/light-rail grade-crossing traffic-control source; full current edition is PDF-only. |
| ERA braking curves page and simulation tools. https://www.era.europa.eu/domains/european-rail-traffic-management-system/braking-curves | primary-open/example-artifact | EU | Useful for rail-side braking/profile variants when the road-rail composite includes rail speed supervision or signalling constraints. |
| RSSB RIS-0703-CCS Issue 2. https://www.rssb.co.uk/standards-catalogue/CatalogueItem/ris-0703-ccs-iss-2 | primary-open metadata/current | UK | Current GB metadata for signalling layout and signal aspect sequence requirements. Useful when the composite passes rail geometry into signalling placement checks. |
| RSSB GKRT0075 Issue 5. https://www.rssb.co.uk/standards-catalogue/CatalogueItem/GKRT0075-Iss-5 | primary-open metadata/current | UK | Current GB metadata for minimum signalling braking and deceleration distances, including steep falling gradient methodology notes. Useful for rail profile to braking-distance handoffs. |
| ARTC curve and gradient details. https://extranet.artc.com.au/eng_network-config_cd.html | primary-open owner artifact | Australia | Public owner route artifacts with corridor PDFs/HTML. The S00 Main South PDF documents chainage, elevation profile, gradient, curve radius/direction, platforms, tunnels, turnouts, level crossings, and source/provenance notes. Strong real input artifact for multimodal extraction. |
| Wikipedia, Geometric design of roads. https://en.wikipedia.org/wiki/Geometric_design_of_roads | secondary | Global | Orientation only. Confirms alignment/profile/cross-section framing and road geometry formulas. |
| Wikipedia, Railway signalling. https://en.wikipedia.org/wiki/Railway_signalling | secondary | Global | Orientation on signal headway, sighting distance, overlap, braking distance, and layout calculation concepts. Needs official rail standards. |
| Wikipedia, Application of railway signals. https://en.wikipedia.org/wiki/Application_of_railway_signals | secondary | Global | Orientation on protection of conflict points, following trains, distant signal placement, and braking distance. |

## Real Inputs

- Alignment plan: chainage, horizontal geometry, curves, transition spirals.
- Long section: grades, vertical curves, sight constraints.
- Design documentation basis: design approval stage, design analysis/justification notes, design criteria, project file, PS&E or DDP references, and region/authority basis.
- Design criteria: design speed, operating speed model, friction/superelevation limits, cross slope, drainage controls, design vehicle/train.
- Rail data: train speed, braking distance, cant/cant deficiency, gradient convention.
- Grade-crossing data: crossing angle, roadway and railroad profile, roadway and railroad alignment, tracks, warning device type, traffic signal preemption, queue clearance, train/highway speeds and volumes, accident history, available sight distance, and railroad coordination.
- Signalling layout: signal chainage, sighting distance, overlap, warning time criteria.

## Real Outputs

- Curve element and minimum radius checks.
- Superelevation/cant/cant-deficiency checks.
- Vertical curve and stopping sight distance table.
- Design-analysis or justification note when design values fall outside the authority's normal range.
- Grade-crossing warning/preemption/queue-clearance note where road and rail meet.
- Signal sighting/warning time/overlap table.
- Alignment interface memo with chainage-based handoffs.

## Task Implications

- The civil road alignment chain is high-confidence.
- Road-rail grade-crossing variants now have stronger WSDOT/MUTCD grounding for interface geometry, warning devices, preemption, and plan/profile inputs.
- Rail signalling now has stronger RSSB/ERA/ARTC grounding, but still needs signal sighting forms and full layout packs before we claim full confidence.
- The strongest verifier risk is sign convention and chainage identity: plausible numbers can be wrong if they refer to the wrong curve, grade, or signal.
