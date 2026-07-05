# ABOUTME: Detailed task-world review for ground investigation, foundation, slope, and retaining-wall tasks.
# ABOUTME: Records multimodal, composition, and meta-harness opportunities for the ground discipline slice.

# Ground Site Foundation And Retaining Pass 008

Review date: 2026-06-28

Reviewed task cards:

- `ground/soil-interpretation/spt-corrections`
- `ground/soil-interpretation/cpt-parameter-derivation`
- `ground/shallow-foundations/terzaghi-bearing-capacity`
- `ground/shallow-foundations/meyerhof-bearing-capacity`
- `ground/shallow-foundations/immediate-settlement`
- `ground/shallow-foundations/consolidation-settlement`
- `ground/slope-stability/infinite-slope`
- `ground/retaining-walls/lateral-earth-pressure`
- `ground/retaining-walls/wall-bearing`
- `ground/retaining-walls/wall-overturning`

Source files read for this pass:

- `src/aec_bench/templates/builtin/ground/spt_corrections/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/ground/cpt_parameter_derivation/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/ground/terzaghi_bearing_capacity/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/ground/meyerhof_bearing_capacity/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/ground/immediate_settlement/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/ground/consolidation_settlement/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/ground/infinite_slope/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/ground/lateral_earth_pressure/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/ground/wall_bearing/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/ground/wall_overturning/{params.toml,instruction.md,engine.py}`

## Slice Read

The ground discipline is compact but extremely composable. It has a clear workflow:

- field test interpretation: SPT and CPT records become corrected values or derived soil behavior/strength parameters;
- shallow foundation checks: bearing capacity and settlement consume soil properties, footing geometry, loading, and groundwater state;
- slope and retaining checks: lateral pressure, overturning, and bearing consume the same soil profile and structural wall geometry.

The high-value multimodal artifacts are borehole logs, SPT field sheets, CPT traces, soil profiles, lab summary tables, groundwater records, footing plans, load schedules, retaining-wall sections, and surcharge plans. The numeric engines are deterministic, but the real benchmark opportunity is evidence assembly and handoff integrity.

Two cross-template cautions matter before composing these tasks:

- The civil retaining-wall stability template and the ground retaining-wall templates use different wall-geometry assumptions. Civil `retaining-wall-stability` places the stem at the front/toe side for a rectangular gravity wall, while ground `wall-overturning` models a cantilever L-wall with toe length `B/3` and the stem toward the heel side. Any composed retaining-wall world needs an explicit wall-geometry sidecar.
- Ground `lateral-earth-pressure` supports Rankine and Coulomb theory but does not model water table explicitly, while the civil lateral-earth-pressure template includes water-table effects but is Rankine-only. That creates a useful discipline-interface task, but only if theory and groundwater assumptions are declared.

## Task 1: SPT Corrections

Current world:

- Computes correction factors `CE`, `CB`, `CS`, `CR`, energy-corrected `N60`, overburden correction `CN`, and normalized `(N1)60`.
- Inputs are raw N-value, effective overburden stress, hammer type, borehole diameter, sampler type, and rod length.
- Hard mode hides hammer type, sampler type, and borehole diameter.
- The engine uses lookup tables for energy, borehole diameter, sampler, and rod length corrections.
- The overburden correction is capped at 2.0.

Multimodal expansion:

- Best first modality: SPT field record plus borehole log.
- A field sheet can expose hammer type, sampler configuration, borehole diameter, rod length, and raw blow count.
- A borehole log or interpreted profile can supply effective overburden stress at test depth.

Requirements:

- Field record with equipment and raw N-value.
- Borehole log with depth and groundwater/effective stress context.
- Correction factor table as a source artifact.
- Evidence record for each correction factor before `N60` and `(N1)60`.

Harness opportunities:

- Add equipment-source gates for hammer, borehole, and sampler corrections.
- Add rod-length interval gate.
- Add overburden cap gate for `CN <= 2.0`.
- Add handoff gate from `(N1)60` to future soil-property or liquefaction-style tasks.
- Add contradiction event if the field sheet equipment conflicts with selected correction factors.

Natural products:

- `spt-corrections -> bearing-capacity/settlement` through interpreted density or strength correlations if added.
- `spt-corrections -> cpt-parameter-derivation` as parallel site investigation evidence.
- `spt-corrections -> retaining-wall/slope` through soil property inference.

Meta-harness handles:

- `projection`: SPT field sheet, borehole log, correction-factor table.
- `difference`: hide equipment fields or remove correction-factor labels.
- `product`: site investigation interpretation package.

