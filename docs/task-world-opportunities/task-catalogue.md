# ABOUTME: Human-readable catalogue of live built-in task templates.
# ABOUTME: Summarises metadata used as the spine for task-world opportunity review.

# Task Catalogue

Live built-in template count: `184`.

## Civil (57)

| Task | Category | Params | Outputs | Hidden Params | Card |
| --- | --- | ---: | ---: | --- | --- |
| `hudson-armor-sizing` | `armor-stability` | 5 | 3 | `rock_density_kg_m3`, `stability_coefficient_kd`, `water_density_kg_m3` | [task-cards/civil/hudson-armor-sizing.md](task-cards/civil/hudson-armor-sizing.md) |
| `freeboard-calculation` | `coastal-drainage` | 5 | 2 | `construction_tolerance_m`, `safety_margin_m`, `slr_allowance_m`, `wave_allowance_m` | [task-cards/civil/freeboard-calculation.md](task-cards/civil/freeboard-calculation.md) |
| `culvert-capacity` | `culvert-design` | 7 | 4 | `invert_elevation_m` | [task-cards/civil/culvert-capacity.md](task-cards/civil/culvert-capacity.md) |
| `detention-volume-preliminary` | `detention-design` | 4 | 2 | `allowable_release_rate_m3_s` | [task-cards/civil/detention-volume-preliminary.md](task-cards/civil/detention-volume-preliminary.md) |
| `orifice-outlet-design` | `detention-design` | 3 | 3 | `discharge_coefficient`, `head_above_centreline_m` | [task-cards/civil/orifice-outlet-design.md](task-cards/civil/orifice-outlet-design.md) |
| `weir-outlet-design` | `detention-design` | 4 | 2 | `discharge_coefficient`, `head_over_weir_m` | [task-cards/civil/weir-outlet-design.md](task-cards/civil/weir-outlet-design.md) |
| `driveway-gradient-check` | `driveway-access` | 4 | 3 | `location_type` | [task-cards/civil/driveway-gradient-check.md](task-cards/civil/driveway-gradient-check.md) |
| `sediment-basin-sizing` | `erosion-sediment` | 6 | 3 | `soil_loss_rate_m3_ha_yr`, `volumetric_runoff_coeff_m3_ha` | [task-cards/civil/sediment-basin-sizing.md](task-cards/civil/sediment-basin-sizing.md) |
| `sewer-pipe-sizing` | `gravity-sewer` | 5 | 4 | `mannings_n` | [task-cards/civil/sewer-pipe-sizing.md](task-cards/civil/sewer-pipe-sizing.md) |
| `sewer-slope-check` | `gravity-sewer` | 3 | 3 | `mannings_n` | [task-cards/civil/sewer-slope-check.md](task-cards/civil/sewer-slope-check.md) |
| `curve-elements` | `horizontal-geometry` | 3 | 6 | `ip_chainage_m` | [task-cards/civil/curve-elements.md](task-cards/civil/curve-elements.md) |
| `min-curve-radius` | `horizontal-geometry` | 3 | 2 | `side_friction_factor` | [task-cards/civil/min-curve-radius.md](task-cards/civil/min-curve-radius.md) |
| `superelevation-rate` | `horizontal-geometry` | 5 | 2 | `side_friction_factor` | [task-cards/civil/superelevation-rate.md](task-cards/civil/superelevation-rate.md) |
| `mannings-pipe-capacity` | `hydraulic-calculations` | 4 | 4 | `mannings_n` | [task-cards/civil/mannings-pipe-capacity.md](task-cards/civil/mannings-pipe-capacity.md) |
| `open-channel-capacity` | `hydraulic-calculations` | 5 | 6 | `mannings_n` | [task-cards/civil/open-channel-capacity.md](task-cards/civil/open-channel-capacity.md) |
| `roadway-spread` | `hydraulic-calculations` | 4 | 2 | `mannings_n` | [task-cards/civil/roadway-spread.md](task-cards/civil/roadway-spread.md) |
| `rational-method` | `hydrologic-calculations` | 3 | 2 | `runoff_coefficient` | [task-cards/civil/rational-method.md](task-cards/civil/rational-method.md) |
| `scs-curve-number` | `hydrologic-calculations` | 2 | 3 | `curve_number` | [task-cards/civil/scs-curve-number.md](task-cards/civil/scs-curve-number.md) |
| `sls-load-combinations` | `load-combinations` | 4 | 6 | `load_category` | [task-cards/civil/sls-load-combinations.md](task-cards/civil/sls-load-combinations.md) |
| `uls-load-combinations` | `load-combinations` | 5 | 6 | `load_category` | [task-cards/civil/uls-load-combinations.md](task-cards/civil/uls-load-combinations.md) |
| `bund-volume-calculation` | `oil-containment` | 8 | 4 | `equipment_footprint_area_m2`, `num_equipment_items` | [task-cards/civil/bund-volume-calculation.md](task-cards/civil/bund-volume-calculation.md) |
| `flap-gate-headloss` | `outfall-hydraulics` | 4 | 4 | `gate_type` | [task-cards/civil/flap-gate-headloss.md](task-cards/civil/flap-gate-headloss.md) |
| `outfall-submergence-check` | `outfall-hydraulics` | 5 | 5 | `tidal_period_hours` | [task-cards/civil/outfall-submergence-check.md](task-cards/civil/outfall-submergence-check.md) |
| `darcy-weisbach-headloss` | `pipe-hydraulics` | 5 | 4 | `roughness_height_mm` | [task-cards/civil/darcy-weisbach-headloss.md](task-cards/civil/darcy-weisbach-headloss.md) |
| `hazen-williams-headloss` | `pipe-hydraulics` | 4 | 3 | `c_factor` | [task-cards/civil/hazen-williams-headloss.md](task-cards/civil/hazen-williams-headloss.md) |
| `pipe-velocity-check` | `pipe-hydraulics` | 3 | 2 | `service_type` | [task-cards/civil/pipe-velocity-check.md](task-cards/civil/pipe-velocity-check.md) |
| `npsh-calculation` | `pump-station` | 6 | 4 | `specific_gravity`, `vapour_pressure_kpa` | [task-cards/civil/npsh-calculation.md](task-cards/civil/npsh-calculation.md) |
| `pump-power-calc` | `pump-station` | 4 | 3 | `motor_efficiency_pct`, `pump_efficiency_pct` | [task-cards/civil/pump-power-calc.md](task-cards/civil/pump-power-calc.md) |
| `thermal-stress-calculation` | `rail-stress` | 4 | 3 | `elastic_modulus_mpa`, `thermal_expansion_coeff_micro_per_c` | [task-cards/civil/thermal-stress-calculation.md](task-cards/civil/thermal-stress-calculation.md) |
| `cerc-longshore-transport` | `sediment-transport` | 6 | 3 | `k_coefficient`, `porosity`, `sediment_density_kg_m3`, `water_density_kg_m3` | [task-cards/civil/cerc-longshore-transport.md](task-cards/civil/cerc-longshore-transport.md) |
| `exit-gradient` | `seepage-analysis` | 5 | 5 | `foundation_soil_type`, `specific_gravity`, `void_ratio` | [task-cards/civil/exit-gradient.md](task-cards/civil/exit-gradient.md) |
| `uplift-pressure` | `seepage-analysis` | 5 | 4 | `drain_efficiency_pct` | [task-cards/civil/uplift-pressure.md](task-cards/civil/uplift-pressure.md) |
| `intersection-sight-distance` | `sight-distance` | 6 | 4 | `setback_distance_m`, `vehicle_type` | [task-cards/civil/intersection-sight-distance.md](task-cards/civil/intersection-sight-distance.md) |
| `ssd-on-grade` | `sight-distance` | 3 | 3 | `reaction_time_s` | [task-cards/civil/ssd-on-grade.md](task-cards/civil/ssd-on-grade.md) |
| `fos-rapid-drawdown` | `slope-stability` | 7 | 4 | `cohesion_kpa`, `friction_angle_deg`, `saturated_unit_weight_kn_m3` | [task-cards/civil/fos-rapid-drawdown.md](task-cards/civil/fos-rapid-drawdown.md) |
| `fos-seismic` | `slope-stability` | 8 | 3 | `cohesion_kpa`, `friction_angle_deg`, `unit_weight_kn_m3` | [task-cards/civil/fos-seismic.md](task-cards/civil/fos-seismic.md) |
| `fos-steady-state` | `slope-stability` | 6 | 3 | `cohesion_kpa`, `friction_angle_deg`, `saturated_unit_weight_kn_m3` | [task-cards/civil/fos-steady-state.md](task-cards/civil/fos-steady-state.md) |
| `lateral-earth-pressure` | `slope-stability` | 7 | 6 | `friction_angle_deg`, `unit_weight_kn_m3` | [task-cards/civil/lateral-earth-pressure.md](task-cards/civil/lateral-earth-pressure.md) |
| `retaining-wall-stability` | `slope-stability` | 11 | 6 | `backfill_friction_angle_deg`, `backfill_unit_weight_kn_m3`, `foundation_cohesion_kpa`, `foundation_friction_angle_deg` | [task-cards/civil/retaining-wall-stability.md](task-cards/civil/retaining-wall-stability.md) |
| `spillway-weir-capacity` | `spillway-hydraulics` | 8 | 5 | `abutment_shape`, `discharge_coefficient`, `pier_shape` | [task-cards/civil/spillway-weir-capacity.md](task-cards/civil/spillway-weir-capacity.md) |
| `stilling-basin-sizing` | `spillway-hydraulics` | 3 | 4 | `tailwater_depth_m` | [task-cards/civil/stilling-basin-sizing.md](task-cards/civil/stilling-basin-sizing.md) |
| `hgl-check` | `stormwater-piped` | 8 | 7 | `mannings_n`, `pit_loss_coefficient` | [task-cards/civil/hgl-check.md](task-cards/civil/hgl-check.md) |
| `pipe-invert-calculation` | `stormwater-piped` | 6 | 5 | `minimum_cover_mm` | [task-cards/civil/pipe-invert-calculation.md](task-cards/civil/pipe-invert-calculation.md) |
| `downpipe-sizing` | `stormwater-roof` | 3 | 4 | `rainfall_intensity_mm_hr` | [task-cards/civil/downpipe-sizing.md](task-cards/civil/downpipe-sizing.md) |
| `gutter-sizing` | `stormwater-roof` | 4 | 4 | `rainfall_intensity_mm_hr` | [task-cards/civil/gutter-sizing.md](task-cards/civil/gutter-sizing.md) |
| `tidal-prism` | `tidal-water-levels` | 5 | 4 | `exchange_duration_h` | [task-cards/civil/tidal-prism.md](task-cards/civil/tidal-prism.md) |
| `cant-calculation` | `track-geometry` | 5 | 3 | `actual_cant_mm`, `max_cant_deficiency_mm` | [task-cards/civil/cant-calculation.md](task-cards/civil/cant-calculation.md) |
| `transition-spiral-length` | `track-geometry` | 6 | 4 | `min_twist_ratio`, `rate_of_change_cant_mm_s`, `rate_of_change_cd_mm_s` | [task-cards/civil/transition-spiral-length.md](task-cards/civil/transition-spiral-length.md) |
| `vertical-curve-design` | `track-geometry` | 4 | 3 | `max_vertical_acceleration_m_s2` | [task-cards/civil/vertical-curve-design.md](task-cards/civil/vertical-curve-design.md) |
| `pollutant-load-estimate` | `water-quality` | 6 | 4 | `emc_tn_mg_l`, `emc_tp_mg_l`, `emc_tss_mg_l` | [task-cards/civil/pollutant-load-estimate.md](task-cards/civil/pollutant-load-estimate.md) |
| `linear-wave-theory` | `wave-climate` | 3 | 5 | `wave_period_s` | [task-cards/civil/linear-wave-theory.md](task-cards/civil/linear-wave-theory.md) |
| `wave-breaking` | `wave-climate` | 4 | 4 | `bottom_slope`, `wave_period_s` | [task-cards/civil/wave-breaking.md](task-cards/civil/wave-breaking.md) |
| `wave-shoaling` | `wave-climate` | 4 | 3 | `deep_water_wave_angle_deg`, `wave_period_s` | [task-cards/civil/wave-shoaling.md](task-cards/civil/wave-shoaling.md) |
| `wave-runup` | `wave-overtopping` | 5 | 3 | `berm_factor`, `roughness_factor`, `wave_period_s` | [task-cards/civil/wave-runup.md](task-cards/civil/wave-runup.md) |
| `design-wind-pressure` | `wind-load-derivation` | 5 | 3 | `air_density_kg_per_m3`, `cdyn` | [task-cards/civil/design-wind-pressure.md](task-cards/civil/design-wind-pressure.md) |
| `design-wind-speed` | `wind-load-derivation` | 6 | 2 | `shielding_multiplier`, `terrain_category` | [task-cards/civil/design-wind-speed.md](task-cards/civil/design-wind-speed.md) |
| `solar-array-wind-load` | `wind-load-derivation` | 8 | 5 | `row_position`, `tilt_angle_deg` | [task-cards/civil/solar-array-wind-load.md](task-cards/civil/solar-array-wind-load.md) |

