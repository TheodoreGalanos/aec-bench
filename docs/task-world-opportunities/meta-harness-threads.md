# ABOUTME: Collects reusable meta-harness settings discovered during task-world review.
# ABOUTME: Tracks operation handles, gates, and repair candidates that apply across task families.

# Meta-Harness Threads

## Reusable Settings

| Setting | Applies To | Practical Task-Level Elements |
| --- | --- | --- |
| Source-authority gate | Tasks using standards tables, datasheets, or scenario context | Record which source artifact supplied each derived parameter; verifier checks source-to-parameter trace. |
| Intermediate-value construction gate | Multi-output formula tasks and composed workflows | Require named intermediate values, not just final outputs, when the world has staged calculations. |
| Modality projection | Multimodal variants of existing formulas | Project the same world into text-only, table-source, drawing-source, or document-source variants. |
| Difficulty difference operation | Existing hidden-parameter tasks | Remove visible parameters or remove calculator tool access while preserving ground truth and evidence. |
| Product-world pipeline | Cross-task combinations | Compose left/right worlds with explicit handoff fields and separate closure gates per stage. |
| Shared-subworld product | Non-traditional cross-discipline combinations | Compose worlds over a shared profile, SLD, borehole log, equipment layout, occupancy schedule, or operating scenario before checking scalar handoffs. |
| Contradiction ledger | Tasks with verifier/artifact disagreement risk | If numeric answer passes but produced artifact is inconsistent, record the contradiction and trigger review. |

## Early Repair Targets

| Repair Target | Trigger | Why It Matters |
| --- | --- | --- |
| `evidence_profile` | Verifier only checks final numeric answer when source interpretation is central. | Multimodal tasks need source-reading evidence, not only arithmetic correctness. |
| `world_schema` | A task lacks declared handles for source artifacts, hidden parameters, or handoff values. | Deterministic meta-harness operations need stable paths. |
| `verifier` | Tolerance-only scoring misses staged reasoning, artifact quality, or unit consistency. | Complex tasks should identify where a failure occurred. |
| `generator` | Task variants require realistic drawings/tables but current sampler only emits scalar params. | Multimodal expansion depends on source artifact generation. |
| `governance` | A task uses standards excerpts or project-sensitive source material. | Public/holdout separation and source authority need explicit controls. |

## Detailed Setting: Stormwater Chain

Detailed pass: `detailed-passes/civil-stormwater-detention-001.md`

Candidate operation handles for explicit world sidecars:

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

Reusable gates:

- Upstream task output equals downstream task input within declared units.
- Branch decision is stated before the final detention volume.
- Source-derived hidden parameter has a cited source record.
- Final pass/fail agrees with computed clearance and threshold.
- Produced design record contains the required handoff fields.

## Detailed Setting: Conveyance And Outfall Hydraulics

Detailed pass: `detailed-passes/civil-conveyance-outfall-002.md`

Candidate operation handles for explicit world sidecars:

- `source_artifacts.pipe_schedule`
- `source_artifacts.pipe_long_section`
- `source_artifacts.roughness_table`
- `source_artifacts.channel_section`
- `source_artifacts.road_cross_section`
- `source_artifacts.culvert_long_section`
- `source_artifacts.outfall_profile`
- `source_artifacts.tide_scenario_table`
- `source_artifacts.gate_datasheet`
- `source_artifacts.spillway_drawing`
- `source_artifacts.correction_factor_table`
- `source_artifacts.tailwater_profile`
- `branch_decisions.pipe_geometry_regime`
- `branch_decisions.friction_regime`
- `branch_decisions.culvert_control`
- `branch_decisions.tidal_edge_case`
- `branch_decisions.basin_type`
- `compliance.velocity_pass_fail`
- `handoffs.design_flow`
- `handoffs.unit_discharge`
- `handoffs.tailwater`

Reusable gates:

- Selected roughness or C-factor is traceable to source material/condition.
- Pipe/channel geometry regime matches the source artifact.
- Darcy friction regime follows the computed Reynolds number.
- Culvert controlling condition is the larger of inlet and outlet headwater.
- Tidal edge case is selected correctly for always submerged/unsubmerged conditions.
- Spillway effective crest length reflects pier and abutment corrections.
- Stilling basin type follows Froude-number thresholds.
- Downstream task inputs equal upstream outputs within declared units.

## Detailed Setting: Coastal Wave And Shoreline Worlds

Detailed pass: `detailed-passes/civil-coastal-wave-003.md`

Candidate operation handles for explicit world sidecars:

- `source_artifacts.wave_table`
- `source_artifacts.wave_rose`
- `source_artifacts.bathymetry_profile`
- `source_artifacts.shoreline_orientation_map`
- `source_artifacts.structure_section`
- `source_artifacts.roughness_factor_table`
- `source_artifacts.slr_scenario_table`
- `source_artifacts.rock_material_table`
- `source_artifacts.sediment_table`
- `source_artifacts.basin_map`
- `source_artifacts.inlet_section`
- `branch_decisions.depth_regime`
- `branch_decisions.breaker_type`
- `branch_decisions.runup_regime`
- `branch_decisions.transport_direction`
- `branch_decisions.datum_consistency`
- `handoffs.nearshore_wave_height`
- `handoffs.breaking_wave_height`
- `handoffs.runup_allowance`
- `handoffs.tidal_exchange`

Reusable gates:

- Wave period, height, and angle are traceable to the selected source row or wave-rose bin.
- Bathymetry/profile extraction uses the declared datum and chainage.
- Shoaling/refraction coefficients produce the nearshore wave-height handoff.
- Breaker type follows the computed Iribarren number.
- Runup regime matches the governing expression selected by the engine.
- Freeboard components have separate source records and datum consistency.
- Hudson density and `KD` are traceable to material/armor assumptions.
- CERC transport direction matches the signed wave angle convention.
- Tidal-prism exchange duration and basin area are source-derived, not guessed.

## Detailed Setting: Road And Rail Geometry Worlds

Detailed pass: `detailed-passes/civil-road-rail-geometry-004.md`

Candidate operation handles for explicit world sidecars:

- `source_artifacts.alignment_plan`
- `source_artifacts.alignment_schedule`
- `source_artifacts.road_design_criteria`
- `source_artifacts.standards_friction_table`
- `source_artifacts.road_cross_section`
- `source_artifacts.intersection_plan`
- `source_artifacts.driveway_long_section`
- `source_artifacts.vertical_profile`
- `source_artifacts.track_curve_table`
- `source_artifacts.corridor_class_table`
- `source_artifacts.rail_section_table`
- `source_artifacts.temperature_record`
- `branch_decisions.superelevation_clamp`
- `branch_decisions.governing_spiral_criterion`
- `branch_decisions.stress_state`
- `branch_decisions.grade_sign_convention`
- `compliance.driveway_gradient`
- `compliance.radius_minimum`
- `compliance.sight_distance`
- `handoffs.curve_radius`
- `handoffs.actual_cant`
- `handoffs.cant_deficiency`
- `handoffs.maximum_speed`