## Task 2: CPT Parameter Derivation

Current world:

- Derives corrected cone resistance, friction ratio, normalized CPT parameters, soil behavior type index, undrained shear strength, and friction angle.
- Inputs are cone resistance, sleeve friction, pore pressure, depth, unit weight, water table depth, and net area ratio.
- Hard mode hides total unit weight and net area ratio.
- The engine computes total/effective overburden stresses, `Ic`, and then branches at `Ic > 2.6` for clay-like behavior versus sand-like behavior.
- For clay-like behavior it reports `Su` and sets `phi = 0`; for sand-like behavior it reports `phi` and sets `Su = 0`.

Multimodal expansion:

- Best first modality: CPT trace or tabular CPT point record plus groundwater profile.
- A trace can expose `qc`, `fs`, `u2`, and depth.
- A soil profile can expose total unit weight and water table.
- A cone equipment record can expose net area ratio.

Requirements:

- CPT data source at the selected depth.
- Groundwater and unit-weight source for stress calculations.
- Net area ratio source or equipment default record.
- Branch evidence for clay-like versus sand-like interpretation.
- Separate handoff fields for `Su` and `phi`, because only one is nonzero in the current engine branch.

Harness opportunities:

- Add CPT row extraction gate.
- Add stress-state gate for total/effective overburden.
- Add branch gate for `Ic > 2.6`.
- Add source-authority gate for hidden unit weight and net area ratio.
- Add handoff gate into bearing, slope, and retaining tasks with explicit drained/undrained context.

Natural products:

- `cpt-parameter-derivation -> immediate/consolidation settlement` through inferred soil stiffness and clay state if correlations are added.
- `cpt-parameter-derivation -> infinite-slope` through `Su` or `phi`.
- `cpt-parameter-derivation -> bearing-capacity` through strength parameter handoff.

Meta-harness handles:

- `projection`: CPT trace, CPT row table, groundwater profile, equipment record.
- `difference`: hide unit weight, net area ratio, water table, or soil behavior labels.
- `product`: field test to design parameter package.

## Task 3: Terzaghi Bearing Capacity

Current world:

- Computes Terzaghi bearing capacity factors, ultimate bearing capacity, and allowable bearing capacity.
- Inputs are cohesion, friction angle, unit weight, footing width, embedment depth, footing shape, water table depth, and factor of safety.
- Hard mode hides cohesion, friction angle, and unit weight.
- The engine interpolates or computes bearing capacity factors and applies water table correction based on water depth relative to embedment and footing width.
- Shape factors are limited to strip, square, and circular footings.

Multimodal expansion:

- Best first modality: footing plan/section plus soil profile and groundwater table.
- A footing drawing can expose footing shape, width, and embedment depth.
- A geotechnical report can expose soil parameters and water table.
- A design note can expose the factor of safety.

Requirements:

- Footing geometry source.
- Soil parameter source, ideally connected to SPT/CPT/lab evidence.
- Groundwater source for the three water-table cases.
- Bearing-capacity factor table and interpolation trace.
- Allowable capacity record via factor of safety.

Harness opportunities:

- Add footing-shape gate.
- Add water-table correction branch gate.
- Add factor interpolation gate.
- Add source-authority gate for hidden soil properties.
- Add handoff gate into settlement tasks using the same footing and applied pressure context.

Natural products:

- `cpt/spt -> terzaghi-bearing-capacity` through soil property interpretation.
- `terzaghi-bearing-capacity -> immediate-settlement` as capacity plus serviceability.
- `terzaghi-bearing-capacity -> wall-bearing` for shallow foundation versus retaining-wall bearing comparisons.

Meta-harness handles:

- `projection`: footing plan, foundation section, soil profile, groundwater record, factor table.
- `difference`: hide soil properties or water-table labels.
- `product`: shallow foundation capacity package.

## Task 4: Meyerhof Bearing Capacity

Current world:

- Computes Meyerhof bearing factors, shape factors, depth factors, inclination factors, ultimate capacity, and allowable capacity.
- Inputs are cohesion, friction angle, unit weight, footing width/length, embedment depth, footing shape, load inclination, and factor of safety.
- Hard mode hides cohesion, friction angle, and unit weight.
- The engine normalizes footing dimensions so `B` is the shorter dimension.
- Inclination factors reduce capacity for inclined loads; `i_gamma` goes to zero when load inclination exceeds friction angle.

