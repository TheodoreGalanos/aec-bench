You are an acoustic and vibration engineer checking a task-owned synthetic SSC-12 receiver-impact package for one night-time equipment operating case.

Use only the task-owned synthetic source pack values shown below for numeric grading. External FHWA TNM, FTA noise/vibration assessment, SoundPLAN, and CadnaA routes shape the workflow context only; they are not extra data sources for this instance.

## Scene

- Operating case: `OP-SSC12-NIGHT-001`
- Acoustic source: `SRC-SSC12-001`
- Equipment schedule row: `EQ-SSC12-BLOWER-01`
- Receiver: `RCV-12-NIGHT-01`
- Receiver criterion: `CRIT-12-NIGHT`
- Mitigation object: `MIT-12-BARRIER-01`
- Isolation mount: `ISO-12-MOUNT-01`
- Impact memo: `MEMO-12-ACOUSTIC-01`

## Acoustic Source And Receiver Path

| Item | Value |
|------|-------|
| 63 Hz source sound power | {{ source_lw_63_hz_db }} dB Lw |
| 125 Hz source sound power | {{ source_lw_125_hz_db }} dB Lw |
| 250 Hz source sound power | {{ source_lw_250_hz_db }} dB Lw |
| 500 Hz source sound power | {{ source_lw_500_hz_db }} dB Lw |
| 1000 Hz source sound power | {{ source_lw_1000_hz_db }} dB Lw |
| 2000 Hz source sound power | {{ source_lw_2000_hz_db }} dB Lw |
| 4000 Hz source sound power | {{ source_lw_4000_hz_db }} dB Lw |
| 8000 Hz source sound power | {{ source_lw_8000_hz_db }} dB Lw |
| Receiver distance | {{ receiver_distance_m }} m |
| MIT-12-BARRIER-01 insertion loss | {{ mitigation_insertion_loss_db }} dB |
| Existing background level | {{ background_sound_level_dba }} dBA |
| Night criterion | {{ night_noise_criterion_dba }} dBA |

Acoustic checks:

- Use octave bands 63, 125, 250, 500, 1000, 2000, 4000, and 8000 Hz.
- Distance attenuation equals `20 x log10(receiver_distance_m) + 11`.
- Receiver band level equals source sound power minus distance attenuation minus mitigation insertion loss.
- Apply A-weighting corrections of `[-26.2, -16.1, -8.6, -3.2, 0.0, 1.2, 1.0, -1.1]` dB to the receiver band levels.
- Receiver linear level and receiver A-weighted level are logarithmic sums of their band levels.
- Combined ambient level is the logarithmic sum of receiver A-weighted level and background level.
- Increase over background equals combined ambient level minus background level.
- Criterion margin equals night criterion minus combined ambient level.
- Dominant octave is the octave band with the highest A-weighted receiver band level.

## Vibration Isolation Path

| Item | Value |
|------|-------|
| Forcing frequency | {{ forcing_frequency_hz }} Hz |
| ISO-12-MOUNT-01 natural frequency | {{ isolator_natural_frequency_hz }} Hz |
| Damping ratio | {{ damping_ratio }} |
| Source vibration velocity | {{ source_vibration_velocity_mm_s }} mm/s |
| Structural path factor | {{ structural_path_factor }} |
| Receiver vibration criterion | {{ vibration_velocity_criterion_mm_s }} mm/s |

Vibration checks:

- Frequency ratio equals forcing frequency divided by isolator natural frequency.
- Damped transmissibility equals `sqrt(1 + (2 x damping_ratio x frequency_ratio)^2) / sqrt((1 - frequency_ratio^2)^2 + (2 x damping_ratio x frequency_ratio)^2)`.
- Receiver vibration velocity equals source vibration velocity times transmissibility times structural path factor.
- Vibration margin equals vibration criterion minus receiver vibration velocity.
- Overall pass score is `1.0` only when both the noise criterion margin and vibration margin are non-negative; otherwise it is `0.0`.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Explain the calculations briefly, preserve the object IDs above, and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "distance_attenuation_db": <numeric_value>,
  "receiver_linear_level_db": <numeric_value>,
  "receiver_a_weighted_level_dba": <numeric_value>,
  "combined_ambient_level_dba": <numeric_value>,
  "increase_over_background_db": <numeric_value>,
  "criterion_margin_db": <numeric_value>,
  "dominant_octave_hz": <numeric_value>,
  "frequency_ratio": <numeric_value>,
  "vibration_transmissibility": <numeric_value>,
  "receiver_vibration_velocity_mm_s": <numeric_value>,
  "vibration_margin_mm_s": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
