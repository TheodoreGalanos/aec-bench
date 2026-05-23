You are a senior instrumentation and controls engineer specializing in control valve sizing for process plants.

## Problem

Calculate the required flow coefficient (Cv) for a control valve in incompressible liquid service using the ISA-75.01.01 / IEC 60534-2-1 sizing method. Determine whether the flow is choked (cavitating).

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Volumetric flow rate (Q) | {{ flow_rate_m3_h }} | m³/h |
| Upstream pressure (P1) | {{ upstream_pressure_bar }} | bar |
| Downstream pressure (P2) | {{ downstream_pressure_bar }} | bar |
{% if fluid_specific_gravity is defined %}
| Fluid specific gravity (SG) | {{ fluid_specific_gravity }} | - |
{% endif %}
{% if fluid_vapor_pressure_bar is defined %}
| Fluid vapor pressure (Pv) | {{ fluid_vapor_pressure_bar }} | bar |
{% endif %}
{% if fluid_critical_pressure_bar is defined %}
| Fluid critical pressure (Pc) | {{ fluid_critical_pressure_bar }} | bar |
{% endif %}
{% if fl_recovery_factor is defined %}
| Liquid pressure recovery factor (FL) | {{ fl_recovery_factor }} | - |
{% endif %}
{% if archetype_description is defined %}

### Process Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A control valve sizing tool is available at `/workspace/cv-liquid-incompressible_calc.py`. Run it with:

```bash
python3 /workspace/cv-liquid-incompressible_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Actual pressure drop across the valve (bar)
2. Required valve flow coefficient Cv
3. Choked (limiting) pressure drop (bar)
4. Whether the flow is choked (1.0 = choked, 0.0 = not choked)

## Applicable Standards

- ISA-75.01.01 — Industrial-Process Control Valves, Flow capacity sizing equations
- IEC 60534-2-1 — Industrial-process control valves, Part 2-1: Flow capacity

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the ISA-75.01.01 sizing method for incompressible liquids without attached fittings (Fp = 1):
  - **Actual pressure drop:** deltaP = P1 - P2
  - **Critical pressure ratio factor:** FF = 0.96 - 0.28 * sqrt(Pv / Pc)
  - **Choked pressure drop:** deltaP_choked = FL² × (P1 - FF × Pv)
  - **Effective pressure drop:** deltaP_eff = min(deltaP, deltaP_choked)
  - **Choked flow check:** if deltaP >= deltaP_choked, the flow is choked
  - **Metric flow coefficient:** Kv = Q × sqrt(SG / deltaP_eff), where Q in m³/h, deltaP_eff in bar
  - **US flow coefficient:** Cv = 1.156 × Kv
- All pressures are absolute (bar). Specific gravity is dimensionless relative to water at 15°C.

## Output Format

Show your step-by-step working in Markdown, including the choked flow check, effective pressure drop selection, and Cv calculation. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "pressure_drop_bar": <numeric_value>,
  "cv_required": <numeric_value>,
  "choked_pressure_drop_bar": <numeric_value>,
  "is_choked": <1.0_or_0.0>
}
```

Write your complete solution to `/workspace/output.md`.
