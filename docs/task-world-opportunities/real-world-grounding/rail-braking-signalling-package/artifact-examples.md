# ABOUTME: Real and near-real artifact examples for rail braking signalling package grounding.
# ABOUTME: Identifies public inputs, outputs, reports, and fixture candidates for benchmark design.

# Rail Braking Signalling Package Artifact Examples

## Public Artifacts Found

| Artifact | Source | Input/Output Shape | Benchmark Use |
| --- | --- | --- | --- |
| IRSE Introduction to Railway Signalling | https://www.irse.org/Portals/0/NewPortal/DownloadableLinks/QualificationsCareers/Module%202/Mod2%20Introduction%20to%20Railway%20Signalling%20v1.0_Additional%20reading.pdf?ver=2020-11-25-154312-703 | Workflow description for blocks, aspects, train detection, interlocking, AWS/TPWS, and cab signalling. | Practice-grounded chain validation and vocabulary source; not enough for deterministic design values. |
| RSSB RIS-0703-CCS Issue 2 | https://www.rssb.co.uk/standards-catalogue/CatalogueItem/ris-0703-ccs-iss-2 | Live metadata for signalling layout and signal aspect sequence requirements. | Current GB authority metadata for layout/aspect-sequence variants. |
| RSSB GKRT0075 Issue 5 | https://www.rssb.co.uk/standards-catalogue/CatalogueItem/GKRT0075-Iss-5 | Live metadata for minimum signalling braking and deceleration distances, including steep falling gradient methodology notes. | Current GB authority metadata for braking-distance and signal-spacing variants. |
| RSSB RIS-0737-CCS Issue 1 | https://www.rssb.co.uk/standards-catalogue/CatalogueItem/RIS-0737-CCS-Iss-1 | Live metadata for signal sighting assessment requirements, route compatibility of lineside assets and vehicles, and operational-context assessment. | Current GB authority metadata for signal-sighting assessment variants. |
| RSSB GKRT0057 Issue 2 | https://www.rssb.co.uk/standards-catalogue/CatalogueItem/gkrt0057-iss-2 | Live metadata for lineside signal and indicator product design and assessment, framed around risk of trains exceeding the end of movement authority. | Current GB authority metadata for signal/indicator product-readability and end-of-authority risk variants. |
| RSSB RIS-0734/RIS-0735 | https://www.rssb.co.uk/standards-catalogue/CatalogueItem/ris-0734-ccs-iss-2-1 and https://www.rssb.co.uk/standards-catalogue/CatalogueItem/ris-0735-ccs-iss-1-1 | Live metadata for permanent, temporary, and emergency speed restriction signing. | Speed-signing and warning-board source family for multimodal signage variants. |
| ERA ERTMS page | https://www.era.europa.eu/domains/infrastructure/european-rail-traffic-management-system-ertms_en | ETCS/ERTMS system authority, specifications, braking-curves link, CCS TSI references. | EU signalling/speed-control authority metadata. |
| ERA braking-curves page | https://www.era.europa.eu/domains/european-rail-traffic-management-system/braking-curves | Tool, handbook, train/trackside data concept, braking distance computation. | Strong artifact source for braking-curve input/output shape. |
| ARTC signalling procedures index | https://extranet.artc.com.au/eng_signal_procedure.html | Public list of design, construction, maintenance, forms, drawings, design tools, and competency documents with state applicability. | Australian owner-standard discovery source; anchors which documents/forms belong to the package. |
| ARTC ESD-05-01 Common Signal Design Principles | https://extranet.artc.com.au/docs/eng/signal/procedures/design/ESD-05-01.pdf | Route classes, route locking, approach locking, headway, signal spacing, sighting point/distance, braking-distance concepts, overlap concepts, point locking, and interlocking principles. | Design-chain authority for composing braking, signal spacing, overlap, and locking gates. |
| ARTC ESD-05-03 Train Braking Application Design | https://extranet.artc.com.au/docs/eng/signal/procedures/design/ESD-05-03.pdf | Applicable train types/brake tables, STOPDIST workflow, multiple-gradient and long-train considerations, records, design reports, design check, and design verification. | Strong fixture model for staged braking calculations and design-report evidence. |
| ARTC ESD0503F-01 braking summary form | https://extranet.artc.com.au/docs/eng/signal/forms/design/ESD0503F-01.pdf | Entry signal, position km, stop signal, train type, line speed, braking distance, signal designer, project, organisation, date, and signal arrangement plan. | Direct structured output template for braking-distance summary records. |
| ARTC ESS-04-01 Signal Sighting and Position | https://extranet.artc.com.au/docs/eng/signal/procedures/construction/ESS-04-01.pdf | Signal sighting working-group process, design-authority review, and required signal-sighting-form fields including signal ID, design/actual location, dimensions, sketches, lens/background, line speed, sighting distance, signage, interference/read-through, and signatures. | Strongest public signal-sighting fixture source found so far; gives input/output fields for multimodal sighting tasks. |
| ARTC signalling forms page | https://extranet.artc.com.au/eng_signal_form.html | Public list of braking summary, signal sighting, design-control/package/checklist, rolling-stock interface, commissioning, and handover forms. | Form catalogue for staged package deliverables even when filled project records are unavailable. |
| ARTC drawing management page | https://extranet.artc.com.au/eng_network-config_drawing.html | Describes controlled as-built/historic drawing repository, authorised-user access, drawing request process, drawing templates, signal-data submission checklist, and signal drawing templates. | Explains why live signal arrangement plans are controlled while providing a realistic source-reference workflow for task-supplied/redrawn plans. |
| RSSB standards catalogue and GKRT/GIRT metadata | https://www.rssb.co.uk/standards-catalogue | Public standard identity and issue metadata for UK rail signalling. | UK source discovery and terminology lineage. |
| ARTC curve and gradient diagrams | https://extranet.artc.com.au/eng_network-config_cd.html and https://extranet.artc.com.au/docs/eng/network-config/cd/S00.pdf | Corridor PDFs/HTML with chainage, elevation profile, gradients, curve radii/direction, platforms, tunnels, turnouts, level crossings, and provenance notes. | Real geometry/profile input artifact for braking and chainage-aware signalling variants. |
| US eCFR 49 CFR Part 236 | https://www.ecfr.gov/current/title-49/subtitle-B/chapter-II/part-236 | Public US regulatory structure for signal/train-control systems, including roadway signals, signal spacing, track circuits, interlocking, automatic train stop/control, cab signals, PTC, testing, and records. | Regional regulatory contrast; useful for US variants that need stopping-distance and train-control evidence without claiming railroad-specific layout tables. |
| FRA Positive Train Control overview | https://railroads.dot.gov/research-development/program-areas/train-control/ptc/positive-train-control-ptc | Public federal overview of PTC purpose, mandated route-mile implementation, interoperability, certification, and document-submission expectations. | US train-control compliance and report-package context. |
| FRA Railroads' PTC dockets | https://railroads.dot.gov/research-development/program-areas/train-control/ptc/railroads-ptc-dockets | Public railroad-by-railroad docket list for PTC documents in regulations.gov. | Discovery path for real PTC Implementation Plans, Safety Plans, test requests, and decision letters. |
| FRA PTC quarterly report form | https://railroads.dot.gov/elibrary/positive-train-control-ptc-quarterly-report | Public form/template page for quarterly PTC progress reports, including Form FRA F 6180.165 and guide links. | Form-shaped artifact for US train-control reporting variants. |
| Railway signal detection paper | https://arxiv.org/abs/1712.06107 | Forward-facing locomotive video, signal detection, track association, asset location inventory, 150 km/247-signal evaluation route. | Multimodal signal asset/sighting and track-association fixture analogue. |

