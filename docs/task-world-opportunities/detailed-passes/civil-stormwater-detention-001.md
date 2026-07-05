# ABOUTME: Detailed task-world review for the first civil stormwater and detention slice.
# ABOUTME: Analyzes multimodal expansion, task products, and meta-harness settings task by task.

# Civil Stormwater And Detention Pass 001

Review date: 2026-06-28

Reviewed task cards:

- `civil/hydrologic-calculations/rational-method`
- `civil/hydrologic-calculations/scs-curve-number`
- `civil/detention-design/detention-volume-preliminary`
- `civil/detention-design/orifice-outlet-design`
- `civil/detention-design/weir-outlet-design`
- `civil/stormwater-piped/pipe-invert-calculation`
- `civil/stormwater-piped/hgl-check`

Source files read for this pass:

- `src/aec_bench/templates/builtin/civil/rational_method/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/civil/scs_curve_number/{instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/civil/detention_volume_preliminary/{params.toml,engine.py}`
- `src/aec_bench/templates/builtin/civil/orifice_outlet_design/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/civil/weir_outlet_design/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/civil/pipe_invert_calculation/{params.toml,engine.py}`
- `src/aec_bench/templates/builtin/civil/hgl_check/{params.toml,instruction.md,engine.py}`

## Slice Read

This group is a strong first candidate for multimodal and product-world work because it already has a natural engineering story:

1. Estimate runoff from catchment and rainfall.
2. Size preliminary detention storage against an allowable release rate.
3. Size low-flow and overflow outlet controls.
4. Check pipe invert/cover and hydraulic grade line for conveyance.

The current templates are scalar and deterministic, which is good for closure. The missing layer is evidence: catchment areas, curve numbers, release limits, basin heads, pipe materials, pit losses, and cover requirements are exactly the values that real projects derive from plans, maps, tables, design briefs, or standards notes.

## Task 1: Rational Method

Current world:

- Computes `Q = C * I * A / 360` and reports `peak_runoff_m3_s` and `peak_runoff_l_s`.
- The hard mode hides `runoff_coefficient`; the prompt replaces it with a site description.
- The engine validates `0 <= C <= 1`, positive rainfall intensity, positive area, and the 80 ha rational-method limit.

Multimodal expansion:

- Best first modality: catchment plan plus rainfall table.
- The plan can expose catchment boundary and surface mix; the table can expose design rainfall intensity.
- The hidden `runoff_coefficient` becomes a source-interpretation task rather than a scalar omission.
- A harder variant can provide a site plan with roofs, pavement, landscape, and road reserves, requiring weighted runoff coefficient selection.

Requirements:

- Generated plan artifact with known polygon areas by surface class.
- Rainfall table or IDF excerpt with duration/AEP row selection.
- Source-to-parameter trace: `catchment_area_ha`, `rainfall_intensity_mm_hr`, `runoff_coefficient`.
- Intermediate evidence gate for unit conversion from area and rainfall intensity.

Harness opportunities:

- Keep the engine as arithmetic oracle, but add a construction gate requiring the model to name the selected surface classes and coefficient basis.
- Add a contradiction check where final `Q` can be numerically correct only if the recorded `C`, `I`, and `A` match source evidence.
- Add a modality projection handle: text-only, table-source, plan-source, plan-plus-table.

Natural products:

- `rational-method -> detention-volume-preliminary` using `peak_runoff_m3_s` as `post_dev_peak_flow_m3_s`.
- `rational-method -> hgl-check` using peak flow as pipe reach design flow.
- `rational-method -> pollutant-load-estimate` if runoff is extended to annual volume or event volume.

Meta-harness handles:

- `projection`: arithmetic-only versus source-interpretation.
- `difference`: remove explicit `C`, then remove explicit catchment area, then remove explicit rainfall intensity.
- `product`: compose with detention or pipe checks.

## Task 2: SCS Curve Number

Current world:

- Computes retention `S`, abstraction `Ia`, and runoff depth `Q` from rainfall depth and curve number.
- The instruction exposes the standard equations and asks for a JSON block.
- The engine has a branch: runoff is zero when rainfall depth does not exceed initial abstraction.

Multimodal expansion:

- Best first modality: soil/land-use table plus rainfall depth source.
- A richer version can use a catchment map with hydrologic soil groups and land-cover zones.
- The curve number should be derived from land use, soil group, condition, and imperviousness rather than inferred from a one-line archetype.

Requirements:

- Source table mapping land-use/soil-group pairs to curve numbers, ideally embedded in the task world to avoid internet dependency.
- Optional weighted CN calculation for multiple subareas.
- Evidence fields for `rainfall_depth_mm`, selected CN rows, weighted CN, `S`, `Ia`, and branch decision.

Harness opportunities:

- Add a branch construction gate: model must state whether `P > Ia` before computing runoff.
- Add a source-authority gate for the selected CN row.
- Add a product handle that converts runoff depth over catchment area to runoff volume for detention sizing.

Natural products:

- `scs-curve-number -> detention-volume-preliminary` if extended to runoff volume/hydrograph.
- `scs-curve-number -> rational-method` as a comparison world under the same catchment context.
- `scs-curve-number -> sediment-basin-sizing` if storm runoff volume becomes an erosion-control input.

Meta-harness handles:

- `subset`: restrict to single land-use CN or multi-zone weighted CN.
- `difference`: remove the explicit CN and require table selection.
- `product`: combine with rainfall/runoff volume or detention storage worlds.

## Task 3: Detention Volume Preliminary

Current world:

- Estimates detention volume from `post_dev_peak_flow_m3_s`, `allowable_release_rate_m3_s`, `storm_duration_hr`, and `design_depth_m`.
- Computes `required_storage_volume_m3` and `approximate_surface_area_m2`.
- The hard mode hides `allowable_release_rate_m3_s`.
- The engine uses a meaningful branch:
  - no detention if `Q_allow >= Q_post`;
  - triangular minus rectangle when `Q_allow < Q_post / 2`;
  - partial triangular storage when `Q_allow >= Q_post / 2`.

Multimodal expansion:

- Best first modality: council detention requirement extract plus conceptual basin sketch.
- The design depth can come from a basin section; allowable release can come from a pre-development flow table, consent condition, or council policy excerpt.
- A map/table pair can provide post-development and pre-development peak flow alternatives.

Requirements:

- Handoff field from hydrology task: `post_dev_peak_flow_m3_s`.
- Source artifact for allowable release rate.
- Branch evidence record with selected case and why.
- Optional basin geometry artifact if `approximate_surface_area_m2` becomes a layout/footprint check.

Harness opportunities:

- Add a construction gate for branch selection before final volume.
- Add a product-world closure gate that the input `post_dev_peak_flow_m3_s` equals the upstream hydrology output.
- Add an artifact-production variant requiring a small detention design record with `source_flows`, `branch_case`, `storage`, and `surface_area`.

Natural products:

- Upstream: rational method or SCS-derived hydrograph.
- Downstream: orifice outlet design, weir outlet design, pipe invert, HGL, and flood/freeboard checks.

Meta-harness handles:

- `projection`: arithmetic branch world, source-authority world, basin-geometry world.
- `difference`: remove allowable release rate, then remove design depth.
- `product`: combine with outlet sizing and conveyance checks.

## Task 4: Orifice Outlet Design

Current world:

- Sizes circular orifice area, diameter, and velocity using `Q = Cd * A * sqrt(2gH)`.
- Hard mode hides both `discharge_coefficient` and `head_above_centreline_m`.
- The instruction supplies default `Cd = 0.61` when absent, but hard mode can hide the true sampled coefficient.

Multimodal expansion:

- Best first modality: basin outlet section or control structure detail.
- The head above centreline is geometric and should be read from a section/elevation drawing.
- The discharge coefficient can come from a detail note, device type, or embedded coefficient table.

Requirements:

- Generated section drawing with water level, orifice centreline, invert, and dimensions.
- Source table or note for `Cd`, with default-policy clarity.
- Geometry extraction verifier for head and a numerical verifier for final area/diameter.

Harness opportunities:

- Add a source geometry gate for `head_above_centreline_m`.
- Add a source-authority gate for `discharge_coefficient`.
- Add a contradiction event if the model uses default `Cd = 0.61` while the source artifact states a different coefficient.

Natural products:

- `detention-volume-preliminary -> orifice-outlet-design` using allowable release or target discharge as `design_flow_m3_s`.
- `orifice-outlet-design -> hgl-check` if the outlet feeds a downstream pipe reach.
- `orifice-outlet-design + weir-outlet-design` as normal/emergency outlet pair under one basin drawing.

Meta-harness handles:

- `projection`: geometry-only versus coefficient/source-table versus final sizing.
- `difference`: remove head, remove coefficient, remove both while preserving source drawing.
- `product`: normal outlet plus detention storage, or normal outlet plus emergency weir.

## Task 5: Weir Outlet Design

Current world:

- Sizes sharp-crested rectangular weir crest length and unit discharge using the Francis formula.
- Hard mode hides `discharge_coefficient` and `head_over_weir_m`; `number_of_contractions` is optional and derivable from archetype but not in hard hidden params.
- The engine computes `Cw = Cd * sqrt(2g)` and adjusts crest length for end contractions.

Multimodal expansion:

- Best first modality: emergency spillway detail or basin overflow section.
- The drawing can expose head over crest, suppressed versus contracted weir, and crest length constraints.
- A table or note can expose `Cd` and contraction assumptions.

Requirements:

- Weir section/elevation artifact with crest, design water level, sidewalls, and contraction condition.
- Source-to-parameter trace for head, coefficient, and number of contractions.
- Optional layout constraint if the required crest length must fit within a basin embankment.

Harness opportunities:

- Add an explicit end-contraction construction gate; current hard mode hides head and coefficient but the contraction assumption can still be a subtle failure.
- Add a geometric feasibility artifact: required length versus available crest length.
- Add an event trigger for formula-regime mismatch, for example using orifice logic on a weir or ignoring contractions.

Natural products:

- `detention-volume-preliminary -> weir-outlet-design` for emergency overflow design flow.
- `orifice-outlet-design + weir-outlet-design` as a combined outlet-control package.
- `weir-outlet-design -> freeboard-calculation` if overflow head/freeboard is added.

Meta-harness handles:

- `projection`: geometry interpretation, coefficient authority, contraction assumption, final sizing.
- `difference`: remove head and coefficient; later remove contraction information.
- `product`: emergency spillway paired with storage/freeboard worlds.

## Task 6: Pipe Invert Calculation

Current world:

- Computes downstream invert, obvert, cover depth, grade fall, and cover adequacy.
- Hard mode hides `minimum_cover_mm` and requires inference from installation context.
- The engine is simple but very useful as a geometry handoff: invert, grade, diameter, and cover can be read from or written back to drawings.

Multimodal expansion:

- Best first modality: pipe long section or drainage schedule.
- A second modality is a standards/local authority cover table.
- A richer task asks the model to detect whether a proposed pipe conflicts with cover requirements under road, verge, or trunk-main contexts.

Requirements:

- Long-section drawing with upstream invert, pipe length, grade, diameter, downstream surface.
- Embedded cover-requirement table keyed by installation context.
- Artifact output containing computed downstream invert and cover check, suitable for a drawing markup or design table.

Harness opportunities:

- Add geometry extraction gates for invert, grade, length, diameter, and surface level.
- Add source-authority gate for minimum cover.
- Add a design-writeback variant where the model must produce a drainage schedule row.

Natural products:

- `pipe-invert-calculation -> hgl-check` using pipe diameter/length and possibly levels.
- `rational-method -> pipe-invert-calculation` via pipe sizing or flow-based diameter selection if a sizing step is added.
- `pipe-invert-calculation -> driveway/road geometry` when cover depends on road crossfall/profile context.

Meta-harness handles:

- `projection`: geometry extraction versus compliance check.
- `difference`: remove cover requirement or drawing labels.
- `product`: pair with HGL check for a pipe reach design world.

## Task 7: HGL Check

Current world:

- Computes velocity, friction loss, pit loss, upstream HGL, clearance, surcharge ratio, and pass/fail.
- Hard mode hides `mannings_n` and `pit_loss_coefficient` from pipe/junction description.
- The engine assumes full-pipe flow for a single reach and uses a pass/fail threshold based on minimum clearance.

Multimodal expansion:

- Best first modality: drainage long section plus pit/junction detail.
- Manning's `n` can come from pipe material; pit loss coefficient can come from junction geometry or embedded lookup table.
- A richer version can include downstream tailwater source and surface levels from a long section.

Requirements:

