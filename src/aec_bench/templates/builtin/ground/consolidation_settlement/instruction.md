You are a senior geotechnical engineer specializing in foundation settlement analysis.

## Task

Calculate the primary consolidation settlement of a clay layer using **Terzaghi's one-dimensional consolidation theory**.

## Given Parameters

| Parameter | Value | Unit |
|-----------|-------|------|
| Clay layer thickness (H) | {{ clay_thickness_m }} | m |
{% if compression_index_cc is defined %}| Compression index (Cc) | {{ compression_index_cc }} | - |
{% endif %}{% if recompression_index_cr is defined %}| Recompression index (Cr) | {{ recompression_index_cr }} | - |
{% endif %}{% if initial_void_ratio_e0 is defined %}| Initial void ratio (e₀) | {{ initial_void_ratio_e0 }} | - |
{% endif %}| Preconsolidation pressure (σ'p) | {{ preconsolidation_pressure_kpa }} | kPa |
| Initial effective stress (σ'v0) | {{ initial_effective_stress_kpa }} | kPa |
| Final effective stress (σ'vf) | {{ final_effective_stress_kpa }} | kPa |

{% if archetype_description is defined %}
### Site Conditions

{{ archetype_description }}
{% endif %}

## Method

Use **Terzaghi's 1D consolidation settlement** equations. First determine the overconsolidation ratio:

**OCR = σ'p / σ'v0**

Then calculate settlement based on the stress state:

### Case 1: Normally Consolidated (OCR ≤ 1)

**S_c = (Cc × H) / (1 + e₀) × log₁₀(σ'vf / σ'v0)**

### Case 2: Overconsolidated, remains OC (σ'vf ≤ σ'p)

**S_c = (Cr × H) / (1 + e₀) × log₁₀(σ'vf / σ'v0)**

### Case 3: Overconsolidated, becomes NC (σ'vf > σ'p)

**S_c = (Cr × H) / (1 + e₀) × log₁₀(σ'p / σ'v0) + (Cc × H) / (1 + e₀) × log₁₀(σ'vf / σ'p)**

## Constraints

- No internet access is available.
- Use the exact equations specified above.
- Use base-10 logarithm (log₁₀).
- Report settlement in millimetres (mm).
- Determine which case applies based on OCR and the relationship between σ'vf and σ'p.

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

1. Overconsolidation ratio (OCR)
2. Primary consolidation settlement S_c (mm)

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "ocr": <value>,
  "settlement_mm": <value>
}
```

Write your complete solution to `/workspace/output.md`.
