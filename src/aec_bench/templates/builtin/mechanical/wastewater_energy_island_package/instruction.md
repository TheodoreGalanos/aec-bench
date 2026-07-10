You are a wastewater process and plant-energy engineer checking a task-owned synthetic SSC-10 wastewater energy island package.

Use only the task-owned synthetic source pack values shown below for numeric grading. BioWin, GPS-X, SUMO, EPA wastewater energy-efficiency guidance, and NREL REopt style workflows shape the context only; this instance does not run those tools or parse a real process model, source pack, or vendor export.

## Scene

- Energy island case: `CASE-SSC10-ENERGY-001`
- Process basis register: `PROCESS-10-BASIS-01`
- Process flow diagram: `PFD-10-AERATION-01`
- Aeration basin: `AER-10-BASIN-01`
- Blower and motor schedule: `BLOWER-10-01`
- Digester and biogas ledger: `DIG-10-BIOGAS-01`
- PV generation schedule: `PV-10-ARRAY-01`
- Battery energy storage: `BESS-10-ISLAND-01`
- Process feeder: `FEEDER-10-480V-01`
- Energy island memo: `MEMO-10-ENERGY-ISLAND-01`

## Process Oxygen Basis

| Item | Value |
|------|-------|
| Design flow | {{ flow_rate_m3_d }} m3/d |
| Influent BOD | {{ influent_bod_mg_l }} mg/L |
| Effluent BOD | {{ effluent_bod_mg_l }} mg/L |
| Influent TKN | {{ influent_tkn_mg_l }} mg/L |
| Effluent TKN | {{ effluent_tkn_mg_l }} mg/L |
| Sludge production | {{ sludge_production_kg_d }} kg/d |
| Denitrified nitrogen | {{ denitrified_nitrogen_mg_l }} mg/L |

Process oxygen checks:

- BOD removed equals `flow_rate_m3_d x (influent_bod_mg_l - effluent_bod_mg_l) / 1000`.
- Nitrogen removed equals `flow_rate_m3_d x (influent_tkn_mg_l - effluent_tkn_mg_l) / 1000`.
- Denitrified nitrogen mass equals `flow_rate_m3_d x denitrified_nitrogen_mg_l / 1000`.
- Carbonaceous oxygen equals `max(bod_removed_kg_d - 1.42 x sludge_production_kg_d, 0)`.
- Nitrogenous oxygen equals `4.57 x nitrogen_removed_kg_d`.
- Denitrification oxygen credit equals `2.86 x denitrified_nitrogen_kg_d`.
- Total oxygen demand equals `max(carbonaceous_oxygen_kg_d + nitrogenous_oxygen_kg_d - denitrification_credit_kg_d, 0)`.

## Blower And Process Load Basis

| Item | Value |
|------|-------|
| Field oxygen transfer efficiency | {{ field_transfer_efficiency }} |
| Air oxygen mass fraction | {{ air_oxygen_mass_fraction }} |
| Air density | {{ air_density_kg_nm3 }} kg/Nm3 |
| Selected blower airflow capacity | {{ blower_airflow_capacity_nm3_h }} Nm3/h |
| Blower discharge pressure | {{ blower_discharge_pressure_kpa }} kPa |
| Blower efficiency | {{ blower_efficiency }} |
| Blower motor efficiency | {{ blower_motor_efficiency }} |
| Selected blower motor rating | {{ selected_blower_motor_kw }} kW |
| Mixer load | {{ mixer_load_kw }} kW |
| Recycle pump load | {{ recycle_pump_load_kw }} kW |
| Controls load | {{ controls_load_kw }} kW |

Blower and process-load checks:

- Oxygen transfer per normal cubic metre of air equals `air_oxygen_mass_fraction x air_density_kg_nm3 x field_transfer_efficiency`.
- Required airflow equals `total_oxygen_kg_d / 24 / oxygen_transfer_kg_nm3`.
- Blower capacity oxygen equals `blower_airflow_capacity_nm3_h x 24 x oxygen_transfer_kg_nm3`.
- Oxygen capacity margin equals blower capacity oxygen minus total oxygen demand.
- Blower shaft power uses the source-owned simplified approximation `(required_airflow_nm3_h / 3600) x blower_discharge_pressure_kpa / blower_efficiency`.
- Blower input power equals blower shaft power divided by blower motor efficiency.
- Blower motor margin equals selected blower motor rating minus blower input power.
- Critical process load equals blower input power plus mixer load plus recycle pump load plus controls load.
- Daily process energy equals critical process load times 24.

## Biogas, PV, BESS, And Feeder Basis

