# ABOUTME: Real and near-real artifact examples for road rail alignment task grounding.
# ABOUTME: Identifies public inputs, outputs, reports, and fixture candidates for benchmark design.

# Road Rail Alignment Artifact Examples

## Public Artifacts Found

| Artifact | Source | Input/Output Shape | Benchmark Use |
| --- | --- | --- | --- |
| Caltrans Highway Design Manual | https://dot.ca.gov/programs/design/manual-highway-design-manual-hdm | Road design chapters including geometric design and drainage. | US road geometry standard source. |
| Austroads Guide to Road Design Part 3 | https://austroads.gov.au/publications/road-design/agrd03 | Current 2026 edition metadata, design parameters, alignment, superelevation, grades, operating speeds, and sight distance. | Australia/NZ road geometry source. |
| WSDOT Chapter 300 design documentation workflow | https://wsdot.wa.gov/publications/manuals/fulltext/M22-01/300.pdf | Design Approval, Project Development Approval, Design Analysis, Design Documentation Package, Project File, PS&E, and design-to-construction turnover checklist shape. | Source-pack pattern for documentation/approval gates and design-analysis flags. |
| WSDOT horizontal/profile/superelevation/sight-distance chapters | https://wsdot.wa.gov/publications/manuals/fulltext/M22-01/1210.pdf, https://wsdot.wa.gov/publications/manuals/fulltext/M22-01/1220.pdf, https://wsdot.wa.gov/publications/manuals/fulltext/M22-01/1250.pdf, https://wsdot.wa.gov/publications/manuals/fulltext/M22-01/1260.pdf | Horizontal plan elements, roadway profile elements, vertical curves, cross slope, superelevation tables, runoff transitions, stopping/passing/decision sight-distance assumptions, grade effects, and horizontal-curve sight checks. | Strong verifier-field source for road plan/profile/crossfall/sight-distance variants. |
| WSDOT railroad grade-crossing chapter | https://wsdot.wa.gov/publications/manuals/fulltext/M22-01/1350.pdf | Roadway and railway plan/profile inputs around crossings, crossing angle, warning devices, preemption, queue clearance, train/road speeds and volumes, sight distance, and coordination factors. | Strong road-rail interface source-pack source for grade-crossing variants. |
| FHWA MUTCD 11th Edition with Revision 1 | https://mutcd.fhwa.dot.gov/kno_11th_Editionr1.htm | Current official traffic-control manual metadata; Part 8 covers railroad/light-rail grade crossings. | Current US traffic-control authority basis for grade-crossing warning-device variants. |
| ERA ERTMS page and braking-curve tool | https://www.era.europa.eu/domains/european-rail-traffic-management-system/braking-curves | ETCS braking-distance tool, handbook, train/trackside data concept. | Rail braking/speed-control artifact source for rail variants. |
| RSSB RIS-0703/GKRT0075 current metadata | https://www.rssb.co.uk/standards-catalogue/CatalogueItem/ris-0703-ccs-iss-2 and https://www.rssb.co.uk/standards-catalogue/CatalogueItem/GKRT0075-Iss-5 | Live GB metadata for signalling layout/aspect sequence and minimum signalling braking/deceleration distances. | Rail standard basis for geometry-to-signalling handoffs. |
| ARTC curve and gradient diagrams | https://extranet.artc.com.au/eng_network-config_cd.html and https://extranet.artc.com.au/docs/eng/network-config/cd/S00.pdf | Corridor diagrams with chainage, elevation profile, gradients, curve radii/direction, platforms, tunnels, turnouts, level crossings, and provenance notes. | Strong real multimodal route-profile fixture for extraction and chainage-aware verification. |
| RSSB standards catalogue metadata | https://www.rssb.co.uk/standards-catalogue | Standard identity, issue lineage, public synopses. | UK rail source discovery and standard lineage. |

## Fixture Candidates

- Plan/profile drawing with chainage, horizontal curves, grades, vertical curves, and design speed.
- Design Documentation Package excerpt with authority basis, design criteria, Design Analysis/justification note, project stage, and PS&E/DDP references.
- Alignment table, vertical-curve table, and superelevation/crossfall table.
- Speed profile and sight-distance issue register.
- WSDOT-style grade-crossing source pack with 500 ft roadway plan/profile legs, 500 ft railway plan/profile, crossing angle, track count, warning-device locations, signal/preemption context, queue-storage distance, and sight-distance evidence.
- Rail gradient/speed/braking input sheet plus signal chainage table.
- ARTC-style curve/gradient diagram excerpt with route-feature extraction and braking/signalling handoff table.

## Remaining Artifact Need

- Public accepted road plan/profile drawing sets with enough geometry to test extraction.
- Rail signal layout examples and signal sighting forms.
- Filled or accepted grade-crossing plan/profile examples and preemption/queue-clearance worksheets.
- Australian road-rail interface standards and level-crossing/sighting artifacts beyond ARTC route-profile diagrams.
