You are checking a task-owned synthetic SSC-12 vibration isolation and support package.

Use only the source pack values below for numeric grading. External FTA vibration assessment, manufacturer isolator, and structural support workflows provide context only; they are not extra data sources for this instance.

## Scene

- Product: `SSC-12-LH-02`
- Equipment data sheet: `EQ-12-VIB-02`
- Support layout: `SUPPORT-12-LAYOUT-02`
- Isolator data: `ISO-12-DATA-02`
- Foundation/support schedule: `FOUND-12-SCHED-02`
- Vibration criterion: `CRIT-12-VIB-02`
- Isolation memo: `MEMO-12-ISO-02`

## Source Pack Values

| Item | Value |
|------|-------|
| Equipment mass | {{ equipment_mass_kg }} kg |
| Dynamic allowance factor | {{ dynamic_allowance_factor }} |
| Support count | {{ support_count }} |
| Support capacity | {{ support_capacity_kn }} kN |
| Forcing frequency | {{ forcing_frequency_hz }} Hz |
| Isolator natural frequency | {{ isolator_natural_frequency_hz }} Hz |
| Damping ratio | {{ damping_ratio }} |
| Source vibration velocity | {{ source_vibration_velocity_mm_s }} mm/s |
| Structural path factor | {{ structural_path_factor }} |
| Vibration velocity criterion | {{ vibration_velocity_criterion_mm_s }} mm/s |
| Cycles per hour | {{ cycles_per_hour }} |
| Operating hours per day | {{ operating_hours_per_day }} h |
| Design life | {{ design_life_days }} d |
| Allowable fatigue cycles | {{ allowable_fatigue_cycles }} |

Calculate the frequency ratio, damped transmissibility, receiver vibration velocity, vibration margin, support service reaction, support reaction margin, fatigue damage ratio, fatigue margin, and pass score.

Write `/workspace/output.md` with a compact memo preserving the object IDs above. Include a source-boundary statement that this is a task-owned synthetic source pack.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "frequency_ratio": <numeric_value>,
  "vibration_transmissibility": <numeric_value>,
  "receiver_vibration_velocity_mm_s": <numeric_value>,
  "vibration_margin_mm_s": <numeric_value>,
  "support_service_reaction_kn": <numeric_value>,
  "support_reaction_margin_kn": <numeric_value>,
  "fatigue_damage_ratio": <numeric_value>,
  "fatigue_margin": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
