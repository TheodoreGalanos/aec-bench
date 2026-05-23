You are a senior electrical engineer specializing in solar PV system design.

## Problem

Calculate the DC/AC ratio (inverter loading ratio) for a solar PV installation, estimate the annual clipping losses, and determine the expected annual energy yield per IEC 62548 and AS/NZS 5033.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| DC array capacity | {{ dc_array_capacity_kwp }} | kWp |
| Inverter AC capacity | {{ inverter_ac_capacity_kw }} | kW |
{% if annual_psh is defined %}
| Annual peak sun hours | {{ annual_psh }} | h |
{% endif %}
| System losses (excl. clipping) | {{ system_losses_pct }} | % |
{% if archetype_description is defined %}

### Site Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A DC/AC ratio calculation tool is available at `/workspace/dc-ac-ratio_calc.py`. Run it with:

```bash
python3 /workspace/dc-ac-ratio_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. DC/AC ratio (Inverter Loading Ratio, ILR) — ratio of DC array capacity to inverter AC capacity
2. Estimated annual clipping loss (%) — energy lost when DC output exceeds inverter capacity
3. Annual energy yield (kWh) — total AC energy produced over one year
4. Specific yield (kWh/kWp) — energy produced per kWp of installed DC capacity

## Applicable Standards

- IEC 62548 — Photovoltaic (PV) arrays — Design requirements
- AS/NZS 5033 — Installation and safety requirements for photovoltaic (PV) arrays

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- DC/AC ratio: ILR = DC array capacity (kWp) / inverter AC capacity (kW)
- Clipping loss estimation (quadratic model for moderate-irradiance sites):
  - For ILR ≤ 1.0: clipping = 0%
  - For ILR > 1.0: clipping_pct = 10.0 × (ILR - 1)² + (-0.5) × (ILR - 1), minimum 0%
- Inverter efficiency: 96.5% (CEC weighted)
- Annual energy yield: E = P_dc × PSH × (1 - system_losses/100) × η_inv × (1 - clipping/100)
- Specific yield: E / P_dc (kWh per kWp)

## Output Format

Show your step-by-step working in Markdown, including the ILR calculation, clipping loss estimation, and energy yield computation. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "dc_ac_ratio": <numeric_value>,
  "estimated_clipping_loss_pct": <numeric_value>,
  "annual_energy_yield_kwh": <numeric_value>,
  "specific_yield_kwh_per_kwp": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