## Fixture Candidates

- Train braking parameter sheet and gradient/speed profile.
- Track plan/chainage diagram with signal locations and conflict points.
- Block-section/aspect diagram plus train-detection and interlocking state table.
- STOPDIST-like braking report bundle plus ARTC-style ESD0503F-01 summary record.
- ETCS braking-curve simulation workbook inputs/outputs.
- Signal sighting form/photo set with ARTC-style fields for signal ID, design and actual km, dimensions, lens/background, line speed, sighting distance, signage, interference, read-through, and working-group signatures.
- GB sighting/product-readability packet with RIS-0737/GKRT0057 authority metadata, driver approach image, signal/indicator product metadata, route/vehicle compatibility note, and task-supplied criteria excerpt.
- Overlap/headway calculation note with route/point locking assumptions.
- ARTC-style curve and gradient diagram excerpt with signal or speed restriction chainages overlaid.
- Forward-facing signal photo/video frame plus track association and asset-location table.
- Controlled signal arrangement plan reference or redrawn equivalent, with source-drawing metadata but no restricted drawing dependency.
- US PTC compliance packet with docket reference, PTC Implementation Plan or Safety Plan excerpt, FRA decision-letter status, host/tenant interoperability note, subdivision or route scope, and quarterly-report form fields.

## Remaining Artifact Need

- Filled signal sighting records, live signal arrangement plans, and route tables suitable for redistribution.
- Operator-specific braking assumptions and actual STOPDIST reports for real projects.
- Public PTC docket documents with enough non-redacted route/scope/system detail to create reusable US report-pack fixtures.
- Additional non-GB/non-ARTC owner standards, especially US railroad/AREMA practice and other Australian state/operator practices.
- Regional mapping across UK, EU/ETCS, Australia, and North America.