Reusable gates:

- Curve chainage identities close: `PC = IP - T` and `PT = PC + L`.
- Side-friction and reaction-time assumptions are traceable to standards/source tables.
- Superelevation clamp decision is recorded before development length.
- Gap time equals base plus grade plus lane corrections.
- Grade sign convention is explicit for stopping sight distance.
- Driveway compliance matches gradient and selected location limit.
- Cant deficiency and maximum speed use the selected gauge/corridor constraints.
- Governing spiral length equals the maximum of the three criterion lengths.
- Vertical curve length uses percent-grade difference consistently.
- Stress state matches temperature-change sign.

## Detailed Setting: Civil Geotechnical Seepage And Stability Worlds

Detailed pass: `detailed-passes/civil-geotech-seepage-stability-005.md`

Candidate operation handles for explicit world sidecars:

- `source_artifacts.dam_cross_section`
- `source_artifacts.foundation_profile`
- `source_artifacts.flow_net`
- `source_artifacts.drain_gallery_detail`
- `source_artifacts.operating_level_table`
- `source_artifacts.embankment_zoning_section`
- `source_artifacts.phreatic_surface_profile`
- `source_artifacts.reservoir_operation_record`
- `source_artifacts.material_property_table`
- `source_artifacts.borehole_log`
- `source_artifacts.seismic_hazard_table`
- `source_artifacts.retaining_wall_section`
- `source_artifacts.groundwater_record`
- `source_artifacts.surcharge_plan`
- `branch_decisions.soil_property_source`
- `branch_decisions.water_state_regime`
- `branch_decisions.drain_efficiency_assumption`
- `branch_decisions.drawdown_state`
- `branch_decisions.seismic_vertical_coefficient`
- `branch_decisions.water_table_regime`
- `branch_decisions.active_pressure_clamp`
- `branch_decisions.middle_third_bearing`
- `compliance.piping_fos`
- `compliance.steady_state_fos`
- `compliance.rapid_drawdown_fos`
- `compliance.seismic_fos`
- `compliance.sliding_overturning_bearing`
- `handoffs.soil_properties`
- `handoffs.hydraulic_head`
- `handoffs.pore_pressure_state`
- `handoffs.lateral_pressure`
- `handoffs.foundation_capacity`

Reusable gates:

- Soil-property values are traceable to an explicit table, borehole/lab source, or declared archetype default.
- Headwater, tailwater, water table, and reservoir levels use one datum and one scenario state.
- Exit gradient, critical gradient, and piping factor of safety use consistent `G_s` and void ratio values.
- Uplift drain efficiency is converted from percent to fraction and produces a plausible drain pressure ordinate.
- Steady-state pore pressure uses the declared pore-pressure-ratio formulation.
- Rapid-drawdown post-event driving stress uses saturated unit weight while effective stress remains buoyant.
- Seismic vertical coefficient convention is stated before the pseudo-static FoS and yield acceleration.
- Lateral water force is calculated independently of Rankine `Ka`.
- Active pressure clamp is recorded when cohesion would make the net active force negative.
- Retaining-wall toe/heel orientation and heel width match the source drawing.
- Sliding, overturning, eccentricity, base pressure, and bearing checks preserve their force and moment decomposition.
- The retaining-wall outside-middle-third base-pressure branch is audited for instruction/engine consistency before multimodal variants are generated.

## Detailed Setting: Civil Services And Environmental Systems

Detailed pass: `detailed-passes/civil-services-environmental-systems-006.md`

Candidate operation handles for explicit world sidecars:

- `source_artifacts.roof_plan`
- `source_artifacts.gutter_schedule`
- `source_artifacts.downpipe_layout`
- `source_artifacts.rainfall_intensity_table`
- `source_artifacts.standard_capacity_table`
- `source_artifacts.sewer_long_section`
- `source_artifacts.pipe_material_schedule`
- `source_artifacts.velocity_limits_table`
- `source_artifacts.pump_station_section`
- `source_artifacts.pump_curve`
- `source_artifacts.system_curve`
- `source_artifacts.fluid_property_table`
- `source_artifacts.motor_schedule`
- `source_artifacts.catchment_land_use_map`
- `source_artifacts.emc_table`
- `source_artifacts.erosion_control_plan`
- `source_artifacts.soil_loss_table`
- `source_artifacts.bund_layout`
- `source_artifacts.container_register`
- `source_artifacts.equipment_layout`
- `branch_decisions.standard_size_selection`
- `branch_decisions.nominated_vs_required_asset`
- `branch_decisions.velocity_compliance_state`
- `branch_decisions.pump_suction_state`
- `branch_decisions.fluid_property_source`
- `branch_decisions.sediment_basin_type`
- `branch_decisions.pollutant_land_use_class`
- `branch_decisions.bund_governing_rule`
- `compliance.roof_drainage`
- `compliance.sewer_velocity`
- `compliance.npsh_margin`
- `compliance.bund_capacity`
- `handoffs.roof_design_flow`
- `handoffs.sewer_design_flow`
- `handoffs.total_dynamic_head`
- `handoffs.pollutant_loads`
- `handoffs.environmental_control_volume`

Reusable gates:

- Rainfall intensity, Manning roughness, EMC, fluid property, and efficiency values are traceable to a source table or declared archetype.
- Standard size selection chooses the smallest adequate listed size, not merely any passing size.
- Compliance outputs agree with the computed capacity, velocity, volume, or margin.
- Unit conversions are explicit for litres, cubic metres, hectares, millimetres, kPa, percentages, and decimal efficiencies.
- Sewer long-section slope uses the intended invert pair and preserves any directionality needed by the task.
- NPSH static suction head sign is consistent with flooded suction or suction lift source geometry.
- Sediment basin Type D and Type F volume components are selected correctly.
- Bund governing capacity rule is the larger of 110 percent largest container or 25 percent total stored volume.
- Gutter-sizing variants declare whether the task checks a nominated profile or designs the smallest adequate replacement.

## Detailed Setting: Civil Wind And Load Actions

Detailed pass: `detailed-passes/civil-wind-load-actions-007.md`