## Electrical (52)

| Task | Category | Params | Outputs | Hidden Params | Card |
| --- | --- | ---: | ---: | --- | --- |
| `access-controller-sizing` | `access-control` | 9 | 5 | `battery_derating_factor` | [task-cards/electrical/access-controller-sizing.md](task-cards/electrical/access-controller-sizing.md) |
| `incident-energy` | `arc-flash` | 6 | 4 | `electrode_gap_mm`, `enclosure_type` | [task-cards/electrical/incident-energy.md](task-cards/electrical/incident-energy.md) |
| `bess-sizing` | `bess-design` | 5 | 4 | `depth_of_discharge_pct`, `round_trip_efficiency_pct` | [task-cards/electrical/bess-sizing.md](task-cards/electrical/bess-sizing.md) |
| `bess-sizing-basic` | `bess-design` | 5 | 4 | `end_of_life_capacity_retention_pct` | [task-cards/electrical/bess-sizing-basic.md](task-cards/electrical/bess-sizing-basic.md) |
| `busbar-forces` | `busbar-design` | 7 | 3 | `busbar_material`, `support_condition` | [task-cards/electrical/busbar-forces.md](task-cards/electrical/busbar-forces.md) |
| `cable-ampacity` | `cable-sizing` | 6 | 4 | `installation_method`, `insulation_type` | [task-cards/electrical/cable-ampacity.md](task-cards/electrical/cable-ampacity.md) |
| `voltage-drop` | `cable-sizing` | 6 | 4 | `conductor_material` | [task-cards/electrical/voltage-drop.md](task-cards/electrical/voltage-drop.md) |
| `single-span-sag-tension` | `catenary-design` | 4 | 4 | `wire_weight_per_m_n` | [task-cards/electrical/single-span-sag-tension.md](task-cards/electrical/single-span-sag-tension.md) |
| `cctv-storage-calculation` | `cctv-design` | 5 | 3 | `retention_days` | [task-cards/electrical/cctv-storage-calculation.md](task-cards/electrical/cctv-storage-calculation.md) |
| `ppm-calculation` | `cctv-design` | 5 | 3 | `target_ppm` | [task-cards/electrical/ppm-calculation.md](task-cards/electrical/ppm-calculation.md) |
| `cv-liquid-incompressible` | `control-valve-sizing` | 7 | 4 | `fl_recovery_factor`, `fluid_critical_pressure_bar`, `fluid_specific_gravity`, `fluid_vapor_pressure_bar` | [task-cards/electrical/cv-liquid-incompressible.md](task-cards/electrical/cv-liquid-incompressible.md) |
| `ac-resistance-temperature` | `electrical-parameters` | 4 | 3 | `conductor_material` | [task-cards/electrical/ac-resistance-temperature.md](task-cards/electrical/ac-resistance-temperature.md) |
| `line-capacitance` | `electrical-parameters` | 7 | 4 | `frequency_hz` | [task-cards/electrical/line-capacitance.md](task-cards/electrical/line-capacitance.md) |
| `line-inductance` | `electrical-parameters` | 6 | 3 | `bundle_count` | [task-cards/electrical/line-inductance.md](task-cards/electrical/line-inductance.md) |
| `voltage-regulation` | `electrical-parameters` | 6 | 4 | `load_reactive_power_mvar` | [task-cards/electrical/voltage-regulation.md](task-cards/electrical/voltage-regulation.md) |
| `leni-calculation` | `energy-performance` | 6 | 3 | `daylight_factor` | [task-cards/electrical/leni-calculation.md](task-cards/electrical/leni-calculation.md) |
| `road-aeci-calculation` | `energy-performance` | 5 | 2 | `dimmed_hours_per_year` | [task-cards/electrical/road-aeci-calculation.md](task-cards/electrical/road-aeci-calculation.md) |
| `road-pdi-calculation` | `energy-performance` | 3 | 2 | `illuminated_area_m2` | [task-cards/electrical/road-pdi-calculation.md](task-cards/electrical/road-pdi-calculation.md) |
| `escalator-capacity` | `escalator-design` | 4 | 4 | `practical_loading_factor_pct` | [task-cards/electrical/escalator-capacity.md](task-cards/electrical/escalator-capacity.md) |
| `grid-resistance` | `grounding-design` | 6 | 4 | `soil_resistivity_ohm_m` | [task-cards/electrical/grid-resistance.md](task-cards/electrical/grid-resistance.md) |
| `interior-uniformity` | `interior-lighting` | 4 | 3 | `background_average_illuminance_lux` | [task-cards/electrical/interior-uniformity.md](task-cards/electrical/interior-uniformity.md) |
| `bandwidth-calculation` | `its-communications` | 8 | 3 | `future_capacity_buffer_pct` | [task-cards/electrical/bandwidth-calculation.md](task-cards/electrical/bandwidth-calculation.md) |
| `warning-time-calculation` | `level-crossings` | 5 | 4 | `system_delay_s` | [task-cards/electrical/warning-time-calculation.md](task-cards/electrical/warning-time-calculation.md) |
| `lux-level-calculation` | `lighting-design` | 9 | 4 | `utilisation_factor` | [task-cards/electrical/lux-level-calculation.md](task-cards/electrical/lux-level-calculation.md) |
| `pfc-sizing` | `load-flow` | 3 | 4 | `initial_power_factor` | [task-cards/electrical/pfc-sizing.md](task-cards/electrical/pfc-sizing.md) |
| `radial-feeder-voltage-drop` | `load-flow` | 6 | 5 | `load_reactive_power_kvar` | [task-cards/electrical/radial-feeder-voltage-drop.md](task-cards/electrical/radial-feeder-voltage-drop.md) |
| `poe-power-budget` | `poe-network` | 4 | 5 | `required_headroom_pct` | [task-cards/electrical/poe-power-budget.md](task-cards/electrical/poe-power-budget.md) |
| `battery-sizing` | `power-supply` | 8 | 4 | `temperature_derating_factor` | [task-cards/electrical/battery-sizing.md](task-cards/electrical/battery-sizing.md) |
| `power-load-calculation` | `power-supply` | 5 | 4 | `future_expansion_pct` | [task-cards/electrical/power-load-calculation.md](task-cards/electrical/power-load-calculation.md) |
| `road-uniformity-check` | `road-lighting` | 5 | 3 | `target_overall_uniformity` | [task-cards/electrical/road-uniformity-check.md](task-cards/electrical/road-uniformity-check.md) |
| `car-dimensions-check` | `shaft-sizing` | 7 | 5 | `minimum_door_opening_mm` | [task-cards/electrical/car-dimensions-check.md](task-cards/electrical/car-dimensions-check.md) |
| `shaft-dimensions` | `shaft-sizing` | 9 | 4 | `rear_clearance_mm` | [task-cards/electrical/shaft-dimensions.md](task-cards/electrical/shaft-dimensions.md) |
| `three-phase-fault-current` | `short-circuit` | 8 | 6 | `voltage_factor_c` | [task-cards/electrical/three-phase-fault-current.md](task-cards/electrical/three-phase-fault-current.md) |
| `4-20ma-scaling` | `signal-processing` | 3 | 3 | `upper_range_value` | [task-cards/electrical/4-20ma-scaling.md](task-cards/electrical/4-20ma-scaling.md) |
| `overlap-calculation` | `signal-sighting` | 6 | 6 | `low_adhesion_factor` | [task-cards/electrical/overlap-calculation.md](task-cards/electrical/overlap-calculation.md) |
| `signal-sighting-distance` | `signal-sighting` | 4 | 5 | `track_gradient_pct` | [task-cards/electrical/signal-sighting-distance.md](task-cards/electrical/signal-sighting-distance.md) |
| `all-red-interval-calculation` | `signal-timing` | 3 | 3 | `vehicle_speed_m_s` | [task-cards/electrical/all-red-interval-calculation.md](task-cards/electrical/all-red-interval-calculation.md) |
| `pedestrian-clearance-time` | `signal-timing` | 2 | 2 | `walking_speed_m_s` | [task-cards/electrical/pedestrian-clearance-time.md](task-cards/electrical/pedestrian-clearance-time.md) |
| `yellow-interval-calculation` | `signal-timing` | 4 | 4 | `road_grade_pct` | [task-cards/electrical/yellow-interval-calculation.md](task-cards/electrical/yellow-interval-calculation.md) |
| `dc-ac-ratio` | `solar-pv-design` | 4 | 4 | `annual_psh` | [task-cards/electrical/dc-ac-ratio.md](task-cards/electrical/dc-ac-ratio.md) |
| `string-sizing` | `solar-pv-design` | 9 | 4 | `site_max_temp_c`, `site_min_temp_c` | [task-cards/electrical/string-sizing.md](task-cards/electrical/string-sizing.md) |
| `voltage-drop-dc` | `solar-pv-design` | 7 | 4 | `cable_resistivity_ohm_mm2_m` | [task-cards/electrical/voltage-drop-dc.md](task-cards/electrical/voltage-drop-dc.md) |
| `sports-illuminance-uniformity` | `sports-lighting` | 10 | 5 | `target_uniformity_u2` | [task-cards/electrical/sports-illuminance-uniformity.md](task-cards/electrical/sports-illuminance-uniformity.md) |
| `ice-load-calculation` | `structural-loading` | 5 | 6 | `ice_density_kg_m3` | [task-cards/electrical/ice-load-calculation.md](task-cards/electrical/ice-load-calculation.md) |
| `wind-load-conductor` | `structural-loading` | 6 | 3 | `terrain_category` | [task-cards/electrical/wind-load-conductor.md](task-cards/electrical/wind-load-conductor.md) |
| `conduit-fill-calculation` | `structured-cabling` | 4 | 4 | `maximum_fill_pct` | [task-cards/electrical/conduit-fill-calculation.md](task-cards/electrical/conduit-fill-calculation.md) |
| `fiber-link-loss-budget` | `structured-cabling` | 7 | 5 | `system_loss_budget_db` | [task-cards/electrical/fiber-link-loss-budget.md](task-cards/electrical/fiber-link-loss-budget.md) |
| `static-thermal-rating` | `thermal-rating` | 9 | 4 | `absorptivity`, `emissivity` | [task-cards/electrical/static-thermal-rating.md](task-cards/electrical/static-thermal-rating.md) |
| `handling-capacity` | `traffic-analysis` | 5 | 2 | `car_loading_factor_pct` | [task-cards/electrical/handling-capacity.md](task-cards/electrical/handling-capacity.md) |
| `interval-calculation` | `traffic-analysis` | 2 | 2 | `lift_count` | [task-cards/electrical/interval-calculation.md](task-cards/electrical/interval-calculation.md) |
| `vms-legibility-distance` | `vms-design` | 3 | 4 | `reading_rate_chars_s` | [task-cards/electrical/vms-legibility-distance.md](task-cards/electrical/vms-legibility-distance.md) |
| `rf-link-budget` | `wireless-design` | 7 | 4 | `obstacle_losses_db` | [task-cards/electrical/rf-link-budget.md](task-cards/electrical/rf-link-budget.md) |

