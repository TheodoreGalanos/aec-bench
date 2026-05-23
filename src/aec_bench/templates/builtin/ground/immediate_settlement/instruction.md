You are a senior geotechnical engineer specializing in foundation settlement analysis.

## Task

Calculate the elastic (immediate) settlement of a shallow foundation using **Boussinesq elastic theory** with shape-dependent influence factors.

## Given Parameters

| Parameter | Value | Unit |
|-----------|-------|------|
| Applied pressure (q) | {{ applied_pressure_kpa }} | kPa |
| Footing width (B) | {{ footing_width_m }} | m |
| Footing length (L) | {{ footing_length_m }} | m |
{% if elastic_modulus_mpa is defined %}| Elastic modulus (E) | {{ elastic_modulus_mpa }} | MPa |
{% endif %}{% if poisson_ratio is defined %}| Poisson's ratio (ν) | {{ poisson_ratio }} | - |
{% endif %}| Footing shape | {{ footing_shape }} | - |
| Foundation rigidity | {{ foundation_rigidity }} | - |

{% if archetype_description is defined %}
### Site Conditions

{{ archetype_description }}
{% endif %}

## Method

Use the **elastic settlement equation**:

**S_i = q × B × (1 − ν²) / E × I_f**

where:
- q = net applied pressure (kPa)
- B = footing width (shorter dimension, m)
- ν = Poisson's ratio
- E = elastic modulus (convert to kPa: 1 MPa = 1000 kPa)
- I_f = influence factor (depends on shape and rigidity)

### Influence Factors

For flexible rectangular footings at the centre (Bowles, 1996):

| L/B | I_f |
|-----|-----|
| 1.0 | 1.12 |
| 1.5 | 1.36 |
| 2.0 | 1.53 |
| 3.0 | 1.78 |
| 5.0 | 2.10 |
| 10.0 | 2.54 |

Interpolate linearly for intermediate L/B values.

For circular footings (flexible centre): I_f = 1.00

For rigid foundations: multiply the flexible I_f by 0.80

## Constraints

- No internet access is available.
- Use the exact equation and influence factor table specified above.
- B is always the shorter dimension (B ≤ L).
- Convert elastic modulus from MPa to kPa before calculation.
- Report settlement in millimetres (mm).

{% if tool_available %}
## Available Tool

A calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate:

1. Influence factor I_f (accounting for shape and rigidity)
2. Immediate settlement S_i (mm)

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "influence_factor": <value>,
  "settlement_mm": <value>
}
```

Write your complete solution to `/workspace/output.md`.
