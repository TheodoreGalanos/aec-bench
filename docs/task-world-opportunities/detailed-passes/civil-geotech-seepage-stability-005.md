# ABOUTME: Detailed task-world review for civil seepage, slope-stability, and retaining-wall tasks.
# ABOUTME: Records multimodal, composition, and meta-harness opportunities for the fifth civil slice.

# Civil Geotechnical Seepage And Stability Pass 005

Review date: 2026-06-28

Reviewed task cards:

- `civil/seepage-analysis/exit-gradient`
- `civil/seepage-analysis/uplift-pressure`
- `civil/slope-stability/fos-steady-state`
- `civil/slope-stability/fos-seismic`
- `civil/slope-stability/fos-rapid-drawdown`
- `civil/slope-stability/lateral-earth-pressure`
- `civil/slope-stability/retaining-wall-stability`

Source files read for this pass:

- `src/aec_bench/templates/builtin/civil/exit_gradient/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/civil/uplift_pressure/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/civil/fos_steady_state/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/civil/fos_seismic/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/civil/fos_rapid_drawdown/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/civil/lateral_earth_pressure/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/civil/retaining_wall_stability/{params.toml,instruction.md,engine.py}`

## Slice Read

This slice is a civil geotechnical and dam-safety package: seepage, uplift, slope stability under steady-state/drawdown/seismic cases, lateral earth pressure, and gravity retaining-wall external stability.

Compared with the earlier stormwater, coastal, and road geometry slices, this family is dominated by three task-world concerns:

- water state: headwater, tailwater, phreatic line, drain relief, reservoir drawdown, water table, and pore pressure;
- material provenance: soil type, unit weight, void ratio, cohesion, friction angle, interface friction, and foundation properties;
- decomposition discipline: a model must keep forces, stresses, moments, and branch decisions consistent across intermediate calculations.

These tasks are strong candidates for multimodal expansion because real engineering evidence is rarely a neat scalar table. The natural source pack is a dam or retaining-wall section, borehole/lab/property tables, operating level records, water table or phreatic surface notes, seismic hazard coefficients, and surcharge/context plans.

This pass also found a possible consistency repair candidate in `retaining-wall-stability`: the instruction text says the outside-middle-third base-pressure branch uses `q_max = V / (3 * x_resultant)`, while the engine uses `q_max = 2V / (3 * distance_to_near_edge)`. Before expanding that task into multimodal variants, the instruction/verifier/engine contract should be audited so the richer task world does not preserve an ambiguous bearing-pressure rule.

## Task 1: Exit Gradient

Current world:

- Computes exit gradient, critical gradient, factor of safety against piping, saturated unit weight, and buoyant unit weight.
- Inputs are head difference, seepage path length, specific gravity, void ratio, and foundation soil type.
- Hard mode hides specific gravity, void ratio, and foundation soil type.
- The engine uses `i_exit = delta_h / L`, `i_cr = (G_s - 1) / (1 + e)`, `FoS = i_cr / i_exit`, and standard saturated/buoyant unit-weight formulas.
- Soil type is validated against a small table, but the engine uses the provided numeric `G_s` and `e` in the final computation.

Multimodal expansion:

- Best first modality: dam/foundation cross-section or seepage control detail.
- A section can expose upstream and downstream levels, cutoff geometry, seepage path, sheet pile embedment, and downstream toe location.
- A geotechnical table or borehole log can expose soil type, `G_s`, and void ratio ranges.
- A flow-net artifact would be especially useful if we later move beyond the current direct-gradient simplification.

Requirements:

- Source artifact for head difference and seepage path length, with datum and chainage/section labels.
- Soil-property source for specific gravity, void ratio, and soil type.
- Evidence record that distinguishes inferred archetype defaults from explicitly provided lab data.
- Compliance threshold context for permanent dam, levee, or temporary works if a pass/fail output is added.

Harness opportunities:

- Add source-geometry gate for seepage path extraction.
- Add source-authority gate for soil-property inference.
- Add construction gates for exit gradient, critical gradient, and unit weights.
- Add compliance gate for factor of safety against a declared threshold.
- Add contradiction event if the selected soil type and numeric `G_s`/`e` values disagree with the cited source row.

Natural products:

- `exit-gradient -> uplift-pressure` in a dam foundation seepage package.
- `exit-gradient -> fos-steady-state` when seepage conditions inform slope stability.
- `exit-gradient -> retaining-wall/lateral-earth-pressure` where groundwater and piping concerns govern temporary excavations or cofferdams.

Meta-harness handles:

- `projection`: text-only scalar task, cross-section source task, flow-net source task, lab-table source task.
- `difference`: hide soil properties or remove explicit seepage path labels.
- `product`: dam seepage safety package with uplift and embankment stability checks.

## Task 2: Uplift Pressure

Current world:

- Computes upstream pressure, drain-line pressure, downstream pressure, and total uplift force per unit dam length.
- Inputs are headwater depth, tailwater depth, base width, drain distance from upstream face, and drain efficiency percentage.
- Hard mode hides drain efficiency.
- The engine uses a bilinear uplift pressure distribution and trapezoidal integration across the base.
- Drain efficiency is supplied as a percentage but converted internally to a fraction.

Multimodal expansion:

- Best first modality: concrete gravity dam section with drain gallery or drain line detail.
- Operating level tables can provide headwater and tailwater depths.
- A drainage gallery inspection note can support drain-efficiency assumptions.
- A generated pressure diagram could become an output artifact checked against the numeric integration.

Requirements:

- Dam section with base width, upstream/downstream faces, drain line location, and foundation contact line.
- Headwater/tailwater source with clear datum.
- Drain-efficiency source or assumption record tied to structure type and maintenance condition.
- Pressure-distribution sidecar with upstream, drain, and downstream ordinate values.

Harness opportunities:

- Add geometry gate that drain distance is inside the base width.
- Add source-authority gate for drain efficiency.
- Add unit gate for percent-to-fraction conversion.
- Add pressure-shape gate: drain pressure must sit between headwater and tailwater pressure according to efficiency.
- Add artifact gate if a pressure diagram is requested.

Natural products:

- `uplift-pressure -> retaining-wall-stability` style force/moment products for gravity structures if a dam stability task is added.
- `uplift-pressure -> exit-gradient` through shared headwater/tailwater and foundation seepage context.
- `uplift-pressure -> spillway/weir/freeboard` in dam safety packages where operating levels drive both hydraulic and structural checks.

Meta-harness handles:

- `projection`: operating-level table, dam section, drain-gallery detail, pressure diagram.
- `difference`: hide drain efficiency or obscure drain maintenance state.
- `product`: gravity dam stability package with seepage, uplift, and overtopping/freeboard checks.

## Task 3: Factor Of Safety Under Steady-State Seepage

Current world:

- Computes factor of safety, driving stress, and resisting stress for an infinite slope under steady-state seepage.
- Inputs are slope angle, failure depth, cohesion, friction angle, saturated unit weight, and pore pressure ratio.
- Hard mode hides cohesion, friction angle, and saturated unit weight.
- The engine computes pore pressure as `ru * gamma_sat * z`, driving stress as `gamma_sat * z * sin(beta) * cos(beta)`, and resistance as `c' + sigma'_n * tan(phi')`.
- The instruction notes a minimum FoS of 1.5 for steady-state seepage, but the current output remains numeric rather than an explicit compliance decision.

Multimodal expansion:

- Best first modality: embankment zoning section plus material-property table.
- A phreatic surface or seepage analysis profile can provide pore pressure ratio context.
- A dam safety note can identify the relevant material zone and failure depth.

Requirements:

- Embankment section with slope angle, material zones, and selected failure surface depth.
- Material source for `c'`, `phi'`, and saturated unit weight.
- Pore pressure ratio source or derived evidence from phreatic line/seepage analysis.
- Compliance threshold record for the selected loading condition.

Harness opportunities:

- Add source-geometry gate for slope angle and failure depth.
- Add material-source gate for hidden properties.
- Add construction gates for pore pressure, driving stress, effective normal stress, and resisting stress.
- Add compliance gate for `FoS >= 1.5` or an explicitly declared project threshold.
- Add event trigger when a model uses dry/infinite-slope formulas while `ru > 0`.

Natural products:

- `fos-steady-state -> fos-rapid-drawdown` using the same upstream slope and material properties under a changed reservoir state.
- `fos-steady-state -> fos-seismic` as a static-to-pseudo-static scenario portfolio.
- `exit-gradient/uplift-pressure -> fos-steady-state` in a dam seepage-and-stability package.

Meta-harness handles:

- `projection`: material table, embankment section, phreatic surface profile, calculation sheet.
- `difference`: hide material properties or remove the explicit pore pressure ratio source.
- `product`: embankment stability scenario set with shared geometry and material state.

## Task 4: Factor Of Safety Under Seismic Loading

Current world:

- Computes pseudo-static seismic factor of safety, yield acceleration, and yield ratio for an infinite slope.
- Inputs are slope angle, slip depth, cohesion, friction angle, unit weight, pore pressure ratio, horizontal seismic coefficient, and vertical seismic coefficient.
- Hard mode hides cohesion, friction angle, and unit weight.
- The engine treats vertical seismic coefficient as upward and conservative, reducing effective weight.
- If `kh = 0`, the engine returns infinite yield ratio.

Multimodal expansion:

- Best first modality: slope section plus seismic design criteria table.
- A site hazard note can provide `kh` and `kv`; a dam or road embankment section provides geometry.
- A pore-pressure or groundwater source can connect the seismic check to the steady-state case.

Requirements:

- Source for slope angle and slip depth.
- Material-property table for `c'`, `phi'`, and unit weight.
- Seismic hazard/design-coefficient source for `kh` and `kv`, including whether `kv` is considered.
- Evidence record for upward vertical coefficient convention and yield acceleration calculation.

Harness opportunities:

- Add source-authority gate for seismic coefficients.
- Add branch gate for `kv` omitted versus explicitly supplied.
- Add construction gates for driving stress, effective normal stress, pore pressure, resisting stress, and yield acceleration.
- Add yield-ratio gate that handles `kh = 0` deliberately rather than accidentally.
- Add compliance gate for pseudo-static FoS and `ky / kh`.

Natural products:

- `fos-steady-state -> fos-seismic` as a base/static and seismic case pair.
- `fos-seismic -> vertical-curve/road-rail` only indirectly where transport embankments share alignment and geotechnical data.
- `fos-seismic -> retaining-wall-stability` in a future seismic retaining-wall product if active pressure and inertial effects are added.

Meta-harness handles:

- `projection`: seismic criteria table, slope section, material table, hazard note.
- `difference`: hide material properties, hide `kv`, or remove the coefficient source label.
- `product`: scenario portfolio across normal, drawdown, and earthquake loading.

## Task 5: Factor Of Safety During Rapid Drawdown

Current world:

- Computes factor of safety before drawdown, factor of safety after drawdown, drawdown ratio, and undrained pore pressure.
- Inputs are upstream slope angle, slip depth, cohesion, friction angle, saturated unit weight, initial reservoir level, and final reservoir level.
- Hard mode hides cohesion, friction angle, and saturated unit weight.
- The engine uses buoyant unit weight before drawdown and full saturated unit weight for post-drawdown driving shear.
- The drawdown ratio is `(initial - final) / initial`; final level must be below initial level.

Multimodal expansion:

- Best first modality: reservoir operation hydrograph plus upstream embankment section.
- A drawdown event table can provide initial/final levels and elapsed time.
- A material/permeability note can justify whether the drawdown is rapid enough for undrained pore pressures.