## Ground (10)

| Task | Category | Params | Outputs | Hidden Params | Card |
| --- | --- | ---: | ---: | --- | --- |
| `lateral-earth-pressure` | `retaining-walls` | 8 | 7 | `cohesion_kpa`, `friction_angle_deg`, `unit_weight_kn_m3` | [task-cards/ground/lateral-earth-pressure.md](task-cards/ground/lateral-earth-pressure.md) |
| `wall-bearing` | `retaining-walls` | 8 | 5 | `soil_cohesion_kpa`, `soil_friction_angle_deg`, `soil_unit_weight_kn_m3` | [task-cards/ground/wall-bearing.md](task-cards/ground/wall-bearing.md) |
| `wall-overturning` | `retaining-walls` | 9 | 5 | `backfill_friction_angle_deg`, `backfill_unit_weight_kn_m3` | [task-cards/ground/wall-overturning.md](task-cards/ground/wall-overturning.md) |
| `consolidation-settlement` | `shallow-foundations` | 7 | 2 | `compression_index_cc`, `initial_void_ratio_e0`, `recompression_index_cr` | [task-cards/ground/consolidation-settlement.md](task-cards/ground/consolidation-settlement.md) |
| `immediate-settlement` | `shallow-foundations` | 7 | 2 | `elastic_modulus_mpa`, `poisson_ratio` | [task-cards/ground/immediate-settlement.md](task-cards/ground/immediate-settlement.md) |
| `meyerhof-bearing-capacity` | `shallow-foundations` | 9 | 14 | `cohesion_kpa`, `friction_angle_deg`, `unit_weight_kn_m3` | [task-cards/ground/meyerhof-bearing-capacity.md](task-cards/ground/meyerhof-bearing-capacity.md) |
| `terzaghi-bearing-capacity` | `shallow-foundations` | 8 | 5 | `cohesion_kpa`, `friction_angle_deg`, `unit_weight_kn_m3` | [task-cards/ground/terzaghi-bearing-capacity.md](task-cards/ground/terzaghi-bearing-capacity.md) |
| `infinite-slope` | `slope-stability` | 6 | 4 | `cohesion_kpa`, `friction_angle_deg`, `unit_weight_kn_m3` | [task-cards/ground/infinite-slope.md](task-cards/ground/infinite-slope.md) |
| `cpt-parameter-derivation` | `soil-interpretation` | 7 | 7 | `net_area_ratio`, `total_unit_weight_kn_m3` | [task-cards/ground/cpt-parameter-derivation.md](task-cards/ground/cpt-parameter-derivation.md) |
| `spt-corrections` | `soil-interpretation` | 6 | 7 | `borehole_diameter_mm`, `hammer_type`, `sampler_type` | [task-cards/ground/spt-corrections.md](task-cards/ground/spt-corrections.md) |

