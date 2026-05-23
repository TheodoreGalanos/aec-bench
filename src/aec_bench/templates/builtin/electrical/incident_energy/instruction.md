You are a senior electrical engineer specializing in power systems safety and arc flash hazard assessment.

## Problem

Calculate the arc flash incident energy and determine the required PPE category for electrical equipment using the IEEE 1584 empirical method and NFPA 70E.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| System voltage | {{ system_voltage_v }} | V |
| Bolted fault current | {{ bolted_fault_current_ka }} | kA |
| Protective device clearing time | {{ clearing_time_s }} | s |
| Working distance | {{ working_distance_mm }} | mm |
{% if electrode_gap_mm is defined %}
| Electrode gap | {{ electrode_gap_mm }} | mm |
{% endif %}
{% if enclosure_type is defined %}
| Enclosure type | {{ enclosure_type }} | - |
{% endif %}
{% if archetype_description is defined %}

### Equipment Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

An arc flash calculation tool is available at `/workspace/incident-energy_calc.py`. Run it with:

```bash
python3 /workspace/incident-energy_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Arcing fault current (kA) — from the IEEE 1584 empirical equation
2. Incident energy at the working distance (cal/cm2)
3. Arc flash boundary distance where incident energy equals 1.2 cal/cm2 (mm)
4. Required PPE category (integer 0-4 per NFPA 70E)

## Applicable Standards

- IEEE 1584 — Guide for Performing Arc-Flash Hazard Calculations
- NFPA 70E — Standard for Electrical Safety in the Workplace

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the IEEE 1584 empirical method:
  - **Arcing current (systems <= 1000 V):**
    lg(Ia) = K + 0.662*lg(Ibf) + 0.0966*V + 0.000526*G + 0.5588*V*lg(Ibf) - 0.00304*G*lg(Ibf)
    where K = -0.153 (open) or -0.097 (box/MCC), V is voltage in kV, G is electrode gap in mm, Ibf is bolted fault current in kA
  - **Arcing current (systems > 1000 V):**
    lg(Ia) = 0.00402 + 0.983*lg(Ibf)
  - **Normalized incident energy:**
    lg(En) = K1 + K2 + 1.081*lg(Ia) + 0.0011*G
    where K1 = -0.792 (open) or -0.555 (box/MCC), K2 = -0.113 (grounded) or 0 (ungrounded)
  - **Incident energy:**
    E = 4.184 * Cf * En * (t/0.2) * (610^x / D^x)
    where Cf = 1.5 (<= 1 kV) or 1.0 (> 1 kV), t is clearing time in seconds, D is working distance in mm
  - **Arc flash boundary:**
    DB = [4.184 * Cf * En * (t/0.2) * (610^x / Eb)]^(1/x)
    where Eb = 1.2 cal/cm2
- Distance exponents (x): open = 2.000, box = 1.473, MCC = 0.973
- Assume a grounded system (K2 = -0.113)
- PPE categories per NFPA 70E: 0 (< 1.2 cal/cm2), 1 (1.2-4), 2 (4-8), 3 (8-25), 4 (25-40)

## Output Format

Show your step-by-step working in Markdown, including the arcing current calculation, normalized incident energy, final incident energy, arc flash boundary, and PPE determination. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "arcing_current_ka": <numeric_value>,
  "incident_energy_cal_cm2": <numeric_value>,
  "arc_flash_boundary_mm": <numeric_value>,
  "ppe_category": <integer_0_to_4>
}
```

Write your complete solution to `/workspace/output.md`.
