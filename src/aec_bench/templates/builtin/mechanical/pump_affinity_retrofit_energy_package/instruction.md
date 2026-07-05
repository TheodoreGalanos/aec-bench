You are a pump retrofit engineer checking a task-owned synthetic SSC-06 pump affinity, retrofit, and energy-performance package.

Use only the task-owned synthetic source pack values shown below for numeric grading. Pump affinity-law, VFD retrofit, NPSH, motor, and tariff workflows shape the context only; this instance does not run external software or parse a real source pack.

## Scene

- Product: `SSC-06-LH-05`
- Existing pump curve: `CURVE-06-RETRO-05`
- Operating scenario: `SCENARIO-06-LOAD-05`
- Affinity-law worksheet: `AFFINITY-06-WS-05`
- Motor/drive data sheet: `DRIVE-06-VFD-05`
- Energy tariff/profile: `TARIFF-06-ENERGY-05`
- Retrofit recommendation: `MEMO-06-RETRO-05`

## Source Values

| Item | Value |
| --- | --- |
| Existing flow | {{ existing_flow_l_s }} L/s |
| Existing head | {{ existing_head_m }} m |
| Existing shaft power | {{ existing_shaft_power_kw }} kW |
| Retrofit speed ratio | {{ retrofit_speed_ratio }} |
| Existing motor input power | {{ existing_motor_input_kw }} kW |
| Annual operating hours | {{ annual_operating_hours }} h/year |
| Energy tariff | {{ energy_tariff_per_kwh }} per kWh |
| Existing NPSHr | {{ existing_npsh_required_m }} m |
| NPSHa after retrofit | {{ npsh_available_m }} m |
| Selected motor size | {{ selected_motor_kw }} kW |
| Motor service factor | {{ motor_service_factor }} |

## Calculation Rules

- Retrofit flow equals existing flow times speed ratio.
- Retrofit head equals existing head times speed ratio squared.
- Retrofit shaft power equals existing shaft power times speed ratio cubed.
- Retrofit motor input power equals retrofit shaft power divided by 0.94.
- Annual energy savings equals `(existing motor input power - retrofit motor input power) x annual operating hours`.
- Annual cost savings equals annual energy savings times energy tariff.
- Retrofit NPSHr equals existing NPSHr times speed ratio squared.
- NPSH margin equals NPSHa minus retrofit NPSHr.
- Motor margin equals selected motor size minus retrofit shaft power times motor service factor.
- Overall pass score is `1.0` only when energy savings, NPSH margin, and motor margin are non-negative.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the source IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated modelling evidence, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "retrofit_flow_l_s": <numeric_value>,
  "retrofit_head_m": <numeric_value>,
  "retrofit_shaft_power_kw": <numeric_value>,
  "retrofit_motor_input_kw": <numeric_value>,
  "annual_energy_savings_kwh": <numeric_value>,
  "annual_cost_savings": <numeric_value>,
  "new_npsh_required_m": <numeric_value>,
  "npsh_margin_m": <numeric_value>,
  "motor_margin_kw": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