Multimodal expansion:

- Best first modality: foundation plan, load diagram, and soil parameter table.
- A footing plan can expose shape and aspect ratio.
- A structural load schedule or reaction diagram can expose load inclination.
- A geotechnical source can expose soil parameters and factor of safety.

Requirements:

- Footing width, length, shape, embedment, and load inclination sources.
- Soil parameter source.
- Factor table/equation evidence for bearing, shape, depth, and inclination factors.
- Explicit `B <= L` normalization evidence.

Harness opportunities:

- Add footing-aspect-ratio gate.
- Add load-inclination branch gate.
- Add shape/depth/inclination factor gates.
- Add source-authority gate for hidden soil parameters.
- Add comparison gate against Terzaghi for the same foundation where useful.

Natural products:

- `terzaghi-bearing-capacity <-> meyerhof-bearing-capacity` as method-comparison task world.
- `meyerhof-bearing-capacity -> wall-bearing` through shared effective-width/bearing factor logic.
- `meyerhof-bearing-capacity -> structural load combinations` through load inclination and foundation reactions.

Meta-harness handles:

- `projection`: footing plan, load diagram, soil report, factor equations.
- `difference`: hide soil properties, load inclination, or footing-shape labels.
- `product`: foundation bearing method comparison package.

## Task 5: Immediate Settlement

Current world:

- Computes influence factor and elastic immediate settlement.
- Inputs are applied pressure, footing width/length, elastic modulus, Poisson ratio, footing shape, and foundation rigidity.
- Hard mode hides elastic modulus and Poisson ratio.
- The engine interpolates influence factor based on `L/B` for rectangular footings, uses a circular footing factor for circular footings, and applies a rigid-foundation reduction factor.
- Elastic modulus is converted from MPa to kPa before settlement calculation.

Multimodal expansion:

- Best first modality: foundation plan plus geotechnical stiffness table.
- A footing plan can expose width, length, shape, and rigidity assumption.
- A geotechnical report or lab/field correlation table can expose elastic modulus and Poisson ratio.
- A load schedule can expose applied pressure.

Requirements:

- Footing geometry and rigidity source.
- Applied pressure source from structural load or foundation reaction.
- Stiffness/source table for hidden soil properties.
- Influence factor interpolation evidence.
- Settlement output tied to a serviceability threshold if extended.

Harness opportunities:

- Add `L/B` influence interpolation gate.
- Add rigid/flexible branch gate.
- Add MPa-to-kPa conversion gate.
- Add source-authority gate for modulus and Poisson ratio.
- Add product-world gate with bearing capacity using the same footing and soil profile.

Natural products:

- `bearing-capacity -> immediate-settlement` as capacity and serviceability pair.
- `cpt/spt -> immediate-settlement` through stiffness correlation if added.
- `immediate-settlement -> load-combinations` through service load pressure handoff.

Meta-harness handles:

- `projection`: footing plan, load schedule, stiffness table, influence factor table.
- `difference`: hide modulus/Poisson ratio or rigidity labels.
- `product`: shallow foundation serviceability package.

## Task 6: Consolidation Settlement

Current world:

- Computes overconsolidation ratio and primary consolidation settlement.
- Inputs are clay thickness, compression/recompression indices, initial void ratio, preconsolidation pressure, initial effective stress, and final effective stress.
- Hard mode hides compression index, recompression index, and initial void ratio.
- The engine branches between normally consolidated, overconsolidated but remains OC, and overconsolidated becoming NC.
- Settlement is reported in millimetres.

Multimodal expansion:

- Best first modality: soil profile plus oedometer/lab summary table.
- A borehole section can expose clay layer thickness and stress state.
- A lab table can expose `Cc`, `Cr`, `e0`, and preconsolidation pressure.
- A loading schedule can expose final effective stress after foundation construction.

Requirements:

- Clay layer thickness and stress profile source.
- Lab source for compression parameters.
- Load increment/final stress source.
- Branch evidence for NC/OC state.
- Settlement component evidence for two-part OC-to-NC case.

Harness opportunities:

- Add OCR branch gate.
- Add source-authority gate for hidden consolidation parameters.
- Add stress-increase handoff gate from foundation loading.
- Add two-part settlement construction gate.
- Add serviceability threshold gate if combined with immediate settlement.

Natural products:

- `immediate-settlement -> consolidation-settlement` as short-term plus long-term settlement package.
- `cpt/spt -> consolidation-settlement` if lab/soil classification correlations are introduced.
- `foundation load schedule -> consolidation-settlement` through final effective stress.