- Pipe reach drawing/schedule with diameter, length, material, pit type, downstream HGL, and upstream surface level.
- Embedded table for Manning roughness and pit loss coefficients.
- Evidence record for full-pipe assumption, velocity, friction slope, pit loss, HGL, clearance, and pass/fail.

Harness opportunities:

- Add intermediate construction gates for area, hydraulic radius, velocity, friction slope, and pit loss.
- Add a contradiction check where pass/fail must agree with clearance and minimum clearance.
- Add a product-world handoff from hydrology flow and pipe invert geometry.

Natural products:

- `rational-method -> hgl-check` for design flow.
- `pipe-invert-calculation -> hgl-check` for pipe reach geometry.
- `hgl-check -> detention/outlet redesign` if surcharging indicates a downstream constraint.

Meta-harness handles:

- `projection`: hydraulics calculation, coefficient source selection, compliance decision.
- `difference`: hide roughness and pit loss; later hide tailwater or surface levels in drawings.
- `product`: compose with hydrology and pipe invert as a complete reach check.

## Cross-Task Product Worlds

### Product World A: Text Baseline Drainage Chain

Inputs stay scalar. Handoffs are explicit JSON fields.

1. `rational-method` computes `peak_runoff_m3_s`.
2. `detention-volume-preliminary` consumes that as `post_dev_peak_flow_m3_s`.
3. `orifice-outlet-design` consumes allowable release as `design_flow_m3_s`.
4. `weir-outlet-design` consumes emergency design overflow.
5. `pipe-invert-calculation` and `hgl-check` verify a selected downstream reach.

Useful because it tests multi-step arithmetic and handoff discipline without multimodal complexity.

### Product World B: Multimodal Basin Package

One source pack contains:

- Catchment plan.
- Rainfall/flow table.
- Council allowable-release note.
- Basin section with orifice and weir geometry.
- Drainage long section.

The model must produce a design record, not just final numbers. The verifier checks source extraction, arithmetic outputs, branch decisions, and handoff consistency.

### Product World C: Meta-Harness Repair Scenario

Start with a baseline world where final numeric scoring exists. Add an agentic review stage that can identify:

- correct final number but wrong source interpretation;
- correct hydrology but wrong detention branch;
- correct outlet formula but wrong head read from drawing;
- correct HGL arithmetic but pass/fail contradiction.

The meta-harness pass should propose whether to repair `generator`, `verifier`, `world_schema`, or `evidence_profile`.

## Initial Combination Findings

| Candidate | Product Axis | Handoff Fields | Main New Evidence |
| --- | --- | --- | --- |
| Rational method to detention | `hydrology_to_storage` | `peak_runoff_m3_s -> post_dev_peak_flow_m3_s` | Catchment plan, rainfall table, flow handoff record. |
| SCS to detention | `runoff_depth_to_storage` | `runoff_depth_mm`, catchment area, hydrograph assumption | CN table/map and runoff volume/hydrograph derivation. |
| Detention to orifice | `storage_to_low_flow_control` | `allowable_release_rate_m3_s -> design_flow_m3_s` | Council release note, basin section head. |
| Detention to weir | `storage_to_overflow_control` | overflow design flow, head over crest | Spillway section and contraction assumption. |
| Pipe invert to HGL | `geometry_to_hydraulics` | diameter, length, possibly levels | Long section, pipe material, pit detail. |
| Rational method to HGL | `hydrology_to_conveyance` | `peak_runoff_m3_s -> design_flow_m3_per_s` | Flow handoff record and reach geometry. |

## Meta-Harness Follow-Ups

Add operation handles to future explicit world sidecars:

- `source_artifacts.catchment_plan`
- `source_artifacts.rainfall_table`
- `source_artifacts.council_release_note`
- `source_artifacts.basin_section`
- `source_artifacts.pipe_long_section`
- `handoffs.peak_flow`
- `handoffs.allowable_release`
- `handoffs.pipe_geometry`
- `branch_decisions.detention_case`
- `compliance.clearance_pass_fail`

Add closure and construction gates:

- upstream task output equals downstream task input within declared units;
- branch decision is stated and matches sampled parameters;
- final pass/fail matches computed clearance and threshold;
- source-derived hidden parameter has a cited source record;
- produced design record contains all required handoff fields.