Candidate operation handles for explicit world sidecars:

- `source_artifacts.wind_region_table`
- `source_artifacts.site_aerial_context`
- `source_artifacts.terrain_height_table`
- `source_artifacts.topography_profile`
- `source_artifacts.shielding_site_plan`
- `source_artifacts.building_elevation`
- `source_artifacts.pressure_zone_diagram`
- `source_artifacts.tributary_area_sketch`
- `source_artifacts.solar_array_layout`
- `source_artifacts.racking_section`
- `source_artifacts.module_schedule`
- `source_artifacts.pv_coefficient_table`
- `source_artifacts.structural_load_schedule`
- `source_artifacts.occupancy_use_plan`
- `source_artifacts.load_combination_factor_table`
- `source_artifacts.earthquake_action_source`
- `branch_decisions.terrain_category`
- `branch_decisions.shielding_class`
- `branch_decisions.topographic_exposure`
- `branch_decisions.height_interpolation`
- `branch_decisions.wind_pressure_sign`
- `branch_decisions.dynamic_response_factor`
- `branch_decisions.solar_row_position`
- `branch_decisions.solar_tilt_source`
- `branch_decisions.load_category`
- `branch_decisions.governing_combination`
- `compliance.wind_action_handoff`
- `handoffs.site_wind_speed`
- `handoffs.design_wind_pressure`
- `handoffs.solar_wind_actions`
- `handoffs.serviceability_wind_action`
- `handoffs.ultimate_wind_action`
- `handoffs.governing_load_combination`

Reusable gates:

- Terrain category and shielding multiplier are traceable to site context rather than guessed.
- `M_z,cat` interpolation uses the correct terrain column and bracketing heights.
- Wind-speed multiplier product closes to the site wind speed.
- Wind pressure preserves suction/pressure sign convention.
- Tributary area source matches the total force calculation.
- Solar PV tilt and row position select the correct coefficient and interior-row reduction.
- Solar `array_height_m` is declared context-only or connected to an explicit coefficient rule before height-sensitive variants are generated.
- SLS and ULS category factors are traceable to occupancy/use context.
- ULS hidden-category variants require category inference rather than a default Category A shortcut.
- Governing load combination equals the maximum of all computed candidate combinations.

## Detailed Setting: Ground Site Foundation And Retaining Worlds

Detailed pass: `detailed-passes/ground-site-foundation-retaining-008.md`

Candidate operation handles for explicit world sidecars:

- `source_artifacts.spt_field_sheet`
- `source_artifacts.cpt_trace`
- `source_artifacts.borehole_log`
- `source_artifacts.groundwater_profile`
- `source_artifacts.lab_test_summary`
- `source_artifacts.soil_profile`
- `source_artifacts.footing_plan`
- `source_artifacts.foundation_load_schedule`
- `source_artifacts.settlement_stress_profile`
- `source_artifacts.retaining_wall_section`
- `source_artifacts.surcharge_plan`
- `source_artifacts.wall_force_summary`
- `branch_decisions.spt_equipment_correction`
- `branch_decisions.cpt_soil_behavior_type`
- `branch_decisions.bearing_method`
- `branch_decisions.water_table_bearing_case`
- `branch_decisions.footing_shape`
- `branch_decisions.load_inclination`
- `branch_decisions.foundation_rigidity`
- `branch_decisions.consolidation_state`
- `branch_decisions.slope_water_state`
- `branch_decisions.lateral_pressure_theory`
- `branch_decisions.wall_geometry_orientation`
- `branch_decisions.wall_eccentricity_convention`
- `handoffs.corrected_spt_value`
- `handoffs.cpt_strength_parameters`
- `handoffs.foundation_soil_parameters`
- `handoffs.foundation_reaction`
- `handoffs.wall_lateral_force`
- `handoffs.wall_net_moment`
- `compliance.bearing_capacity`
- `compliance.settlement_serviceability`
- `compliance.slope_stability`
- `compliance.wall_overturning`
- `compliance.wall_bearing`

Reusable gates:

- SPT equipment correction factors match the field sheet and correction table.
- CPT row extraction, stress calculation, and soil behavior type branch are recorded before strength handoff.
- Soil parameters are tagged as lab-measured, field-derived, or archetype-inferred.
- Bearing capacity water-table branch and footing shape/method match the source artifacts.
- Settlement immediate/consolidation branches use the correct rigidity, influence factor, OCR, and stress path.
- Infinite-slope water table branch matches groundwater depth relative to failure depth.
- Lateral earth-pressure theory, wall friction, and groundwater assumption are explicit.
- Retaining-wall toe/heel geometry conventions are compatible before cross-template composition.
- Wall-bearing forces and moments come from a compatible wall layout and sign convention.

## Detailed Setting: Structural Systems And Materials

Detailed pass: `detailed-passes/structural-systems-materials-009.md`

Candidate operation handles for explicit world sidecars:

- `source_artifacts.vessel_schedule`
- `source_artifacts.berth_layout`
- `source_artifacts.fender_datasheet`
- `source_artifacts.mooring_analysis`
- `source_artifacts.line_datasheet`
- `source_artifacts.facade_elevation`
- `source_artifacts.cladding_panel_schedule`
- `source_artifacts.bracket_detail`
- `source_artifacts.pipe_schedule`
- `source_artifacts.insulation_fluid_table`
- `source_artifacts.foundation_block_plan`
- `source_artifacts.structural_load_effect_table`
- `source_artifacts.composite_section_drawing`
- `source_artifacts.rebar_schedule`
- `source_artifacts.tolerance_stackup_table`
- `source_artifacts.component_material_schedule`
- `source_artifacts.mill_certificate`
- `source_artifacts.welding_specification`
- `source_artifacts.concrete_mix_design`
- `source_artifacts.production_quality_record`
- `branch_decisions.marine_coefficient_source`
- `branch_decisions.fender_correction_source`
- `branch_decisions.mooring_pass_state`
- `branch_decisions.effective_wind_area_governing_source`
- `branch_decisions.governing_load_combination`
- `branch_decisions.middle_third_state`
- `branch_decisions.section_component_decomposition`
- `branch_decisions.lap_rounding`
- `branch_decisions.tolerance_method`
- `branch_decisions.thermal_material_source`
- `branch_decisions.weldability_risk_class`
- `branch_decisions.concrete_margin_rule`
- `handoffs.design_berthing_energy`
- `handoffs.corrected_fender_capacity`
- `handoffs.effective_wind_area`
- `handoffs.factored_structural_action`
- `handoffs.pipe_line_load`
- `handoffs.foundation_reaction`
- `handoffs.composite_section_properties`
- `handoffs.material_compliance_state`
- `compliance.fender_capacity`
- `compliance.mooring_capacity`
- `compliance.gravity_base_bearing`
- `compliance.lap_splice`
- `compliance.weldability`
- `compliance.concrete_mix`

