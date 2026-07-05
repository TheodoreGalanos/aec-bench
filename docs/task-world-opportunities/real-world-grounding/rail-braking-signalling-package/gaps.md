# ABOUTME: Gap register for the rail braking signalling package.
# ABOUTME: Tracks missing standards access, real artifacts, and follow-up research questions.

# Rail Braking Signalling Package Gaps

## Source Gaps

- Current RSSB metadata is stronger for layout/aspect sequence, braking/deceleration distances, signal sighting assessment, signal/indicator product assessment, and speed signing, but full public GB text, filled sighting records, and Network Rail-style project packages still need capture.
- ARTC now provides public owner standards for signal design principles, braking application design, signal sighting, forms, overlaps, and drawing-management process. Additional Australian state/operator standards are still useful for regional comparison.
- US eCFR Part 236 and FRA PTC sources provide public regulatory and report-package context for signal/train-control systems, stopping-distance dependencies, cab signals, PTC implementation/safety plans, decision letters, quarterly reports, and records/testing, but US railroad-specific signal layout, sighting, brake-table, and AREMA-style design practice remain unresolved.
- Need deeper ERA/ETCS braking-curve source extraction from the tool/handbooks.

## Data Gaps

- Rolling-stock braking curves and adhesion assumptions remain operator-specific. ARTC exposes brake-table names, STOPDIST workflow, and allowances, but not filled project STOPDIST report bundles.
- Blank/required signal sighting form fields are now public via ARTC, but filled signal sighting records, sighting photos, and working-group decision records are rarely public.
- FRA exposes PTC docket/report surfaces, but usable US benchmark fixtures still require selecting non-redacted docket documents with enough route scope, technology, testing, host/tenant, and decision-letter content.
- ARTC curve/gradient diagrams provide public chainage/profile artifacts, and ARTC drawing-management material confirms signal/as-built drawings exist in controlled repositories. Live signal arrangement plans, route tables, and signal data are still controlled or permissioned.

## Benchmark Gaps

- Need explicit jurisdiction/scenario metadata.
- Need a simplified-but-honest braking model for benchmark generation that can represent train-type brake-table selection, progressive gradients, long-train effects, and source-supplied margins without requiring proprietary STOPDIST internals.
- Need visual artifact handling for track plans, profiles, signal arrangement plans, and sighting photos or field sketches.
- Need a track-association verifier for signals in images/video on multi-track alignments.
- Need a controlled-drawing substitution strategy: use redrawn/synthetic signal arrangement plans with ARTC-like metadata, rather than relying on restricted Aconex/DMS drawings.
- Need a US train-control report-package variant that is deliberately scoped to PTC documentation and reporting, separate from signal-layout design, unless task-supplied owner criteria are available.