## Mechanical (50)

| Task | Category | Params | Outputs | Hidden Params | Card |
| --- | --- | ---: | ---: | --- | --- |
| `oxygen-requirements` | `activated-sludge` | 7 | 5 |  | [task-cards/mechanical/oxygen-requirements.md](task-cards/mechanical/oxygen-requirements.md) |
| `sludge-production` | `activated-sludge` | 9 | 5 |  | [task-cards/mechanical/sludge-production.md](task-cards/mechanical/sludge-production.md) |
| `braking-distance` | `braking-systems` | 5 | 4 |  | [task-cards/mechanical/braking-distance.md](task-cards/mechanical/braking-distance.md) |
| `slr-calculation` | `clarifier-design` | 4 | 5 |  | [task-cards/mechanical/slr-calculation.md](task-cards/mechanical/slr-calculation.md) |
| `sor-calculation` | `clarifier-design` | 3 | 4 |  | [task-cards/mechanical/sor-calculation.md](task-cards/mechanical/sor-calculation.md) |
| `air-demand` | `compressed-air` | 7 | 4 |  | [task-cards/mechanical/air-demand.md](task-cards/mechanical/air-demand.md) |
| `mass-balance` | `convergence-assessment` | 5 | 5 |  | [task-cards/mechanical/mass-balance.md](task-cards/mechanical/mass-balance.md) |
| `t-squared-hrr` | `design-fire` | 3 | 4 |  | [task-cards/mechanical/t-squared-hrr.md](task-cards/mechanical/t-squared-hrr.md) |
| `egress-width` | `egress-modeling` | 3 | 4 |  | [task-cards/mechanical/egress-width.md](task-cards/mechanical/egress-width.md) |
| `miner-fatigue` | `fatigue-analysis` | 6 | 6 |  | [task-cards/mechanical/miner-fatigue.md](task-cards/mechanical/miner-fatigue.md) |
| `nac-load-calculation` | `fire-services` | 7 | 4 |  | [task-cards/mechanical/nac-load-calculation.md](task-cards/mechanical/nac-load-calculation.md) |
| `a-weighting` | `fundamental-calculations` | 8 | 3 |  | [task-cards/mechanical/a-weighting.md](task-cards/mechanical/a-weighting.md) |
| `chemical-dosing` | `fundamental-calculations` | 4 | 4 |  | [task-cards/mechanical/chemical-dosing.md](task-cards/mechanical/chemical-dosing.md) |
| `distance-attenuation` | `fundamental-calculations` | 3 | 3 |  | [task-cards/mechanical/distance-attenuation.md](task-cards/mechanical/distance-attenuation.md) |
| `hrt-calculation` | `fundamental-calculations` | 2 | 3 |  | [task-cards/mechanical/hrt-calculation.md](task-cards/mechanical/hrt-calculation.md) |
| `mlss-inventory` | `fundamental-calculations` | 3 | 3 |  | [task-cards/mechanical/mlss-inventory.md](task-cards/mechanical/mlss-inventory.md) |
| `sabine-rt60` | `fundamental-calculations` | 7 | 3 |  | [task-cards/mechanical/sabine-rt60.md](task-cards/mechanical/sabine-rt60.md) |
| `spl-log-sum` | `fundamental-calculations` | 3 | 3 |  | [task-cards/mechanical/spl-log-sum.md](task-cards/mechanical/spl-log-sum.md) |
| `srt-calculation` | `fundamental-calculations` | 6 | 5 |  | [task-cards/mechanical/srt-calculation.md](task-cards/mechanical/srt-calculation.md) |
| `gas-load-calculation` | `gas-services` | 7 | 4 |  | [task-cards/mechanical/gas-load-calculation.md](task-cards/mechanical/gas-load-calculation.md) |
| `lmtd-calculation` | `heat-exchanger-design` | 8 | 6 |  | [task-cards/mechanical/lmtd-calculation.md](task-cards/mechanical/lmtd-calculation.md) |
| `available-flow-calculation` | `hydrant-flow-test` | 4 | 4 |  | [task-cards/mechanical/available-flow-calculation.md](task-cards/mechanical/available-flow-calculation.md) |
| `water-supply-curve` | `hydrant-flow-test` | 4 | 4 |  | [task-cards/mechanical/water-supply-curve.md](task-cards/mechanical/water-supply-curve.md) |
| `gci-calculation` | `mesh-independence` | 4 | 5 |  | [task-cards/mechanical/gci-calculation.md](task-cards/mechanical/gci-calculation.md) |
| `nitrification-srt` | `nutrient-removal` | 9 | 5 |  | [task-cards/mechanical/nitrification-srt.md](task-cards/mechanical/nitrification-srt.md) |
| `hazen-williams-friction` | `pipe-hydraulics` | 5 | 4 |  | [task-cards/mechanical/hazen-williams-friction.md](task-cards/mechanical/hazen-williams-friction.md) |
| `minor-losses-calculation` | `pipe-hydraulics` | 9 | 4 |  | [task-cards/mechanical/minor-losses-calculation.md](task-cards/mechanical/minor-losses-calculation.md) |
| `velocity-check` | `pipe-hydraulics` | 4 | 5 |  | [task-cards/mechanical/velocity-check.md](task-cards/mechanical/velocity-check.md) |
| `pressure-loss-calculation` | `pipe-sizing-water` | 6 | 4 |  | [task-cards/mechanical/pressure-loss-calculation.md](task-cards/mechanical/pressure-loss-calculation.md) |
| `occupant-load` | `prescriptive-compliance` | 2 | 3 |  | [task-cards/mechanical/occupant-load.md](task-cards/mechanical/occupant-load.md) |
| `npsh-available` | `pump-hydraulics` | 6 | 6 |  | [task-cards/mechanical/npsh-available.md](task-cards/mechanical/npsh-available.md) |
| `pump-head-calculation` | `pump-hydraulics` | 6 | 5 |  | [task-cards/mechanical/pump-head-calculation.md](task-cards/mechanical/pump-head-calculation.md) |
| `pump-power-efficiency` | `pump-hydraulics` | 6 | 4 |  | [task-cards/mechanical/pump-power-efficiency.md](task-cards/mechanical/pump-power-efficiency.md) |
| `pump-affinity-laws` | `pump-sizing` | 5 | 4 |  | [task-cards/mechanical/pump-affinity-laws.md](task-cards/mechanical/pump-affinity-laws.md) |
| `pump-power-calculation` | `pump-sizing` | 4 | 4 |  | [task-cards/mechanical/pump-power-calculation.md](task-cards/mechanical/pump-power-calculation.md) |
| `cstr-volume` | `reactor-sizing` | 4 | 4 |  | [task-cards/mechanical/cstr-volume.md](task-cards/mechanical/cstr-volume.md) |
| `pfr-volume` | `reactor-sizing` | 4 | 4 |  | [task-cards/mechanical/pfr-volume.md](task-cards/mechanical/pfr-volume.md) |
| `biogas-production` | `sludge-handling` | 4 | 4 |  | [task-cards/mechanical/biogas-production.md](task-cards/mechanical/biogas-production.md) |
| `elevation-pressure` | `sprinkler-hydraulics` | 2 | 3 |  | [task-cards/mechanical/elevation-pressure.md](task-cards/mechanical/elevation-pressure.md) |
| `friction-loss-hazen-williams` | `sprinkler-hydraulics` | 5 | 4 |  | [task-cards/mechanical/friction-loss-hazen-williams.md](task-cards/mechanical/friction-loss-hazen-williams.md) |
| `sprinkler-discharge` | `sprinkler-hydraulics` | 2 | 3 |  | [task-cards/mechanical/sprinkler-discharge.md](task-cards/mechanical/sprinkler-discharge.md) |
| `steel-critical-temp` | `structural-fire` | 2 | 3 |  | [task-cards/mechanical/steel-critical-temp.md](task-cards/mechanical/steel-critical-temp.md) |
| `por-aor-compliance` | `system-curves` | 6 | 5 |  | [task-cards/mechanical/por-aor-compliance.md](task-cards/mechanical/por-aor-compliance.md) |
| `visibility-criterion` | `tenability-assessment` | 3 | 4 |  | [task-cards/mechanical/visibility-criterion.md](task-cards/mechanical/visibility-criterion.md) |
| `thrust-force-calculation` | `thrust-restraint` | 3 | 3 |  | [task-cards/mechanical/thrust-force-calculation.md](task-cards/mechanical/thrust-force-calculation.md) |
| `davis-resistance` | `train-resistance-dynamics` | 5 | 4 |  | [task-cards/mechanical/davis-resistance.md](task-cards/mechanical/davis-resistance.md) |
| `joukowsky-pressure` | `transient-analysis` | 3 | 3 |  | [task-cards/mechanical/joukowsky-pressure.md](task-cards/mechanical/joukowsky-pressure.md) |
| `wave-speed-calculation` | `transient-analysis` | 6 | 4 |  | [task-cards/mechanical/wave-speed-calculation.md](task-cards/mechanical/wave-speed-calculation.md) |
| `air-changes` | `ventilation` | 2 | 1 |  | [task-cards/mechanical/air-changes.md](task-cards/mechanical/air-changes.md) |
| `vibration-transmissibility` | `vibration` | 3 | 3 |  | [task-cards/mechanical/vibration-transmissibility.md](task-cards/mechanical/vibration-transmissibility.md) |