Reusable gates:

- Marine coefficient and correction-factor products are traceable to a design basis or datasheet.
- Berthing energy handoff equals the fender-check input within units.
- Utilisation, reserve capacity, margin, and pass flags tell the same capacity story.
- Effective wind area selects the maximum of panel, tributary, and minimum areas.
- Load resultants and governing combinations use the declared criterion, not an inferred code rule.
- Pipe-support loads preserve annulus geometry, density sources, and operating versus hydrotest states.
- Gravity-base middle-third flag is checked before trusting elastic bearing output.
- Composite section components, centroids, and transformed concrete areas match the drawing.
- Construction tolerance distinguishes total allowance from RSS tolerance and excludes clearance from RSS.
- Thermal CTE is traceable to material source when hidden.
- Material certificate chemistry maps to the correct carbon-equivalent terms.
- Concrete target strength uses the governing maximum margin rather than averaging margins.

## Detailed Setting: Mechanical Fire Water Hydraulic Pump And Transient

Detailed pass: `detailed-passes/mechanical-fire-water-hydraulic-pump-transient-010.md`

Candidate operation handles for explicit world sidecars:

- `source_artifacts.hydrant_flow_test_sheet`
- `source_artifacts.hydrant_supply_curve`
- `source_artifacts.fire_services_design_basis`
- `source_artifacts.sprinkler_layout`
- `source_artifacts.sprinkler_schedule`
- `source_artifacts.sprinkler_hydraulic_calculation`
- `source_artifacts.pipe_schedule`
- `source_artifacts.pipe_long_section`
- `source_artifacts.hydraulic_profile`
- `source_artifacts.p_id`
- `source_artifacts.fitting_takeoff`
- `source_artifacts.roughness_table`
- `source_artifacts.pump_station_section`
- `source_artifacts.pump_curve`
- `source_artifacts.system_curve`
- `source_artifacts.pump_datasheet`
- `source_artifacts.suction_vessel_datasheet`
- `source_artifacts.fluid_property_table`
- `source_artifacts.motor_schedule`
- `source_artifacts.pipe_material_schedule`
- `source_artifacts.pipe_support_restraint_drawing`
- `source_artifacts.transient_event_note`
- `source_artifacts.pipe_alignment_plan`
- `source_artifacts.thrust_block_detail`
- `branch_decisions.unit_system`
- `branch_decisions.pressure_reference`
- `branch_decisions.elevation_sign_convention`
- `branch_decisions.friction_loss_method`
- `branch_decisions.fitting_loss_method`
- `branch_decisions.selected_pipe_branch`
- `branch_decisions.pump_operating_case`
- `branch_decisions.pump_same_geometry_assumption`
- `branch_decisions.por_aor_state`
- `branch_decisions.cavitation_margin_state`
- `branch_decisions.restraint_condition`
- `branch_decisions.transient_event_case`
- `handoffs.available_fire_flow`
- `handoffs.hydrant_curve_coefficient`
- `handoffs.sprinkler_demand_flow`
- `handoffs.pipe_velocity`
- `handoffs.pipe_friction_loss`
- `handoffs.fitting_loss`
- `handoffs.total_pressure_loss`
- `handoffs.total_dynamic_head`
- `handoffs.npsh_available`
- `handoffs.pump_shaft_power`
- `handoffs.motor_input_power`
- `handoffs.operating_flow_ratio`
- `handoffs.wave_speed`
- `handoffs.surge_pressure`
- `handoffs.bend_thrust_force`
- `compliance.fire_supply_demand`
- `compliance.velocity_range`
- `compliance.npsh_margin`
- `compliance.por_aor`
- `compliance.thrust_restraint`
- `compliance.motor_sizing`

Reusable gates:

- Hydrant source points are traceable to a test sheet before curve extrapolation.
- Hydrant and sprinkler calculations keep psi/gpm and kPa/L/s worlds explicit.
- Sprinkler discharge, pipe friction, and elevation pressure preserve node pressure and flow handoffs.
- Pipe schedule extraction distinguishes nominal diameter from internal diameter.
- Fitting takeoff matches the selected pipe path before total `K` or equivalent length is trusted.
- Hazen-Williams distributed loss and fitting/minor loss are separated before total pressure loss is emitted.
- Velocity pass/fail matches both minimum and maximum margins.
- Pump TDH uses compatible pressure reference, elevation sign, and friction-loss handoff.
- NPSH uses absolute pressure and a declared pump datum before cavitation margin is checked.
- Pump affinity law variants preserve the same-pump/same-impeller assumption.
- Motor input power and recommended motor size preserve pump efficiency, motor efficiency, and sizing-factor provenance.
- POR/AOR flags agree with the operating-flow ratio and the declared BEP source.
- Wave speed handoff equals the input used for Joukowsky surge pressure.
- Surge pressure is added to the correct operating/design pressure before thrust force is calculated.

## Detailed Setting: Mechanical Treatment Process And Solids

Detailed pass: `detailed-passes/mechanical-treatment-process-solids-011.md`

Candidate operation handles for explicit world sidecars:

- `source_artifacts.process_flow_diagram`
- `source_artifacts.process_design_basis`
- `source_artifacts.influent_effluent_lab_report`
- `source_artifacts.chemical_datasheet`
- `source_artifacts.dosing_schedule`
- `source_artifacts.reactor_kinetics_table`
- `source_artifacts.basin_plan`
- `source_artifacts.aeration_basin_schedule`
- `source_artifacts.operating_trend_table`
- `source_artifacts.was_record`
- `source_artifacts.effluent_record`
- `source_artifacts.seasonal_temperature_table`
- `source_artifacts.operating_do_trend`
- `source_artifacts.nitrogen_balance`
- `source_artifacts.sludge_balance_sheet`
- `source_artifacts.primary_clarifier_record`
- `source_artifacts.digester_feed_log`
- `source_artifacts.gas_meter_record`
- `source_artifacts.energy_use_schedule`
- `source_artifacts.clarifier_plan`
- `source_artifacts.active_unit_schedule`
- `source_artifacts.design_criteria_table`
- `branch_decisions.flow_case`
- `branch_decisions.process_unit_selection`
- `branch_decisions.reactor_model`
- `branch_decisions.conversion_basis`
- `branch_decisions.srt_time_window`
- `branch_decisions.temperature_governing_case`
- `branch_decisions.net_growth_feasibility`
- `branch_decisions.oxygen_credit_clamp`
- `branch_decisions.solids_basis_tss_vss`
- `branch_decisions.clarifier_active_area`
- `branch_decisions.clarifier_governing_criterion`
- `handoffs.design_flow`
- `handoffs.mass_load`
- `handoffs.product_feed_rate`
- `handoffs.hrt`
- `handoffs.reactor_volume`
- `handoffs.mlss_inventory`
- `handoffs.actual_srt`
- `handoffs.required_nitrification_srt`
- `handoffs.sludge_production`
- `handoffs.oxygen_requirement`
- `handoffs.volatile_solids_feed`
- `handoffs.biogas_energy`
- `handoffs.surface_overflow_rate`
- `handoffs.solids_loading_rate`
- `compliance.nitrification_srt`
- `compliance.clarifier_sor`
- `compliance.clarifier_slr`
- `compliance.dosing_capacity`
- `compliance.process_upgrade_required`

