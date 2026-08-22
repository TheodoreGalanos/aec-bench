You are a senior mechanical engineer specializing in pump duty calculations.

## Problem

Calculate hydraulic pump power and shaft power from flow, head, fluid density, and pump efficiency.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Flow rate | 742.84 | L/s |
| Total dynamic head | 40.51 | m |
| Fluid density | 995.58 | kg/m3 |
| Pump efficiency | 49.1 | % |


### Pump Context

Water pump power calculation



## Available Tool

A pump power calculation tool is available at `/workspace/pump-power-calculation_calc.py`. Run it with:

```bash
python3 /workspace/pump-power-calculation_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.


## Required

Calculate the following:

1. Flow rate in m3/s
2. Hydraulic power in kW
3. Shaft power in kW
4. Pump efficiency as a fraction

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use g = 9.81 m/s2.
- Use hydraulic power = density x g x flow x head.
- Use shaft power = hydraulic power / efficiency fraction.

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "flow_rate_m3_s": <numeric_value>,
  "hydraulic_power_kw": <numeric_value>,
  "shaft_power_kw": <numeric_value>,
  "efficiency_fraction": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
