# ABOUTME: Research workspace for grounding composite task-world templates in real practice.
# ABOUTME: Tracks source evidence, real inputs/outputs, standards, reports, and remaining gaps.

# Real-World Grounding Research

This folder grounds composite task-world templates against real engineering practice, including the long-horizon product-world scenarios used in the current benchmark slice.

The intent is to collect evidence before changing benchmark tasks: use cases, specifications, standards, real input/output artifacts, reports, regional differences, and gaps. These are research artifacts, not implementation files.

For the current roll-up of long-horizon SSC design notes, runnable baselines, all-product synthetic packages, and remaining boundaries, see `long-horizon-task-summary.md`. For the local SME-authored power distribution review skill inventory, see `power-playground-skill-inventory.md`. For the review-loop lesson on long-horizon task construction, see `review-loop-long-horizon-lessons.md`.

## Folder Contract

Each template folder should eventually contain:

| File | Purpose |
| --- | --- |
| `source-index.md` | Source catalogue with standards, manuals, reports, examples, and web-accessible inputs/outputs. |
| `analysis.md` | Synthesis of real workflow chain, expected inputs/outputs, verifier implications, and data gaps. |
| `scraped-notes.md` | Short, source-bounded notes or small excerpts. Do not paste whole copyrighted documents. |
| `artifact-examples.md` | Real or near-real public artifacts that could become benchmark fixtures or verifier evidence. |
| `gaps.md` | Missing standards, gated sources, inaccessible data, and follow-up questions. |

For copyrighted standards and reports, store bibliographic/source metadata, URLs, section references when visible, and short compliant excerpts only.

## Coverage Tracker