| Item | Value |
|------|-------|
| Volatile solids feed | {{ volatile_solids_feed_kg_d }} kg/d |
| Volatile solids destruction | {{ volatile_solids_destruction_pct }} % |
| Biogas yield | {{ biogas_yield_m3_kg_vs }} m3/kg VS destroyed |
| Methane fraction | {{ methane_fraction }} |
| Methane energy content | {{ methane_energy_kwh_m3 }} kWh/m3 |
| CHP electrical efficiency | {{ chp_electrical_efficiency }} |
| PV generation | {{ pv_generation_kwh_d }} kWh/d |
| BESS nominal capacity | {{ bess_nominal_kwh }} kWh |
| BESS usable SOC fraction | {{ bess_usable_soc_fraction }} |
| BESS inverter efficiency | {{ bess_inverter_efficiency }} |
| BESS reserve | {{ bess_reserve_kwh }} kWh |
| Feeder voltage | {{ feeder_voltage_v }} V |
| Feeder length | {{ feeder_length_km }} km |
| Feeder resistance | {{ feeder_resistance_ohm_per_km }} ohm/km |
| Feeder reactance | {{ feeder_reactance_ohm_per_km }} ohm/km |
| Feeder power factor | {{ feeder_power_factor }} |
| Maximum voltage drop | {{ max_voltage_drop_percent }} % |

Energy island and feeder checks:

- Volatile solids destroyed equals `volatile_solids_feed_kg_d x volatile_solids_destruction_pct / 100`.
- Biogas volume equals volatile solids destroyed times biogas yield.
- Methane volume equals biogas volume times methane fraction.
- Methane energy equals methane volume times methane energy content.
- Biogas electric energy equals methane energy times CHP electrical efficiency.
- Usable BESS energy equals `bess_nominal_kwh x bess_usable_soc_fraction x bess_inverter_efficiency - bess_reserve_kwh`.
- Onsite energy available equals biogas electric energy plus PV generation plus usable BESS energy.
- Island energy margin equals onsite energy available minus daily process energy.
- Process energy intensity equals daily process energy divided by design flow.
- Onsite energy fraction equals onsite energy available divided by daily process energy, capped at 1.0.
- Apparent process power equals critical process load divided by feeder power factor.
- Feeder current equals `apparent_power_kva x 1000 / (sqrt(3) x feeder_voltage_v)`.
- Reactive factor equals `sqrt(1 - feeder_power_factor^2)`.
- Feeder voltage drop percent equals `sqrt(3) x feeder_current_a x feeder_length_km x (feeder_resistance_ohm_per_km x feeder_power_factor + feeder_reactance_ohm_per_km x reactive_factor) / feeder_voltage_v x 100`.
- Voltage drop margin equals maximum voltage drop percent minus feeder voltage drop percent.
- Overall pass score is `1.0` only when oxygen capacity margin, blower motor margin, island energy margin, and voltage drop margin are all non-negative; otherwise it is `0.0`.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Explain the calculations briefly, preserve the object IDs above, and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated BioWin/GPS-X/SUMO/REopt evidence, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "bod_removed_kg_d": <numeric_value>,
  "carbonaceous_oxygen_kg_d": <numeric_value>,
  "nitrogenous_oxygen_kg_d": <numeric_value>,
  "denitrification_credit_kg_d": <numeric_value>,
  "total_oxygen_kg_d": <numeric_value>,
  "required_airflow_nm3_h": <numeric_value>,
  "blower_capacity_oxygen_kg_d": <numeric_value>,
  "oxygen_capacity_margin_kg_d": <numeric_value>,
  "blower_shaft_power_kw": <numeric_value>,
  "blower_input_power_kw": <numeric_value>,
  "blower_motor_margin_kw": <numeric_value>,
  "volatile_solids_destroyed_kg_d": <numeric_value>,
  "biogas_m3_d": <numeric_value>,
  "methane_m3_d": <numeric_value>,
  "methane_energy_kwh_d": <numeric_value>,
  "biogas_electric_energy_kwh_d": <numeric_value>,
  "critical_process_load_kw": <numeric_value>,
  "daily_process_energy_kwh": <numeric_value>,
  "usable_bess_energy_kwh": <numeric_value>,
  "onsite_energy_available_kwh": <numeric_value>,
  "island_energy_margin_kwh": <numeric_value>,
  "process_energy_intensity_kwh_m3": <numeric_value>,
  "onsite_energy_fraction": <numeric_value>,
  "feeder_current_a": <numeric_value>,
  "feeder_voltage_drop_percent": <numeric_value>,
  "voltage_drop_margin_percent": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
