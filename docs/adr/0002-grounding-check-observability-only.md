# Grounding check is observability-only; auto-gating is never the default

**Status**: accepted (2026-04-25)

The grounding check emits `grounding_report.json` as a sidecar artefact in v1 and never affects reward, output, or experiment outcomes. Promotion to a metrics signal (`grounding_pass_rate` in dashboards) is a v1.1 step after repeated report-generation runs validate the false-positive rate. Promotion to a hard gate is *only ever* an opt-in per-template policy via `[grounding.gate]`, never the default.

## Why this escalation, not auto-gating

Auto-gating couples adapter reward to detector fidelity — any detector regression looks like a quality regression, exactly the noise floor we just spent the F1-F8 batch trying to reduce. The detector will be wrong sometimes, especially early. Treating early flags as observability lets us iterate the detector without breaking experiments; treating them as gates means a noisy detector fails runs we care about. The escalation path is intentionally monotonic — observability becomes signal becomes opt-in gate, never the other way — because once downstream consumers (dashboards, alerts, remediation triggers) build on a stricter mode, walking it back is a coordination problem we shouldn't impose on ourselves.