| Template | Current Status |
| --- | --- |
| `stormwater-drainage-package` | First-pass source index and analysis complete. |
| `detention-outlet-hgl-package` | Task-owned SSC-03 detention outlet HGL template now runs as a built-in synthetic task over Rational Method runoff, triangular detention storage, orifice release, emergency weir release, freeboard, and downstream HGL clearance; real source-pack parser/formula verification and accepted project evidence remain open. |
| `pump-station-duty-package` | First-pass packet complete; Ten States gives a strong wastewater pump-station anchor, but pump-curve examples remain needed. |
| `fire-water-supply-sprinkler-demand` | Fire-flow/sprinkler workflow now grounded with EPANET, current UK/EU and Australian metadata, South East Water hydrant-testing guidance, and a sample hydraulic calculation report; exact code criteria remain gated. |
| `road-rail-alignment-package` | First-pass source index started from public road geometry sources; rail interface remains a weak spot. |
| `wind-facade-structural-package` | First-pass source index and analysis started from ASCE/Eurocode metadata; facade examples remain weak. |
| `civil-ground-retaining-interface` | First-pass source index and analysis started from Eurocode/FHWA material; real project examples remain weak. |
| `treatment-aeration-power-package` | First-pass packet complete from EPA package-plant evidence and Ten States wastewater standards; detailed process-design sources remain weak. |
| `wastewater-energy-island-package` | Task-owned SSC-10 wastewater energy island template now runs as a built-in synthetic task over process oxygen demand, blower load, biogas energy, PV/BESS dispatch, process energy intensity, and feeder voltage drop; real process-model/source-pack parser verification and accepted project evidence remain open. |
| `mechanical-load-feeder-voltage-package` | Task-owned SSC-05 mechanical-load feeder template now runs as a built-in synthetic task over equipment demand, future allowance, power-factor correction, feeder current, cable ampacity, breaker continuous loading, and voltage drop; real SLD/load-schedule/cable/protection source-pack parser verification and accepted project evidence remain open. |
| `pv-storage-feeder-package` | First-pass source index and analysis started from NREL/PVWatts/SAM; electrical-code text and feeder examples remain weak. |
| `earthing-arc-flash-package` | First-pass source index and analysis started from IEEE/OSHA metadata; standards text and real study artifacts remain weak. |
| `rail-braking-signalling-package` | First-pass source index and analysis started from RSSB metadata; regional signalling rules remain weak. |
| `level-crossing-warning-backup-power-package` | Task-owned SSC-02 level-crossing warning and backup-power template now runs as a built-in synthetic task over warning time, strike-in distance, signal load, battery/UPS capacity, DC feeder voltage drop, and fiber link margin; real signal-plan/source-pack parser verification and accepted project evidence remain open. |
| `lighting-visual-its-cctv-communications-package` | Task-owned SSC-13 road visual operations source pack exists and now maps to the runnable `road-visual-operations-package` composite template; source-pack parser/formula verification remains open. |
| `ground-structural-electrical-safety-package` | Task-owned SSC-07 ground structural-electrical safety template now runs as a built-in synthetic task over SPT/CPT interpretation, bearing capacity, and separate earthing-grid/GPR checks; real source-pack parser/formula verification and accepted project evidence remain open. |
| `road-low-point-resilience-package` | Task-owned SSC-01 road low-point resilience template now runs as a built-in synthetic task over runoff, gutter spread, inlet/HGL, cabinet flood freeboard, VMS readability, network headroom, and battery runtime; real source-pack parser/formula verification and accepted project evidence remain open. |
| `pipe-transient-support-foundation-package` | Task-owned SSC-14 pipe transient support and foundation template now runs as a built-in synthetic task over bend thrust, support dead load, Terzaghi bearing capacity, eccentric bearing pressure, anchor shear, and sliding margin; real source-pack parser/formula verification and accepted project evidence remain open. |
| `pump-transient-protection-package` | Task-owned SSC-11 pump transient protection template now runs as a built-in synthetic task over wave speed, Joukowsky pressure rise, pump head, bend transient thrust, support vertical load, high-high trip margin, MAWP margin, and utilization checks; real source-pack parser/formula verification and accepted project evidence remain open. |
| `construction-stage-controls-package` | Task-owned SSC-16 construction-stage controls template now runs as a built-in synthetic task over stormwater, TTC, monitoring power/data, and inspection timing; real source-pack parser/formula verification and accepted project evidence remain open. |
| `acoustic-receiver-impact-package` | Task-owned SSC-12 acoustic receiver impact template now runs as a built-in synthetic task over octave-band attenuation, A-weighted receiver level, background addition, criterion margin, and vibration isolation; real source-pack parser/formula verification and accepted project evidence remain open. |
| `control-loop-signal-package` | Task-owned SSC-18 control-loop signal template now runs as a built-in synthetic task over valve Cv, 4-20 mA scaling, alarm/trip current conversion, and loop headroom; real source-pack parser/formula verification and accepted project evidence remain open. |
| `stormwater-pumping-outage-resilience-package` | Task-owned SSC-17 stormwater pumping outage resilience template now runs as a built-in synthetic task over storm inflow/storage, pump power, BESS/generator backup energy, feeder voltage drop, and outage pass/fail margins; real source-pack parser/formula verification and accepted project evidence remain open. |
| `pump-station-duty-power-npsh-feeder-package` | Task-owned SSC-06 pump station duty template now runs as a built-in synthetic task over rising-main headloss, pump curve head margin, motor power, NPSH margin, and feeder voltage drop; real source-pack parser/formula verification and accepted project evidence remain open. |

See `evidence-matrix.md` for the current cross-task confidence view and next-source priorities.

## Source Confidence Labels

- `primary-open`: official source with useful public text or downloadable manual.
- `primary-gated`: official standard or code landing page, but full text is paywalled or unavailable.
- `government-manual`: public agency manual or guidance.
- `industry-practice`: manufacturer, professional body, or trade guidance.
- `secondary`: encyclopedia, summary article, or academic paper used only to orient the search.
- `example-artifact`: real report, model, calculation, drawing, or dataset that resembles task inputs/outputs.
