# ASW-6A rule-freeze decision

Theo approved the proposed ASW-6A values on 2026-08-01.

- Record generation: version 3, with version 1 and version 2 byte preservation.
- Stale threshold: age greater than 28,800 seconds.
- Delay duration: exactly 28,800 seconds.
- Quality states: current, suspect, unavailable.
- Treatment version: version 1.
- Treatment classes: calibration lapse, evidence delay, stale sample,
  contradictory report, observation loss, baseline change.
- Activation: next declared decision point, with no clock movement during
  scheduling.
- Inspection choice: existing physical inspection plus one visible-sensor
  condition check that cannot authorize physical clearance.
- Visibility: actor effect only; private treatment identity, hidden correct
  value, unaffected controls, and future activation.
- Gate: provider-free direct, installed JSON, handover, replay, resume, crash
  recovery, and local Harbor checks. No full repository test suite.
