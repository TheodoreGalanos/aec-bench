# ABOUTME: Detailed task-world review for electrical traffic, rail signalling, ITS, and vertical transportation tasks.
# ABOUTME: Records multimodal, composition, and meta-harness opportunities for the fourth electrical discipline slice.

# Electrical Transport Signalling And Vertical Transportation Pass 017

Review date: 2026-06-28

Reviewed task cards:

- `electrical/signal-timing/yellow-interval-calculation`
- `electrical/signal-timing/all-red-interval-calculation`
- `electrical/signal-timing/pedestrian-clearance-time`
- `electrical/signal-sighting/signal-sighting-distance`
- `electrical/signal-sighting/overlap-calculation`
- `electrical/level-crossings/warning-time-calculation`
- `electrical/vms-design/vms-legibility-distance`
- `electrical/traffic-analysis/handling-capacity`
- `electrical/traffic-analysis/interval-calculation`
- `electrical/escalator-design/escalator-capacity`
- `electrical/shaft-sizing/shaft-dimensions`
- `electrical/shaft-sizing/car-dimensions-check`

Source files read for this pass:

- `src/aec_bench/templates/builtin/electrical/yellow_interval_calculation/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/electrical/all_red_interval_calculation/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/electrical/pedestrian_clearance_time/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/electrical/signal_sighting_distance/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/electrical/overlap_calculation/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/electrical/warning_time_calculation/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/electrical/vms_legibility_distance/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/electrical/handling_capacity/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/electrical/interval_calculation/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/electrical/escalator_capacity/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/electrical/shaft_dimensions/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/electrical/car_dimensions_check/{params.toml,instruction.md,engine.py}`

## Slice Read

This slice is transport and movement oriented: road signal timings, rail signal sighting/overlap/level-crossing warnings, VMS readability, lift traffic handling/intervals, escalator capacity, and lift shaft/car envelope checks. The multimodal sources are route profiles, intersection drawings, signal phasing diagrams, crosswalk layouts, rail alignment and gradient tables, braking assumptions, VMS sign schedules, station concourse plans, lift group schedules, car/shaft drawings, and accessibility criteria.

The strongest composition axis is corridor and station movement:

- road approach geometry drives yellow, all-red, and pedestrian clearance timing;
- rail speed, gradient, braking, and reaction assumptions drive signal sighting, overlap, and warning time;
- mechanical braking-distance can feed electrical rail signal sighting and overlap worlds;
- station/passenger demand drives lift handling, interval, escalator capacity, and shaft/car sizing;
- VMS legibility connects road speed, character height, and message length to ITS display design.

The practical meta-harness issue is convention management. Grade sign, speed unit, crossing length, clear width, car capacity, practical loading, and scenario class all need source roles. Otherwise composed worlds will silently mix road grade, rail gradient, mechanical braking sign, and signalling sign conventions.

## Task 1: Yellow Interval Calculation

Current world:

- Computes approach speed in m/s, grade-adjusted denominator, yellow interval, and rounded yellow interval.
- Inputs are approach speed, perception-reaction time, deceleration rate, and road grade.
- Hard mode hides `road_grade_pct`.
- The engine rejects grade/deceleration combinations that create a non-positive denominator.

Multimodal expansion:

- Best first modality: intersection approach drawing plus signal timing sheet.
- A road-profile variant can infer grade from vertical alignment or survey table.
- A hard variant can combine approach speed, grade, and design deceleration from road/signal context.

Requirements:

- Approach speed source.
- Reaction time and deceleration criterion source.
- Road grade source and sign convention.
- Timing rounding rule.

Harness opportunities:

- Add grade sign-convention gate.
- Add approach selection gate.
- Add rounding gate.
- Add infeasible denominator event gate.

Natural products:

- `yellow-interval-calculation -> all-red-interval-calculation` as signal timing package.
- `civil road geometry -> yellow-interval-calculation`.
- `yellow-interval-calculation -> pedestrian-clearance-time` through same intersection context.

Meta-harness handles:

- `projection`: approach plan, vertical profile, speed survey, signal timing sheet.
- `difference`: hide grade and include upstream/downstream profile slopes.
- `product`: yellow interval timing record.

