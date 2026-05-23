You are a senior electrical engineer specializing in power systems protection and short-circuit analysis.

## Problem

Calculate the three-phase short-circuit currents at a specified fault location in a radial network using the IEC 60909-0 simplified method.

The network consists of an upstream source, a single transformer, and a cable run to the fault point.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Nominal system voltage (Un) | {{ system_voltage_kv }} | kV |
| Upstream source fault level (Sk) | {{ source_fault_level_mva }} | MVA |
| Transformer rated power (Sn) | {{ transformer_rated_power_mva }} | MVA |
| Transformer impedance (uk%) | {{ transformer_impedance_percent }} | % |
| Cable resistance | {{ cable_resistance_ohm_per_km }} | ohm/km |
| Cable reactance | {{ cable_reactance_ohm_per_km }} | ohm/km |
| Cable length | {{ cable_length_m }} | m |
{% if voltage_factor_c is defined %}
| Voltage factor c | {{ voltage_factor_c }} | - |
{% endif %}
{% if archetype_description is defined %}

### Installation Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A fault current calculation tool is available at `/workspace/three-phase-fault-current_calc.py`. Run it with:

```bash
python3 /workspace/three-phase-fault-current_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Source impedance referred to system voltage (ohm)
2. Transformer impedance referred to system voltage (ohm)
3. Cable impedance magnitude (ohm)
4. Total short-circuit impedance at the fault point (ohm)
5. Initial symmetrical short-circuit current Ik'' (kA)
6. Peak short-circuit current ip (kA)

## Applicable Standards

- IEC 60909-0:2016 — Short-circuit currents in three-phase a.c. systems, Calculation of currents
- AS 3851 — The calculation of short-circuit currents in three-phase a.c. systems

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the IEC 60909-0 simplified method for a radial network:
  - Source impedance: Zs = c * Un^2 / Sk (assumed purely reactive)
  - Transformer impedance: Zt = (uk% / 100) * Un^2 / Sn (assumed purely reactive)
  - Cable impedance: Zc = sqrt(Rc^2 + Xc^2) where Rc = r * L/1000 and Xc = x * L/1000
  - Total impedance: sum R and X components separately, then Zk = sqrt(R_total^2 + X_total^2)
  - Initial symmetrical current: Ik'' = c * Un / (sqrt(3) * Zk), result in kA
  - Peak current: ip = kappa * sqrt(2) * Ik''
  - Kappa factor: kappa = 1.02 + 0.98 * exp(-3 * R/X)
- All impedances are referred to the system voltage level.
- Un is in kV, Sk and Sn are in MVA, impedances are in ohm.

## Output Format

Show your step-by-step working in Markdown, including each impedance calculation, the total impedance, and the fault current derivations. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "source_impedance_ohm": <numeric_value>,
  "transformer_impedance_ohm": <numeric_value>,
  "cable_impedance_ohm": <numeric_value>,
  "total_impedance_ohm": <numeric_value>,
  "initial_symmetrical_current_ka": <numeric_value>,
  "peak_current_ka": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
