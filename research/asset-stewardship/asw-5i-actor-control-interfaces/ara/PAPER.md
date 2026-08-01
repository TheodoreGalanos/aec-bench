---
ara_schema_version: "0.1"
title: ASW-5I actor and world-control interfaces
---

# ASW-5I actor and world-control interfaces

## Decision

Theo accepted ASW-5I as the required interface gate before ASW-6A. The change
promotes only the task-neutral actor-call and host-control envelopes. The pump
station still owns its action names, fields, decision rules, projections,
physical effects, and verification.

## Implemented boundary

- The actor can discover task-owned actions, receive one permitted current
  view, and invoke one action against the exact branch, sequence, tenure, view,
  and information set.
- The actor request identity is the durable proposal identity. An exact live
  retry returns the same result without a second transition. Conflicting,
  stale, cross-scope, unknown, or unavailable calls fail closed.
- A separate host-only controller can discover, create, open, resume, inspect,
  snapshot, and verify a run. It rejects an unauthorised principal, raw state,
  and undeclared later-stage controls.
- The local actor surface can resume an existing run but cannot create one.
- Direct Python, the installed JSON interface, and the local Harbor controller
  use the same task-owned actor path.

## Evidence

The focused ASW-5I tests passed with 9 tests. The touched regression gate passed
with 17 tests. The complete pump-station folder passed with 165 tests. Ruff
lint, Ruff format, and MyPy passed on the changed Python surface. No model or
external provider call was made.

## Retained limits

ASW-5I adds no evidence-quality treatment, review case, temporal retrieval,
external archive, branch fan-out, physical treatment, shared world semantics,
or model-study authority. Those controls remain unavailable until their own
task stage supplies a real producer, consumer, and verifier.

The accepted ASW-5I gate activates the existing provider-free authority for
ASW-6A local evidence health only.

## Artifact map

- `logic/claims.yaml` records the supported interface claims.
- `logic/experiments.yaml` records the provider-free checks.
- `logic/solution/architecture.md` records the promoted boundary.
- `evidence/index.yaml` links exact test and quality outputs.
- `trace/exploration_tree.yaml` records the plan conflict, decision, and gate.
- `staging/observations.yaml` retains later-stage control limits.
