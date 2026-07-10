You are a signal and roadside electrical engineer checking a task-owned synthetic SSC-01 bus priority, signal corridor, and cabinet load package.

Use only the task-owned synthetic source pack values below for numeric grading. MUTCD signal timing, transit-priority, detector scheduling, and cabinet feeder workflows shape the context only; they are not extra data sources for this instance.

## Scene

- Product: `SSC-01-LH-05`
- Bus priority plan: `BUS-SSC01-005`
- Signal timing sheet: `SIG-SSC01-005`
- Detector schedule: `DET-SSC01-005`
- Cabinet load schedule: `CAB-SSC01-005`
- Feeder schedule: `FEED-SSC01-005`
- Priority scenario: `AM-PEAK-BUS-PRIORITY`

## Source Values

- Bus approach speed and grade: {{ bus_approach_speed_kmh }} km/h and {{ bus_approach_grade_pct }} %
- Yellow reaction time and deceleration: {{ yellow_reaction_time_s }} s and {{ yellow_deceleration_m_s2 }} m/s2
- Intersection width, bus length, all-red speed: {{ intersection_width_m }} m, {{ bus_length_m }} m, {{ all_red_speed_kmh }} km/h
- Bus throughput source: {{ buses_per_hour }} buses/h at {{ bus_occupancy_pax }} passengers/bus
- Peak passenger demand: {{ peak_passenger_demand_pax_h }} passengers/h
- Cabinet loads: controller {{ controller_load_w }} W, detectors {{ detector_count }} at {{ detector_load_w }} W, transit radio {{ transit_radio_load_w }} W, VMS {{ vms_load_w }} W, signal heads {{ signal_heads_load_w }} W
- Cabinet capacity: {{ cabinet_capacity_w }} W
- Feeder voltage, power factor, length, resistance, and voltage-drop limit: {{ feeder_voltage_v }} V, {{ power_factor }}, {{ feeder_length_km }} km, {{ conductor_resistance_ohm_km }} ohm/km, {{ allowable_voltage_drop_pct }} %
- Battery capacity, efficiency, and backup requirement: {{ battery_capacity_kwh }} kWh, {{ battery_efficiency }}, {{ required_backup_h }} h

## Required Calculations

- Yellow interval is `reaction + v / (2 x deceleration + 2 x g x grade)`.
- All-red interval is `(intersection width + bus length) / all-red speed`.
- Bus handling capacity is buses per hour times passengers per bus.
- Cabinet load is the sum of controller, detector, radio, VMS, and signal-head loads.
- Feeder current is cabinet load divided by voltage and power factor.
- Feeder voltage drop is `2 x length x resistance x current / voltage x 100`.
- Battery runtime is `capacity x efficiency / (cabinet load / 1000)`.
- Overall pass score is `1.0` only when timing, capacity, load, voltage, and battery margins pass.

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the source IDs above and state that the baseline source pack passes the current synthetic checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable source-pack hardening, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "yellow_interval_s": <numeric_value>,
  "all_red_interval_s": <numeric_value>,
  "bus_handling_capacity_pax_h": <numeric_value>,
  "bus_capacity_margin_pax_h": <numeric_value>,
  "cabinet_load_w": <numeric_value>,
  "cabinet_load_margin_w": <numeric_value>,
  "feeder_current_a": <numeric_value>,
  "feeder_voltage_drop_percent": <numeric_value>,
  "voltage_drop_margin_percent": <numeric_value>,
  "battery_runtime_h": <numeric_value>,
  "battery_margin_h": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