## Task 2: All-Red Interval Calculation

Current world:

- Computes clearance distance, raw all-red interval, and capped all-red interval.
- Inputs are intersection width, vehicle length, and vehicle speed.
- Hard mode hides `vehicle_speed_m_s`.
- The engine caps the final interval at 6.0 s.

Multimodal expansion:

- Best first modality: intersection layout and signal timing plan.
- A design-vehicle variant can source vehicle length from vehicle class.
- A hard variant can infer clearance speed from approach context or timing sheet.

Requirements:

- Intersection width source.
- Design vehicle length source.
- Vehicle speed source.
- Evidence when the 6 s cap applies.

Harness opportunities:

- Add intersection width extraction gate.
- Add design vehicle source gate.
- Add cap-branch gate.
- Add timing package handoff gate.

Natural products:

- `yellow-interval-calculation -> all-red-interval-calculation`.
- `all-red-interval-calculation -> pedestrian-clearance-time`.
- `civil intersection sight distance -> all-red-interval-calculation` through shared approach context.

Meta-harness handles:

- `projection`: intersection plan, design vehicle table, signal timing sheet.
- `difference`: include curb-to-curb, stop-line-to-conflict, and total intersection widths.
- `product`: all-red clearance timing record.

## Task 3: Pedestrian Clearance Time

Current world:

- Computes pedestrian clearance time and rounded-up clearance interval.
- Inputs are crosswalk length and walking speed.
- Hard mode hides `walking_speed_m_s`.
- The output is rounded upward with `ceil`.

Multimodal expansion:

- Best first modality: crosswalk layout plus accessibility/design criteria.
- An accessibility variant can infer walking speed from pedestrian population or design standard.
- A hard variant can combine diagonal crossings, refuge islands, and staged clearance.

Requirements:

- Crosswalk length source.
- Walking speed source.
- Rounding rule.
- Accessibility/design context.

Harness opportunities:

- Add crossing-length extraction gate.
- Add walking-speed source gate.
- Add rounding gate.
- Add accessible-design branch gate.

Natural products:

- `pedestrian-clearance-time -> signal timing package`.
- `civil road/intersection plan -> pedestrian-clearance-time`.
- `pedestrian-clearance-time -> VMS/ITS pedestrian information` if added.

Meta-harness handles:

- `projection`: crosswalk plan, accessibility criteria table, phasing diagram.
- `difference`: include total crossing and staged refuge crossing lengths.
- `product`: pedestrian clearance timing record.

## Task 4: Signal Sighting Distance

Current world:

- Computes line speed, reaction distance, grade-adjusted braking rate, braking distance, and required sighting distance.
- Inputs are line speed, service braking rate, driver reaction time, and track gradient.
- Hard mode hides `track_gradient_pct`.
- The engine adds grade effect to braking rate and rejects non-positive grade-adjusted braking.

Multimodal expansion:

- Best first modality: rail alignment profile plus signalling sighting form.
- A rolling-stock variant can source braking rate from vehicle class.
- A hard variant can hand off braking distance from mechanical braking tasks or compare against available sighting distance.

Requirements:

- Line speed source.
- Service braking rate source.
- Driver reaction time source.
- Track gradient source and sign convention.
- Available sighting distance source if checking compliance.

Harness opportunities:

- Add rail gradient sign-convention gate.
- Add line-speed source gate.
- Add reaction/braking decomposition gate.
- Add mechanical braking handoff gate.

Natural products:

- `mechanical braking-distance -> signal-sighting-distance`.
- `signal-sighting-distance -> overlap-calculation`.
- `civil rail geometry -> signal-sighting-distance`.

Meta-harness handles:

- `projection`: track profile, signal layout, rolling-stock braking table, sighting form.
- `difference`: hide gradient in route profile.
- `product`: rail signal sighting distance record.

## Task 5: Overlap Calculation

Current world:

- Computes approach speed, gradient-adjusted braking rate, reaction distance, full-speed overlap, timed overlap option, and danger-point clearance.
- Inputs are approach speed, emergency braking rate, track gradient, reaction time, danger point distance, and low adhesion factor.
- Hard mode hides `low_adhesion_factor`.
- Effective braking combines emergency braking, adhesion factor, and grade.