Meta-harness handles:

- `projection`: borehole profile, lab consolidation table, load schedule, stress profile.
- `difference`: hide compression parameters or preconsolidation interpretation labels.
- `product`: foundation settlement package.

## Task 7: Infinite Slope

Current world:

- Computes pore pressure, driving stress, resisting stress, and factor of safety for infinite slope failure.
- Inputs are slope angle, friction angle, cohesion, unit weight, failure depth, and water table depth.
- Hard mode hides cohesion, friction angle, and unit weight.
- The engine computes pore pressure only when water table depth is above the failure surface.
- This differs from the civil dam steady-state slope task, which uses a pore pressure ratio rather than an explicit water-table depth.

Multimodal expansion:

- Best first modality: slope cross-section plus groundwater profile and soil parameter table.
- A section can expose slope angle and failure depth.
- A groundwater profile can expose water table depth.
- A geotechnical report can expose strength and unit-weight parameters.

Requirements:

- Slope geometry source.
- Water table source.
- Soil parameter source.
- Branch evidence for dry versus water-present case.
- Factor of safety threshold context if extended.

Harness opportunities:

- Add slope-geometry extraction gate.
- Add water-table branch gate.
- Add source-authority gate for hidden soil parameters.
- Add construction gates for pore pressure, driving stress, and resistance.
- Add cross-template comparison gate with civil slope-stability tasks.

Natural products:

- `cpt/spt -> infinite-slope` through interpreted soil parameters.
- `infinite-slope -> civil fos-steady-state/fos-seismic` as method/scenario comparison.
- `infinite-slope -> retaining-wall` for cut-slope and retained-slope packages.

Meta-harness handles:

- `projection`: slope section, groundwater profile, soil property table.
- `difference`: hide soil properties or water-table labels.
- `product`: slope stability package.

## Task 8: Lateral Earth Pressure

Current world:

- Computes Rankine or Coulomb active/passive coefficients, base pressures, total forces, and active-force application point.
- Inputs are friction angle, cohesion, unit weight, wall height, backfill slope, wall friction angle, surcharge, and selected theory.
- Hard mode hides cohesion, friction angle, and unit weight.
- The engine supports Rankine/Coulomb theory and wall friction for Coulomb, but does not include water-table effects.
- Active force is clamped to zero if cohesion dominates.

Multimodal expansion:

- Best first modality: retaining-wall section plus backfill/soil table and theory note.
- A section can expose wall height, backfill slope, and surcharge context.
- A geotechnical report can expose soil parameters.
- A design note can select Rankine versus Coulomb and wall friction.

Requirements:

- Wall geometry and surcharge source.
- Soil parameter source.
- Theory selection source.
- Wall friction source for Coulomb variants.
- Explicit groundwater assumption because this ground task does not model water table.

Harness opportunities:

- Add theory-selection gate.
- Add wall-friction clamp/selection gate.
- Add active-force clamp gate.
- Add application-point moment gate.
- Add discipline-interface gate against civil lateral-earth-pressure for Rankine plus water-table cases.

Natural products:

- `lateral-earth-pressure -> wall-overturning -> wall-bearing` as retaining-wall design chain.
- `civil lateral-earth-pressure <-> ground lateral-earth-pressure` as theory/water-table comparison.
- `lateral-earth-pressure -> structural wall design` when structural tasks are reviewed.

Meta-harness handles:

- `projection`: retaining-wall section, soil table, theory note, surcharge plan.
- `difference`: hide soil properties, theory, or wall friction.
- `product`: retaining-wall pressure package.

## Task 9: Wall Bearing

Current world:

- Computes eccentricity, effective width, maximum bearing pressure, ultimate bearing capacity, and factor of safety.
- Inputs are base width, total vertical load, net moment, foundation soil parameters, embedment depth, and allowable bearing capacity.
- Hard mode hides foundation soil cohesion, friction angle, and unit weight.
- The engine uses Meyerhof effective width and clamps effective width to a small positive value for unstable cases.
- Factor of safety is `allowable_bearing_capacity / q_max`; ultimate bearing capacity is reported but not used in the returned FoS.

Multimodal expansion:

- Best first modality: retaining-wall force summary plus foundation soil table.
- A wall stability sheet can provide total vertical load and net moment.
- A wall section can provide base width and embedment.
- A geotechnical report can provide soil parameters and allowable bearing capacity.

Requirements:

- Handoff source for vertical load and net moment, ideally from `wall-overturning` or a wall stability model.
- Base width and embedment source.
- Foundation soil source and allowable capacity source.
- Effective-width and eccentricity sign convention record.
- Explicit note that FoS uses allowable capacity, not the computed ultimate value.

Harness opportunities:

- Add handoff gate from overturning/stability task.
- Add eccentricity/effective-width gate.
- Add source-authority gate for hidden foundation properties.
- Add bearing pressure compliance gate.
- Add repair/clarity target around signed eccentricity versus absolute eccentricity in source explanations.

Natural products:

- `wall-overturning -> wall-bearing` as retaining-wall stability chain.
- `meyerhof-bearing-capacity -> wall-bearing` through shared bearing-factor method.
- `civil retaining-wall-stability -> ground wall-bearing` as monolith-to-staged decomposition.

Meta-harness handles:

- `projection`: wall force summary, wall section, foundation soil table, bearing capacity note.
- `difference`: hide soil properties or suppress net-moment sign convention.
- `product`: retaining-wall base bearing package.

## Task 10: Wall Overturning

Current world:

- Computes Rankine `Ka`, active force, overturning moment, resisting moment, and overturning factor of safety.
- Inputs are wall height, base width, stem thickness, base thickness, backfill friction angle, backfill unit weight, concrete unit weight, surcharge, and water table depth.
- Hard mode hides backfill friction angle and unit weight.
- The engine models a cantilever L-wall with toe length `B/3`, stem after the toe, and heel soil providing resisting moment.
- Water pressure is added if water table lies within the total wall height.

Multimodal expansion:

- Best first modality: retaining-wall section with toe/heel labels and groundwater/surcharge context.
- A wall section can expose wall geometry and toe/heel layout.
- A groundwater record can expose water table depth.
- A surcharge plan can expose retained surcharge.
- A material table can expose backfill and concrete unit weights.

Requirements:

- Wall geometry source with toe, stem, heel, and base thickness.
- Backfill strength/unit-weight source.
- Water table and surcharge source.
- Moment component ledger for active soil, surcharge, water, base, stem, backfill, and vertical surcharge.
- Clear distinction from the civil retaining-wall geometry convention.

Harness opportunities:

- Add wall-orientation gate for toe/heel layout.
- Add water-table branch gate.
- Add force/moment decomposition gates.
- Add source-authority gate for hidden backfill parameters.
- Add handoff gate into `wall-bearing` using vertical load and net moment if extended.

Natural products:

- `lateral-earth-pressure -> wall-overturning -> wall-bearing` as staged retaining-wall task.
- `wall-overturning -> civil retaining-wall-stability` as method and geometry comparison.
- `wall-overturning -> structural wall/rebar checks` when structural retaining-wall tasks exist.

Meta-harness handles:

- `projection`: wall section, surcharge plan, groundwater record, material table.
- `difference`: hide backfill properties or remove toe/heel labels.
- `product`: retaining-wall overturning and bearing stability package.

## Cross-Discipline Threads Opened

The ground discipline supplies the strongest upstream evidence layer for many civil and structural tasks. It should not be treated as an isolated formula family. The key cross-discipline threads are:

- investigation to design: `spt-corrections` and `cpt-parameter-derivation` supply interpreted properties to bearing, settlement, slope, and retaining checks;
- foundation package: bearing capacity plus immediate and consolidation settlement against one footing/load case;
- retaining-wall staged package: lateral pressure, overturning, and bearing as separated checks that can be compared with civil's all-in-one retaining template;
- water-state comparison: ground infinite slope uses explicit water table, civil dam slope tasks use pore pressure ratio or loading scenarios;
- structural interface: foundation reactions, wind/ULS loads, and retaining forces can feed structural member and connection checks.

## Meta-Harness Implications

For ground tasks, a practical meta-harness should preserve both interpretation provenance and downstream design handoffs. The useful task-world sidecar should declare:

- source investigation record and selected depth/layer;
- soil parameter provenance and whether the parameter is lab-measured, field-derived, or archetype-inferred;
- groundwater state and stress path;
- selected method/theory and branch decisions;
- handoff fields consumed by downstream foundation, slope, or retaining tasks.

The best event candidates are:

- wrong field correction factor selected from source equipment;
- CPT soil behavior branch error;
- water table branch error in bearing/slope/overturning tasks;
- settlement consolidation case error;
- wall theory or wall geometry convention mismatch;
- downstream retaining-wall bearing using forces from an incompatible wall layout.
