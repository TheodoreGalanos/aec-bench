---
ara_schema_version: "0.1"
title: ASW-6A local evidence health
---

# ASW-6A local evidence health

## Approved rule freeze

Theo approved the complete provider-free ASW-6A rule set on 2026-08-01.
Version 3 adds explicit local evidence health while version 1 and version 2
histories remain byte-stable and replayable.

Evidence records separate observation, production, and availability time. The
actor view computes age and exposes quality, source, component scope, baseline,
operating regime, contradiction, supersession, and applicability. Evidence is
stale only when its age is greater than 28,800 seconds. Selected delayed
evidence remains unavailable for exactly 28,800 seconds.

The treatment version 1 catalogue contains only calibration lapse, evidence
delay, stale sample, contradictory report, observation loss, and baseline change.
Each activates at the next declared decision point. The actor sees only its
permitted effect. The host keeps treatment identity, hidden correct values,
unaffected controls, and future activation private.

The existing physical inspection remains available. A new condition check uses
only the visible sensor path and cannot authorize physical clearance.

## Result

The provider-free gate supports all five ASW-6A claims. The focused ASW-6A
suite passed 27 tests. The touched regression gate passed 35 tests. The
complete pump-station folder passed 192 tests. Ruff lint, Ruff format, source
MyPy, and ASW-6A test MyPy passed on the changed Python surface.

Version 3 now preserves evidence time, age, quality, source, scope, baseline,
regime, acceptance, contradiction, supersession, and applicability through
direct Python, installed JSON, structured handover, resume, replay, crash
recovery, and local Harbor. The direct and Harbor paths produce the same final
state for the fixed parity history. Exact control retries return the original
result without another transition.

No model call, external archive, temporal retrieval, maintenance closeout
review, branch fan-out, or physical treatment was authorized or used. The
result supports the synthetic task boundary only.

## Artifact map

- `logic/claims.yaml` records the falsifiable ASW-6A claims.
- `logic/experiments.yaml` records the completed provider-free gates.
- `logic/solution/architecture.md` records the version and control boundary.
- `evidence/index.yaml` links the approved decision and later command output.
- `trace/exploration_tree.yaml` records the approved rule decision.
- `staging/observations.yaml` retains later-stage questions and limits.
