You are a senior mechanical engineer specializing in engineering acoustics.

## Task

Calculate the total unweighted and A-weighted sound pressure levels for the octave-band spectrum in {{ site_context }}.

## Given

| Octave band | Level | Unit | A-weighting correction |
| --- | ---: | --- | ---: |
| 31.5 Hz | {{ level_31_5_hz_db }} | dB | -39.4 dB |
| 63 Hz | {{ level_63_hz_db }} | dB | -26.2 dB |
| 125 Hz | {{ level_125_hz_db }} | dB | -16.1 dB |
| 250 Hz | {{ level_250_hz_db }} | dB | -8.6 dB |
| 500 Hz | {{ level_500_hz_db }} | dB | -3.2 dB |
| 1000 Hz | {{ level_1000_hz_db }} | dB | 0.0 dB |
| 2000 Hz | {{ level_2000_hz_db }} | dB | 1.2 dB |
| 4000 Hz | {{ level_4000_hz_db }} | dB | 1.0 dB |

## Constraints

- No internet access is available.
- Apply the listed A-weighting correction to each octave-band level before summing.
- Use logarithmic summation: `L_total = 10 log10(sum(10^(L_i/10)))`.

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

- Total unweighted level (`total_linear_level_db`)
- Total A-weighted level (`a_weighted_total_dba`)
- A-weighting adjustment (`a_weighting_adjustment_db`)

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "total_linear_level_db": <numeric_value>,
  "a_weighted_total_dba": <numeric_value>,
  "a_weighting_adjustment_db": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