Multimodal expansion:

- Best first modality: signalling layout plus rail braking/adhesion assumptions.
- A route variant can source danger point distance and gradient from signal plans and track profiles.
- A hard variant can test wet/low-adhesion scenarios and compare overlap to available distance.

Requirements:

- Approach speed source.
- Emergency braking and low adhesion source.
- Track gradient source and sign convention.
- Danger point distance source.
- Clearance evidence.

Harness opportunities:

- Add low-adhesion inference gate.
- Add danger-point distance gate.
- Add overlap component gate.
- Add negative-clearance event gate.

Natural products:

- `signal-sighting-distance -> overlap-calculation`.
- `mechanical braking-distance -> overlap-calculation`.
- `warning-time-calculation -> overlap/sighting rail package`.

Meta-harness handles:

- `projection`: signal layout, danger point plan, track profile, adhesion scenario table.
- `difference`: include normal and degraded adhesion cases.
- `product`: rail signal overlap record.

## Task 6: Warning Time Calculation

Current world:

- Computes train speed in m/s, total warning time, strike-in distance, and minimum warning margin.
- Inputs are maximum train speed, minimum warning time, road user clearance, barrier lowering time, and system delay.
- Hard mode hides `system_delay_s`.
- Total warning time is a sum of warning, clearance, barrier, and delay.

Multimodal expansion:

- Best first modality: level crossing plan plus control system timing sheet.
- A road-user variant can source clearance time from crossing geometry and design vehicle/user.
- A hard variant can compare strike-in distance with track circuit or axle counter placement.

Requirements:

- Train speed source.
- Minimum warning time source.
- Clearance/barrier/delay source.
- Strike-in distance source or placement evidence.

Harness opportunities:

- Add system-delay source gate.
- Add timing-component decomposition gate.
- Add strike-in placement gate.
- Add minimum-margin consistency gate.

Natural products:

- `warning-time-calculation -> signal-sighting/overlap rail package`.
- `civil road crossing geometry -> warning-time-calculation`.
- `mechanical braking-distance -> warning-time-calculation` for rail operations context.

Meta-harness handles:

- `projection`: level crossing layout, control timing sheet, train speed table, track circuit plan.
- `difference`: include warning time and total activation time without labels.
- `product`: level crossing warning record.

## Task 7: VMS Legibility Distance

Current world:

- Computes minimum legibility distance, design speed in ft/s, reading time, and message length limit.
- Inputs are character height, design speed, and reading rate.
- Hard mode hides `reading_rate_chars_s`.
- The legibility distance is `character_height_in * 40 ft`.

Multimodal expansion:

- Best first modality: VMS sign schedule plus roadway speed context.
- A message variant can compare candidate message length against available reading time.
- A hard variant can infer reading rate from driver-readability criteria or sign type.

Requirements:

- Character height source.
- Design speed source.
- Reading rate source.
- Message text length source if extended.

Harness opportunities:

- Add sign schedule extraction gate.
- Add reading-rate source gate.
- Add speed unit conversion gate.
- Add message length compliance gate.

Natural products:

- `vms-legibility-distance -> bandwidth-calculation` for ITS sign communications context.
- `civil road geometry/speed -> vms-legibility-distance`.
- `vms-legibility-distance -> road safety messaging package`.

Meta-harness handles:

- `projection`: VMS schedule, roadway speed plan, message library, readability criteria.
- `difference`: include multiple messages and sign sizes.
- `product`: VMS readability record.

## Task 8: Handling Capacity

Current world:

- Computes passengers handled per five minutes and handling capacity percentage.
- Inputs are building population, round-trip time, car capacity, lift count, and car loading factor.
- Hard mode hides `car_loading_factor_pct`.
- The formula uses 300 seconds per five-minute period.

Multimodal expansion:

- Best first modality: lift traffic study plus lift group schedule.
- A building-use variant can infer loading factor from residential/office context.
- A hard variant can combine handling capacity and interval to judge lift group adequacy.

Requirements:

- Building population source.
- Round-trip time source.
- Car capacity and lift count source.
- Loading factor source.
- Handling target if extended.

Harness opportunities:

- Add lift group selection gate.
- Add loading-factor source gate.
- Add five-minute capacity construction gate.
- Add handling/interval combined compliance gate.

Natural products:

- `handling-capacity <-> interval-calculation`.
- `car-dimensions-check -> handling-capacity` through car capacity/context.
- `shaft-dimensions -> handling-capacity` in lift design package.

Meta-harness handles:

- `projection`: lift traffic study, building population schedule, lift group table.
- `difference`: include destination-control and conventional lift groups.
- `product`: lift handling capacity record.

## Task 9: Interval Calculation

Current world:

- Computes average lift interval and arrivals per five minutes.
- Inputs are round-trip time and lift count.
- Hard mode hides `lift_count`.
- It is a compact lift service metric.

Multimodal expansion:

- Best first modality: lift group schedule and traffic study.
- A hard variant can infer lift count from shaft/lift group context.
- A composition variant can compare interval with handling capacity.

Requirements:

- Round-trip time source.
- Lift count source.
- Service interval criterion if extended.

Harness opportunities:

- Add lift-count source gate.
- Add group identity gate.
- Add interval/arrivals consistency gate.
- Add combined lift traffic gate.

Natural products:

- `interval-calculation <-> handling-capacity`.
- `shaft-dimensions -> interval-calculation`.
- `interval-calculation -> passenger movement station package`.

Meta-harness handles:

- `projection`: lift group schedule, traffic study, shaft plan.
- `difference`: include installed lift count and active lift count.
- `product`: lift interval record.

## Task 10: Escalator Capacity

Current world:

- Computes steps per second, persons per step, theoretical capacity, and practical capacity.
- Inputs are escalator speed, step width, step pitch, and practical loading factor.
- Hard mode hides `practical_loading_factor_pct`.
- Persons per step is `1` below 800 mm step width and `2` otherwise.

Multimodal expansion:

- Best first modality: escalator datasheet plus station/concourse demand record.
- A site-context variant can infer practical loading factor from crowding, luggage, or directionality.
- A hard variant can compare escalator capacity with lift handling and pedestrian demand.

Requirements:

- Escalator speed, width, and pitch source.
- Practical loading factor source.
- Passenger demand source if checking adequacy.
- Width branch evidence.

Harness opportunities:

- Add datasheet extraction gate.
- Add persons-per-step branch gate.
- Add practical loading source gate.
- Add passenger-demand handoff gate.

Natural products:

- `escalator-capacity -> handling-capacity` in station vertical movement package.
- `escalator-capacity -> electrical power-load-calculation` through equipment load if added.
- `civil pedestrian demand -> escalator-capacity`.

Meta-harness handles:

- `projection`: escalator datasheet, concourse plan, passenger demand table.
- `difference`: include nominal width and usable step width.
- `product`: escalator passenger capacity record.

## Task 11: Shaft Dimensions

Current world:

- Computes shaft width, shaft depth, pit depth, and headroom.
- Inputs are car dimensions, side/front/rear clearances, counterweight width, rated speed, car count, and inter-car clearance.
- Hard mode hides `rear_clearance_mm`.
- Pit and headroom are simple functions of rated speed.

Multimodal expansion:

- Best first modality: lift layout drawing plus car and shaft schedule.
- A goods/passenger variant can infer rear clearance from lift type/context.
- A hard variant can combine shaft envelope with car dimension/accessibility check.

Requirements:

- Car dimensions source.
- Clearance and counterweight source.
- Speed and car count source.
- Shaft plan identity.

Harness opportunities:

- Add shaft geometry extraction gate.
- Add rear-clearance inference gate.
- Add car-count/inter-car branch gate.
- Add envelope consistency gate.

Natural products:

- `shaft-dimensions -> car-dimensions-check`.
- `shaft-dimensions -> interval/handling-capacity` through lift group context.
- `shaft-dimensions -> architectural coordination package`.

Meta-harness handles:

- `projection`: lift shaft plan, lift datasheet, clearance table, architectural core plan.
- `difference`: include car internal dimensions and shaft dimensions together.
- `product`: lift shaft envelope record.

## Task 12: Car Dimensions Check

Current world:

- Computes width, depth, and door-opening margins plus floor area and rated load density.
- Inputs are actual car width/depth/door opening, rated load, and minimum width/depth/door opening.
- Hard mode hides `minimum_door_opening_mm`.
- The task reports margins but not a binary compliance flag.

Multimodal expansion:

- Best first modality: lift car datasheet plus accessibility or goods-lift criteria table.
- A hard variant can infer minimum door opening from lift class/use.
- A composition variant can feed car dimensions into shaft sizing and lift capacity tasks.

Requirements:

- Actual car dimension source.
- Minimum criteria source.
- Rated load source.
- Margin evidence.

Harness opportunities:

- Add lift class criteria gate.
- Add hidden minimum-door source gate.
- Add margin sign gate.
- Add car/shaft consistency gate.

Natural products:

- `car-dimensions-check -> shaft-dimensions`.
- `car-dimensions-check -> handling-capacity`.
- `car-dimensions-check -> accessibility compliance package`.

Meta-harness handles:

- `projection`: lift car datasheet, accessibility criteria, goods-lift schedule.
- `difference`: include clear door opening and structural opening dimensions.
- `product`: lift car dimensional compliance record.

## Cross-Slice Product Worlds

### Road Signal Timing Package

Candidate chain:

1. Read intersection geometry, approach speed, grade, and signal criteria.
2. Compute yellow interval.
3. Compute all-red clearance.
4. Compute pedestrian clearance.
5. Emit a timing sheet with rounded intervals and branch/cap evidence.

Why it is interesting:

- It is a compact multimodal intersection-world package.
- It uses drawing geometry, speed context, grade, vehicle assumptions, pedestrian criteria, and rounding.
- It can be mutated by approach, grade, design vehicle, accessibility speed, or crossing staging.

### Rail Signalling And Braking Package

Candidate chain:

1. Read rail alignment, speed, gradient, braking table, and signal layout.
2. Compute required sighting distance.
3. Compute overlap distance and danger point clearance.
4. Compute level crossing warning time and strike-in distance.
5. Optionally compare with mechanical braking distance.

Why it is interesting:

- It is one of the strongest cross-discipline task worlds: civil alignment, mechanical braking, electrical signalling.
- It requires explicit grade sign conventions.
- It has good failure events: non-positive braking, negative danger-point clearance, and inadequate warning margin.

### Station Vertical Movement Package

Candidate chain:

1. Read passenger demand, lift group, escalator, and architectural core plans.
2. Compute lift handling capacity and interval.
3. Compute escalator practical capacity.
4. Check car dimensions and shaft envelope.
5. Produce a station/building movement and envelope record.

Why it is interesting:

- It combines passenger demand, equipment capacity, and architectural constraints.
- It has natural multimodal sources: plans, equipment schedules, lift traffic studies, and accessibility criteria.
- It can route failures into equipment count, shaft layout, car size, or operational assumptions.

### VMS Readability And ITS Display Package

Candidate chain:

1. Read VMS sign schedule and road design speed.
2. Compute legibility distance and available reading time.
3. Compare candidate message length.
4. Handoff to communications/bandwidth or road safety messaging tasks.

Why it is interesting:

- It joins physical sign geometry, traffic speed, message content, and ITS communications.
- It can use real text artifacts as evaluation payloads.
- It gives meta-harness changes at the message/content layer as well as the engineering layer.

## Repair And Extension Notes

- Grade sign conventions differ across mechanical braking, road signal, and rail signal templates. Composed worlds need a shared `grade_sign_convention` sidecar before any cross-template braking/sighting pipeline is generated.
- `all-red-interval-calculation` caps the interval at 6.0 s. Future variants should expose whether the cap was active.
- Lift and escalator tasks mostly compute metrics without compliance flags. Product worlds should add criterion gates for acceptable interval, handling capacity, and practical capacity.
- `car-dimensions-check` reports margins but no binary pass/fail; verifier gates should check margin sign before using compliance language.