## Structural (15)

| Task | Category | Params | Outputs | Hidden Params | Card |
| --- | --- | ---: | ---: | --- | --- |
| `berthing-energy-calc` | `berthing-energy` | 7 | 4 |  | [task-cards/structural/berthing-energy-calc.md](task-cards/structural/berthing-energy-calc.md) |
| `bracket-load-calc` | `bracket-connection` | 6 | 4 |  | [task-cards/structural/bracket-load-calc.md](task-cards/structural/bracket-load-calc.md) |
| `scm-substitution` | `concrete-mix-design` | 3 | 4 |  | [task-cards/structural/scm-substitution.md](task-cards/structural/scm-substitution.md) |
| `target-strength-calc` | `concrete-mix-design` | 4 | 4 |  | [task-cards/structural/target-strength-calc.md](task-cards/structural/target-strength-calc.md) |
| `construction-tolerance` | `construction-tolerance` | 6 | 4 |  | [task-cards/structural/construction-tolerance.md](task-cards/structural/construction-tolerance.md) |
| `fender-energy-check` | `fender-design` | 6 | 4 |  | [task-cards/structural/fender-energy-check.md](task-cards/structural/fender-energy-check.md) |
| `load-combinations` | `load-analysis` | 14 | 6 |  | [task-cards/structural/load-combinations.md](task-cards/structural/load-combinations.md) |
| `mooring-line-capacity` | `marine-mooring` | 4 | 5 |  | [task-cards/structural/mooring-line-capacity.md](task-cards/structural/mooring-line-capacity.md) |
| `thermal-movement-calc` | `movement-tolerance` | 4 | 4 | `coefficient_thermal_expansion_microstrain_c` | [task-cards/structural/thermal-movement-calc.md](task-cards/structural/thermal-movement-calc.md) |
| `pipe-support-dead-load` | `pipe-support` | 7 | 5 |  | [task-cards/structural/pipe-support-dead-load.md](task-cards/structural/pipe-support-dead-load.md) |
| `lap-splice-length` | `rebar-detailing` | 5 | 4 |  | [task-cards/structural/lap-splice-length.md](task-cards/structural/lap-splice-length.md) |
| `carbon-equivalent-calc` | `steel-specification` | 9 | 5 |  | [task-cards/structural/carbon-equivalent-calc.md](task-cards/structural/carbon-equivalent-calc.md) |
| `composite-section` | `superstructure-design` | 11 | 5 |  | [task-cards/structural/composite-section.md](task-cards/structural/composite-section.md) |
| `effective-wind-area` | `wind-load-analysis` | 5 | 4 |  | [task-cards/structural/effective-wind-area.md](task-cards/structural/effective-wind-area.md) |
| `gravity-base-stability` | `wind-turbine-foundations` | 5 | 5 |  | [task-cards/structural/gravity-base-stability.md](task-cards/structural/gravity-base-stability.md) |