Reusable gates:

- mg/L and m3/d load conversions are explicit before mass-load handoffs are used.
- Chemical active dose, product strength, product density, and product volume are kept as separate roles.
- Reactor type is declared before CSTR or PFR equations are accepted.
- Conversion basis is derived from source concentration targets when not given directly.
- Basin volume excludes freeboard, standby, or dead volume unless the source explicitly includes it.
- MLSS inventory, wasting solids, effluent solids loss, and SRT use the same time window.
- Required nitrification SRT is compared with actual SRT only after temperature, substrate, oxygen, and decay terms are recorded.
- Non-positive nitrifier net growth is treated as an infeasible design event.
- Oxygen demand records carbonaceous, nitrogenous, denitrification-credit, and zero-clamp branches separately.
- Sludge-production outputs preserve TSS, VSS, and VS roles before any biogas handoff.
- Clarifier active area and active-unit count are source-derived before SOR or SLR is checked.
- SOR and SLR utilisation, margin, and pass flags agree with the governing criterion.

## Detailed Setting: Mechanical Life Safety Environment And Acoustics

Detailed pass: `detailed-passes/mechanical-life-safety-environment-acoustics-012.md`

Candidate operation handles for explicit world sidecars:

- `source_artifacts.floor_plan`
- `source_artifacts.occupancy_schedule`
- `source_artifacts.egress_plan`
- `source_artifacts.door_stair_schedule`
- `source_artifacts.code_criteria_table`
- `source_artifacts.fire_alarm_plan`
- `source_artifacts.notification_device_schedule`
- `source_artifacts.manufacturer_current_table`
- `source_artifacts.design_fire_scenario`
- `source_artifacts.hrr_curve`
- `source_artifacts.smoke_model_output`
- `source_artifacts.tenability_criteria_table`
- `source_artifacts.egress_route_map`
- `source_artifacts.steel_member_schedule`
- `source_artifacts.structural_utilisation_extract`
- `source_artifacts.fire_protection_schedule`
- `source_artifacts.room_schedule`
- `source_artifacts.ventilation_schedule`
- `source_artifacts.gas_appliance_schedule`
- `source_artifacts.room_finish_schedule`
- `source_artifacts.absorption_table`
- `source_artifacts.equipment_noise_schedule`
- `source_artifacts.octave_band_report`
- `source_artifacts.source_receiver_map`
- `branch_decisions.occupancy_classification`
- `branch_decisions.area_basis`
- `branch_decisions.rounding_rule`
- `branch_decisions.egress_element_selection`
- `branch_decisions.nac_circuit_selection`
- `branch_decisions.fire_growth_class`
- `branch_decisions.peak_limited_fire`
- `branch_decisions.tenability_time_location`
- `branch_decisions.structural_fire_load_ratio_source`
- `branch_decisions.ventilation_mode`
- `branch_decisions.gas_diversity_source`
- `branch_decisions.acoustic_source_inclusion`
- `branch_decisions.acoustic_distance_geometry`
- `branch_decisions.acoustic_band_labelling`
- `handoffs.design_occupants`
- `handoffs.required_egress_width`
- `handoffs.nac_total_load`
- `handoffs.hrr_at_time`
- `handoffs.visibility`
- `handoffs.critical_steel_temperature`
- `handoffs.room_volume`
- `handoffs.air_changes`
- `handoffs.diversified_gas_load`
- `handoffs.combined_spl`
- `handoffs.a_weighted_level`
- `handoffs.rt60`
- `handoffs.receiver_spl`
- `compliance.egress_width`
- `compliance.nac_capacity`
- `compliance.visibility_tenability`
- `compliance.fire_protection_required`
- `compliance.gas_load_capacity`
- `compliance.acoustic_receiver_level`

Reusable gates:

- Plan-derived area is tagged as gross, net, included, or excluded before occupant load is calculated.
- Occupant load rounding is recorded before egress width receives the handoff.
- Provided egress width is clear usable width, not nominal leaf/frame width.
- NAC devices belong to the selected circuit before load and spare capacity are checked.
- Design-fire HRR records whether the peak cap is active.
- Smoke visibility row selection preserves time, location, and egress-route identity.
- Structural-fire load ratio provenance is separate from ordinary structural utilisation unless explicitly mapped.
- Room volume, airflow, surface area, and absorption coefficients come from compatible room sources.
- Gas connected load and diversified load are separately named and converted between MJ/h and kW.
- Acoustic source inclusion follows the simultaneous-operating scenario.
- SPL combination uses logarithmic energy addition, not arithmetic addition.
- Octave-band labels are aligned before A-weighting coefficients are applied.
- Source-receiver distance uses the declared geometry before attenuation is calculated.

## Detailed Setting: Mechanical Dynamics Thermal And Verification

Detailed pass: `detailed-passes/mechanical-dynamics-thermal-verification-013.md`

Candidate operation handles for explicit world sidecars:

- `source_artifacts.tool_schedule`
- `source_artifacts.compressed_air_layout`
- `source_artifacts.operating_scenario_table`
- `source_artifacts.rolling_stock_datasheet`
- `source_artifacts.speed_profile`
- `source_artifacts.track_gradient_profile`
- `source_artifacts.braking_curve`
- `source_artifacts.signal_layout`
- `source_artifacts.resistance_coefficient_table`
- `source_artifacts.process_flow_diagram`
- `source_artifacts.process_stream_table`
- `source_artifacts.simulation_balance_report`
- `source_artifacts.cfd_report`
- `source_artifacts.mesh_table`
- `source_artifacts.convergence_plot`
- `source_artifacts.heat_exchanger_datasheet`
- `source_artifacts.thermal_stream_table`
- `source_artifacts.p_id`
- `source_artifacts.correction_factor_note`
- `source_artifacts.equipment_speed_schedule`
- `source_artifacts.isolator_datasheet`
- `source_artifacts.vibration_spectrum`
- `source_artifacts.duty_cycle_histogram`
- `source_artifacts.fatigue_table`
- `branch_decisions.simultaneity_source`
- `branch_decisions.gradient_sign_convention`
- `branch_decisions.adhesion_limited_braking`
- `branch_decisions.braking_sufficiency`
- `branch_decisions.davis_coefficient_source`
- `branch_decisions.mass_balance_boundary`
- `branch_decisions.mesh_value_order`
- `branch_decisions.monotonic_convergence`
- `branch_decisions.flow_arrangement`
- `branch_decisions.minimum_approach_definition`
- `branch_decisions.resonance_region`
- `branch_decisions.fatigue_bin_inclusion`
- `handoffs.compressed_air_demand`
- `handoffs.tractive_power`
- `handoffs.braking_distance`
- `handoffs.mass_balance_closure`
- `handoffs.gci_fine`
- `handoffs.heat_duty`
- `handoffs.minimum_approach`
- `handoffs.transmissibility`
- `handoffs.cumulative_fatigue_damage`
- `compliance.compressed_air_capacity`
- `compliance.braking_distance`
- `compliance.simulation_credibility`
- `compliance.thermal_approach`
- `compliance.vibration_isolation`
- `compliance.fatigue_damage`

Reusable gates:

- Connected and simultaneous compressed-air demands are separately named before capacity handoff.
- Track gradient sign convention is declared before braking deceleration is calculated.
- Adhesion-limited braking is recorded when requested brake effort exceeds the adhesion limit.
- Braking insufficiency is treated as a design event, not a missing numeric answer.
- Davis coefficients are traceable to the selected consist and speed regime.
- Mass-balance stream roles follow the declared process boundary and exclude internal recycle unless intended.
- Mesh values are ordered coarse, medium, fine before GCI arithmetic begins.
- Nonmonotonic convergence triggers a diagnosis/recovery event.
- Heat exchanger terminal temperature differences follow the declared flow arrangement.
- Minimum approach definition is audited for parallel-flow cases before richer LMTD variants are generated.
- Vibration transmissibility identifies resonance/amplification cases before reporting isolation efficiency.
- Fatigue bins include only the applicable duty cycles and preserve allowable-cycle source evidence.

## Detailed Setting: Electrical Power Storage PV And Loadflow

Detailed pass: `detailed-passes/electrical-power-storage-pv-loadflow-014.md`

Candidate operation handles for explicit world sidecars:

- `source_artifacts.equipment_load_list`
- `source_artifacts.design_basis`
- `source_artifacts.ups_battery_schedule`
- `source_artifacts.battery_datasheet`
- `source_artifacts.ambient_temperature_table`
- `source_artifacts.bess_duty_table`
- `source_artifacts.bess_warranty`
- `source_artifacts.pv_layout`
- `source_artifacts.module_datasheet`
- `source_artifacts.inverter_datasheet`
- `source_artifacts.site_climate_table`
- `source_artifacts.solar_resource_table`
- `source_artifacts.dc_cable_schedule`
- `source_artifacts.load_study`
- `source_artifacts.metering_record`
- `source_artifacts.pfc_target_note`
- `source_artifacts.single_line_diagram`
- `source_artifacts.feeder_schedule`
- `source_artifacts.line_parameter_table`
- `source_artifacts.transformer_datasheet`
- `source_artifacts.source_fault_level_note`
- `source_artifacts.iec_voltage_factor_table`
- `branch_decisions.load_role`
- `branch_decisions.future_expansion_source`
- `branch_decisions.temperature_derating_source`
- `branch_decisions.bess_capacity_semantics`
- `branch_decisions.bess_chemistry_assumption`
- `branch_decisions.site_temperature_source`
- `branch_decisions.solar_resource_source`
- `branch_decisions.mppt_clamp_or_infeasibility`
- `branch_decisions.conductor_material_source`
- `branch_decisions.reactive_load_source`
- `branch_decisions.voltage_drop_circuit_type`
- `branch_decisions.fault_location`
- `branch_decisions.voltage_factor_source`
- `handoffs.connected_load`
- `handoffs.maximum_demand`
- `handoffs.critical_load`
- `handoffs.battery_capacity`
- `handoffs.ups_rating`
- `handoffs.bess_bol_capacity`
- `handoffs.pv_annual_energy`
- `handoffs.string_module_window`
- `handoffs.dc_voltage_drop`
- `handoffs.capacitor_kvar`
- `handoffs.feeder_voltage_drop`
- `handoffs.receiving_end_voltage`
- `handoffs.fault_current`
- `compliance.battery_autonomy`
- `compliance.pv_string_window`
- `compliance.dc_voltage_drop`
- `compliance.ac_voltage_drop`
- `compliance.voltage_regulation`
- `compliance.fault_withstand`

Reusable gates:

- Connected load, maximum demand, critical load, and future allowance are separately named before handoff.
- Battery usable fraction records DoD, temperature derating, inverter efficiency, and power factor provenance.
- BESS outputs preserve nominal, usable, beginning-of-life, and end-of-life capacity roles.
- PV site temperatures and peak sun hours are source-derived before hard-mode solar calculations.
- Module and inverter voltage limits are extracted from compatible datasheets before string sizing.
- MPPT clamping or infeasible string windows are recorded as branch/design events.
- DC voltage drop uses loop length/resistance and preserves one-way route length separately.
- PFC uses initial PF, target PF, real power, and reactive power with explicit source roles.
- Feeder and line voltage calculations use the declared real/reactive load case and impedance source.
- Cable voltage-drop table rows cite conductor material, size, circuit type, and criterion.
- Fault-current calculations record source, transformer, cable, and total impedance separately.
- IEC voltage factor inference matches the voltage class before fault-current output is trusted.

## Detailed Setting: Electrical Cables Lines Earthing And Fault Safety

Detailed pass: `detailed-passes/electrical-cables-lines-earthing-fault-safety-015.md`

Candidate operation handles for explicit world sidecars:

- `source_artifacts.cable_schedule`
- `source_artifacts.installation_drawing`
- `source_artifacts.ampacity_table`
- `source_artifacts.conductor_datasheet`
- `source_artifacts.operating_temperature_table`
- `source_artifacts.overhead_line_geometry`
- `source_artifacts.tower_geometry`
- `source_artifacts.weather_table`
- `source_artifacts.terrain_map`
- `source_artifacts.surface_condition_note`
- `source_artifacts.switchboard_layout`
- `source_artifacts.busbar_detail`
- `source_artifacts.protection_study`
- `source_artifacts.arc_flash_label`
- `source_artifacts.earthing_layout`
- `source_artifacts.soil_resistivity_report`
- `source_artifacts.grid_conductor_schedule`
- `source_artifacts.line_parameter_schedule`
- `source_artifacts.bundle_detail`
- `source_artifacts.ole_span_schedule`
- `source_artifacts.contact_wire_datasheet`
- `source_artifacts.tensioning_table`
- `branch_decisions.conductor_material_source`
- `branch_decisions.insulation_type_source`
- `branch_decisions.installation_method_source`
- `branch_decisions.grouping_basis`
- `branch_decisions.surface_condition_source`
- `branch_decisions.heat_balance_zero_rating`
- `branch_decisions.support_condition_source`
- `branch_decisions.busbar_material_usage`
- `branch_decisions.soil_resistivity_source`
- `branch_decisions.frequency_source`
- `branch_decisions.bundle_count_source`
- `branch_decisions.enclosure_type_source`
- `branch_decisions.electrode_gap_source`
- `branch_decisions.terrain_category_source`
- `branch_decisions.ice_density_source`
- `branch_decisions.wire_weight_source`
- `handoffs.ac_resistance`
- `handoffs.derated_ampacity`
- `handoffs.static_thermal_ampacity`
- `handoffs.peak_fault_current`
- `handoffs.busbar_stress`
- `handoffs.grid_resistance`
- `handoffs.ground_potential_rise`
- `handoffs.line_inductance`
- `handoffs.line_capacitance`
- `handoffs.incident_energy`
- `handoffs.conductor_wind_load`
- `handoffs.conductor_ice_load`
- `handoffs.sag_tension`
- `compliance.cable_ampacity`
- `compliance.busbar_withstand`
- `compliance.grounding_gpr`
- `compliance.arc_flash_ppe`
- `compliance.thermal_rating`
- `compliance.weather_loading`
- `compliance.ole_clearance`

Reusable gates:

- Cable material, insulation, size, installation method, and grouping source rows are recorded before derating.
- AC resistance temperature correction uses the selected conductor material coefficient.
- Weather cases preserve ambient temperature, wind speed/angle, solar radiation, terrain, ice, and surface-condition roles.
- Static thermal rating records zero-net-cooling as a branch event.
- Fault-current handoff distinguishes bolted, arcing, peak, and RMS current values.
- Busbar support condition affects stress; material must not be treated as meaningful until a material-margin output exists.
- Soil resistivity is sourced from the correct site/test layer before grid resistance is calculated.
- Line GMD, GMR, bundle count, and bundle spacing are extracted from compatible geometry.
- Line capacitance and inductance handoffs preserve frequency, voltage, and geometry assumptions.
- Incident energy records equipment class, enclosure, electrode gap, working distance, clearing time, and PPE category.
- Wind and ice loads preserve vertical, transverse, combined, and span-load components.
- OLE sag/tension uses wire weight and horizontal tension; wire diameter requires an explicit role if used for inference.

## Detailed Setting: Electrical Lighting And Energy Performance

Detailed pass: `detailed-passes/electrical-lighting-energy-performance-016.md`

Candidate operation handles for explicit world sidecars:

- `source_artifacts.room_plan`
- `source_artifacts.room_schedule`
- `source_artifacts.luminaire_schedule`
- `source_artifacts.photometric_grid`
- `source_artifacts.lighting_criteria_table`
- `source_artifacts.control_schedule`
- `source_artifacts.daylight_report`
- `source_artifacts.energy_model_zone_table`
- `source_artifacts.road_geometry`
- `source_artifacts.road_lighting_grid`
- `source_artifacts.road_class_table`
- `source_artifacts.road_lighting_layout`
- `source_artifacts.dimming_profile`
- `source_artifacts.system_power_schedule`
- `source_artifacts.field_plan`
- `source_artifacts.sports_lighting_class_table`
- `branch_decisions.design_option_identity`
- `branch_decisions.area_basis`
- `branch_decisions.utilisation_factor_source`
- `branch_decisions.maintenance_factor_source`
- `branch_decisions.photometric_zone_mapping`
- `branch_decisions.target_lighting_class`
- `branch_decisions.daylight_factor_source`
- `branch_decisions.dimmed_hours_source`
- `branch_decisions.illuminated_area_source`
- `branch_decisions.training_vs_match_scenario`
- `handoffs.average_illuminance`
- `handoffs.uniformity_ratio`
- `handoffs.installed_lighting_power`
- `handoffs.annual_lighting_energy`
- `handoffs.leni`
- `handoffs.road_aeci`
- `handoffs.road_pdi`
- `handoffs.sports_uniformity`
- `compliance.interior_illuminance`
- `compliance.interior_uniformity`
- `compliance.road_uniformity`
- `compliance.sports_lighting`
- `compliance.lighting_energy`

Reusable gates:

- Geometry, luminaire schedule, photometric grid, target class, and power schedule share one design-option identity.
- Room, road, field, task-plane, and illuminated-area definitions are not interchangeable.
- Utilisation and maintenance factors cite a source before lumen-method averages are trusted.
- Minimum, maximum, average, task, surround, and background illuminance/luminance values preserve their grid-zone roles.
- Hidden target classes map to target illuminance or uniformity criteria before margins are computed.
- LENI records installed power, operating hours, control factor, daylight factor, area, and reference benchmark separately.
- Road AECI separates full-output hours from dimmed hours and dimming level.
- Road PDI uses maintained illuminance and illuminated area, not annual energy.
- Margin sign and target source are checked before pass/fail language is emitted.

## Detailed Setting: Electrical Transport Signalling And Vertical Transportation

Detailed pass: `detailed-passes/electrical-transport-signalling-vertical-017.md`

Candidate operation handles for explicit world sidecars:

- `source_artifacts.intersection_plan`
- `source_artifacts.approach_vertical_profile`
- `source_artifacts.speed_survey`
- `source_artifacts.signal_timing_sheet`
- `source_artifacts.design_vehicle_table`
- `source_artifacts.crosswalk_plan`
- `source_artifacts.pedestrian_criteria_table`
- `source_artifacts.track_profile`
- `source_artifacts.signal_layout`
- `source_artifacts.rolling_stock_braking_table`
- `source_artifacts.adhesion_scenario_table`
- `source_artifacts.level_crossing_plan`
- `source_artifacts.track_circuit_plan`
- `source_artifacts.vms_schedule`
- `source_artifacts.message_library`
- `source_artifacts.readability_criteria`
- `source_artifacts.lift_traffic_study`
- `source_artifacts.lift_group_schedule`
- `source_artifacts.escalator_datasheet`
- `source_artifacts.station_concourse_plan`
- `source_artifacts.shaft_plan`
- `source_artifacts.lift_car_datasheet`
- `source_artifacts.accessibility_criteria`
- `branch_decisions.grade_sign_convention`
- `branch_decisions.approach_selection`
- `branch_decisions.all_red_cap_active`
- `branch_decisions.walking_speed_source`
- `branch_decisions.rail_gradient_source`
- `branch_decisions.low_adhesion_source`
- `branch_decisions.danger_point_selection`
- `branch_decisions.system_delay_source`
- `branch_decisions.vms_reading_rate_source`
- `branch_decisions.lift_group_selection`
- `branch_decisions.car_loading_factor_source`
- `branch_decisions.practical_loading_factor_source`
- `branch_decisions.lift_accessibility_class`
- `handoffs.yellow_interval`
- `handoffs.all_red_interval`
- `handoffs.pedestrian_clearance`
- `handoffs.signal_sighting_distance`
- `handoffs.overlap_distance`
- `handoffs.warning_time`
- `handoffs.strike_in_distance`
- `handoffs.vms_message_length_limit`
- `handoffs.lift_handling_capacity`
- `handoffs.lift_interval`
- `handoffs.escalator_capacity`
- `handoffs.shaft_envelope`
- `handoffs.car_dimension_margins`
- `compliance.signal_timing`
- `compliance.rail_sighting`
- `compliance.level_crossing_warning`
- `compliance.vms_readability`
- `compliance.vertical_transport_capacity`
- `compliance.lift_accessibility`

Reusable gates:

- Road and rail grade values cite a sign convention before braking/timing formulas are applied.
- Approach, lane, crosswalk, signal, and phase identities remain bound to one intersection.
- Yellow, all-red, and pedestrian timing outputs record their rounding or cap branches.
- Rail sighting, overlap, and warning-time tasks preserve speed, braking, gradient, reaction, and adhesion roles separately.
- Mechanical braking-distance handoffs must declare whether they use service or emergency braking before rail signalling receives them.
- Danger point and strike-in locations are source-selected from the correct signalling layout.
- VMS message length is counted from the candidate message, not inferred from sign size alone.
- Lift handling capacity and interval use the same lift group and round-trip time.
- Escalator practical capacity records step-width branch and loading factor source.
- Shaft and car dimension checks distinguish internal car, clear opening, shaft envelope, and architectural core dimensions.

## Detailed Setting: Electrical Communications Security And Instrumentation

Detailed pass: `detailed-passes/electrical-comms-security-instrumentation-018.md`

Candidate operation handles for explicit world sidecars:

- `source_artifacts.door_schedule`
- `source_artifacts.access_control_riser`
- `source_artifacts.device_datasheet`
- `source_artifacts.backup_policy`
- `source_artifacts.its_device_inventory`
- `source_artifacts.network_topology`
- `source_artifacts.data_rate_table`
- `source_artifacts.capacity_planning_note`
- `source_artifacts.camera_schedule`
- `source_artifacts.retention_policy`
- `source_artifacts.recording_profile_table`
- `source_artifacts.camera_layout`
- `source_artifacts.surveillance_objective_table`
- `source_artifacts.poe_switch_schedule`
- `source_artifacts.poe_class_table`
- `source_artifacts.conduit_schedule`
- `source_artifacts.cable_schedule`
- `source_artifacts.pathway_drawing`
- `source_artifacts.fibre_schedule`
- `source_artifacts.patching_diagram`
- `source_artifacts.transceiver_datasheet`
- `source_artifacts.radio_datasheet`
- `source_artifacts.path_profile`
- `source_artifacts.obstruction_map`
- `source_artifacts.instrument_datasheet`
- `source_artifacts.loop_schedule`
- `source_artifacts.p_id`
- `source_artifacts.valve_datasheet`
- `source_artifacts.process_datasheet`
- `source_artifacts.fluid_property_table`
- `branch_decisions.segment_membership`
- `branch_decisions.door_controller_grouping`
- `branch_decisions.battery_derating_source`
- `branch_decisions.future_bandwidth_buffer_source`
- `branch_decisions.retention_policy_source`
- `branch_decisions.surveillance_objective`
- `branch_decisions.poe_headroom_source`
- `branch_decisions.conduit_fill_limit_source`
- `branch_decisions.fibre_budget_source`
- `branch_decisions.rf_obstacle_loss_source`
- `branch_decisions.instrument_range_source`
- `branch_decisions.fluid_property_source`
- `branch_decisions.choked_flow`
- `handoffs.access_system_load`
- `handoffs.access_backup_capacity`
- `handoffs.required_bandwidth`
- `handoffs.cctv_storage`
- `handoffs.cctv_ppm`
- `handoffs.poe_headroom`
- `handoffs.conduit_fill`
- `handoffs.fibre_link_margin`
- `handoffs.rf_link_margin`
- `handoffs.instrument_current_signal`
- `handoffs.control_valve_cv`
- `compliance.access_power`
- `compliance.bandwidth_capacity`
- `compliance.cctv_coverage`
- `compliance.cctv_storage`
- `compliance.poe_budget`
- `compliance.conduit_fill`
- `compliance.fibre_link`
- `compliance.rf_link`
- `compliance.instrument_range`
- `compliance.control_valve_cavitation`

Reusable gates:

- Device counts are scoped to the selected building, floor, controller, network segment, or camera group.
- Access controller count, power supply count, and battery capacity preserve separate rounding and derating rules.
- CCTV objective maps to target PPM before camera coverage margin is used.
- CCTV bitrate, recording hours, retention, and overhead are sourced before storage outputs are trusted.
- PoE headroom is checked from total draw, available headroom, required headroom, and margin together.
- Bandwidth calculations distinguish installed demand, overhead, and future buffer.
- Conduit fill counts only the selected pathway cables and preserves conduit internal diameter.
- Fibre budgets preserve fibre, connector, splice, total loss, system budget, and margin roles.
- RF budgets preserve free-space path loss, obstacle loss, received level, sensitivity, and margin roles.
- 4-20 mA scaling records instrument range and validates that process value lies within range.
- Control valve sizing records actual pressure drop, choked pressure drop, effective pressure drop, and choked-flow branch.