Requirements:

- Upstream slope section with slope angle and slip-surface depth.
- Reservoir level record with initial and final water levels on a consistent datum.
- Material-property source for `c'`, `phi'`, and saturated unit weight.
- Scenario label distinguishing slow drawdown, rapid drawdown, and normal steady-state checks.

Harness opportunities:

- Add scenario-state gate for before/after drawdown.
- Add geometry/source gate for initial and final reservoir levels.
- Add construction gate for `gamma_sub = gamma_sat - gamma_w`.
- Add event trigger if the model incorrectly reduces post-drawdown driving stress using buoyant unit weight.
- Add compliance gate for the rapid-drawdown FoS threshold selected by the task context.

Natural products:

- `fos-steady-state -> fos-rapid-drawdown` with shared geometry/materials and changed water boundary condition.
- `fos-rapid-drawdown -> spillway/freeboard` in reservoir operation packages where flood surcharge and drawdown both matter.
- `fos-rapid-drawdown -> exit-gradient` where drawdown or reservoir operation changes seepage gradients.

Meta-harness handles:

- `projection`: reservoir-level record, embankment section, material table, event scenario note.
- `difference`: hide material properties or remove explicit rapid/slow drawdown labels.
- `product`: dam operation scenario suite with normal, drawdown, and seismic checks.

## Task 6: Lateral Earth Pressure

Current world:

- Computes Rankine active/passive coefficients, active force, passive force, active overturning moment, and hydrostatic water force.
- Inputs are wall height, friction angle, cohesion, unit weight, surcharge, water table depth, and backfill slope.
- Hard mode hides friction angle and unit weight.
- The engine supports horizontal or sloping backfill, water-table effects, surcharge, cohesion reduction, passive force, and active force clamping if cohesion dominates.
- Water pressure is computed separately and is not multiplied by `Ka`.

Multimodal expansion:

- Best first modality: retaining-wall section plus geotechnical report extract.
- A section can expose wall height, backfill slope, water table depth, and retained geometry.
- A surcharge/load plan can expose traffic, storage, building, or rail loads behind the wall.
- A borehole or lab table can expose unit weight, cohesion, and friction angle.

Requirements:

- Wall section with height, retained face, ground line, backfill slope, and water table.
- Soil-property source for friction angle, cohesion, and unit weight.
- Surcharge source and load footprint, especially if the surcharge should be treated as uniform.
- Decomposed pressure-resultant evidence for soil, surcharge, cohesion, and water components.

Harness opportunities:

- Add water-table regime gate: no water, partial submergence, or water table at ground.
- Add source-authority gate for soil properties and surcharge.
- Add branch gate for inclined-backfill coefficient versus horizontal Rankine coefficient.
- Add construction gate that hydrostatic force is independent of `Ka`.
- Add active-force clamp gate where cohesion would otherwise produce negative active pressure.

Natural products:

- `lateral-earth-pressure -> retaining-wall-stability` as the direct pressure-to-stability handoff.
- `ground/lateral-earth-pressure -> civil/retaining-wall-stability` as a cross-discipline comparison once the ground duplicate is reviewed.
- `lateral-earth-pressure -> drainage/downpipe/outfall` where groundwater control or weep-hole drainage changes the retained-water case.

Meta-harness handles:

- `projection`: wall section, surcharge plan, water table record, material table.
- `difference`: hide friction angle/unit weight or remove water-table labels.
- `product`: retaining-wall external stability package.

## Task 7: Retaining Wall Stability

Current world:

- Computes Rankine `Ka`, sliding FoS, overturning FoS, bearing FoS, eccentricity, and maximum base pressure for a rectangular gravity retaining wall.
- Inputs include wall geometry, concrete unit weight, backfill properties, surcharge, foundation properties, and base friction ratio.
- Hard mode hides backfill friction angle, backfill unit weight, foundation friction angle, and foundation cohesion.
- The engine assumes the stem is at the front/toe side, with backfill soil sitting on the heel portion behind the stem.
- The engine decomposes active force, vertical weights, stabilising moments, overturning moments, sliding resistance, eccentricity, base pressure, effective bearing width, and Terzaghi bearing capacity.

Multimodal expansion:

- Best first modality: retaining-wall section with toe/heel orientation and retained ground surface.
- A construction detail can expose concrete dimensions and material unit weight.
- A geotechnical report can expose backfill and foundation properties.
- A loading plan can expose surcharge and whether it acts over the heel.

Requirements:

- Wall cross-section with height, base width, stem thickness, toe, heel, and backfill side clearly labeled.
- Material/source table for concrete, backfill, and foundation properties.
- Surcharge source and footprint relative to heel width.
- Stability decomposition record: active pressure components, vertical forces, moment arms, sliding resistance, eccentricity, base pressure branch, and bearing capacity factors.
- Instruction/engine audit for the outside-middle-third base-pressure branch before producing harder variants.

Harness opportunities:

- Add geometry-orientation gate for toe/heel and heel width.
- Add force/moment decomposition gates for wall weight, soil weight, surcharge weight, active soil pressure, active surcharge pressure, and cohesion reduction.
- Add sliding gate for interface friction `delta` and base adhesion.
- Add bearing branch gate for middle-third versus partial-base compression.
- Add verifier repair target for the instruction/engine eccentricity branch mismatch.
- Add product-world gate that lateral-earth-pressure output fields match retaining-wall active-pressure assumptions if the tasks are composed.

Natural products:

- `lateral-earth-pressure -> retaining-wall-stability` as a two-stage external stability workflow.
- `retaining-wall-stability -> structural concrete/member checks` if structural wall design tasks are added or combined.
- `retaining-wall-stability -> drainage/water-table tasks` where seepage relief, weep holes, or groundwater control changes the active force.
- `retaining-wall-stability -> ground/foundation-bearing tasks` once ground foundation tasks are reviewed.

Meta-harness handles:

- `projection`: wall section, geotechnical report table, surcharge plan, calculation sheet.
- `difference`: hide soil/foundation properties, remove toe/heel labels, or suppress intermediate force decomposition.
- `product`: retaining-wall design package with pressure, stability, drainage, and future structural member checks.

## Cross-Slice Threads Opened

The main cross-slice bridge from this pass is between hydraulic boundary conditions and geotechnical stability. Earlier civil water tasks produce levels, flows, tailwater conditions, and basin/reservoir operating states. This slice consumes those states as head differences, pore pressure ratios, water table depths, drain relief assumptions, and drawdown scenarios.

The strongest next product worlds are:

- dam foundation seepage package: `exit-gradient`, `uplift-pressure`, and future gravity dam stability checks;
- embankment scenario portfolio: `fos-steady-state`, `fos-rapid-drawdown`, and `fos-seismic` sharing one section and material table;
- retaining-wall external stability package: `lateral-earth-pressure` feeding `retaining-wall-stability`;
- civil-ground interface package: civil retaining-wall tasks compared with the ground discipline's broader lateral-earth-pressure template.

## Meta-Harness Implications

For these tasks, a practical meta-harness pass should treat hidden-parameter inference as a first-class operation rather than a prompt trick. The task-world sidecar should declare:

- which source artifact supplies each soil or hydraulic state parameter;
- whether a parameter is explicit, inferred from archetype, or calculated from another source;
- which branch decisions were made before the final number;
- which intermediate values must close for the final answer to be considered trustworthy.

The best event candidates are:

- soil-property source disagreement;
- water-state regime error;
- wrong pore-pressure or unit-weight state;
- pressure or moment component omitted;
- incorrect clamp/branch behavior;
- instruction/engine/verifier inconsistency in bearing-pressure logic.
