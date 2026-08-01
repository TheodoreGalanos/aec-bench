---
ara_schema_version: "0.1"
title: ASW-5 rich work processes
---

# Rich work-process rule freeze

ASW-5 adds one bounded, provider-free work-process scenario to the wastewater
pump-station world. It tests whether overlapping work can survive interruption,
resource competition, cancellation, durable replay, and agent handover without
duplicated work, hidden physical effects, or resource-conservation errors.

The scenario overlaps Pump A post-maintenance verification with Pump B
inspection and obstruction clearance. Access preparation and repair-kit
delivery are timed processes. The work shares one access window, one repair
kit, and one intervention slot. Access can be withdrawn while work is active.
A fresh agent must then safely resume, cancel, or reorder the live work.

## Frozen semantic boundary

- Dependencies use fixed AND lists. ASW-5 does not add a general expression
  language.
- Work can be `blocked`, `active`, `suspended`, `completed`, `failed`,
  `interrupted`, or `cancelled`.
- Access withdrawal automatically suspends access-dependent work. Follow-up
  due dates continue to move while work is suspended.
- Resume checks dependencies and resources again. It uses the remaining
  duration and does not repeat completed work.
- Cancellation releases unused resources. It does not remove operating limits
  or required follow-ups.
- Old completion events cannot affect cancelled or completed work.
- Access, the intervention slot, and the repair kit have explicit reservation
  rules. Access and the slot are released on suspension, cancellation, and
  completion. The kit stays assigned during suspension and is consumed only
  after successful obstruction clearance.
- Interrupted or suspended work has no partial physical effect.
- Physical, safety, evidence, and resource dependencies cannot be waived. Work
  Management can waive only an administrative closeout dependency, and only
  when the proposal names accepted evidence.
- A waiver cannot complete work, satisfy a follow-up, create a resource, or
  remove an operating limit.
- Access withdrawal creates a child `no_intervention` operating limit under
  the existing affected-pump limit. The child blocks resume until access
  returns. The parent remains active until its existing evidence rule is met.
- Agent views and handovers show the parent-child limit chain without exposing
  hidden world state.

## Durable compatibility boundary

ASW-5 creates version 2 state snapshots, transition receipts, approval-policy
records, and transition-rule records. Existing version 1 runs remain reloadable
and replayable. Continuing a version 1 run under version 2 creates a new,
content-addressed version 2 snapshot and a migration record with source
lineage. The version 1 bytes do not change. Unknown versions fail closed.

## Evidence programme

The implementation started with failing tests. Unit tests cover transitions,
dependencies, waiver rules, and resource accounting. Integration tests cover
version 1 reload, version 1 to version 2 migration, durable publication,
replay, views, and handover. End-to-end tests run the complete reference
scenario through the direct host and local Harbor paths. Attack tests cover
stale views, forged evidence, double reservation, invalid waiver, late
completion after cancellation, simultaneous events, crash recovery, and
hidden-state leakage.

No model-provider call, shared extraction, or later ASW stage is authorized by
this rule freeze.

## Result

The provider-free ASW-5 gate passed on 2026-08-01. Seventeen focused tests cover
the approved unit, integration, end-to-end, and attack paths. The complete
pump-station directory also passed with 163 tests. Strict MyPy passed for all
24 changed source files and the five changed test modules. Ruff passed for the
complete changed source and test boundary.

The installed Harbor reference-controller path, independent verifier,
TrialRecord import, strict reload, and evaluation also ran without a provider.
Replay and the Harbor verifier pass, but evaluation records one obligation
breach because the forced access interruption does not pause the verification
deadline. The imported TrialRecord therefore has reward `0.0` while retaining
the verifier's execution evidence. Direct and Harbor evaluation vectors are
identical, and the tenure handover omits no live process.

The repository-wide test run produced 7,601 passes, 21 existing skips, and 10
failures outside ASW-5. Eight failures reproduced at the unchanged
`origin/main` commit. One test depends on the checkout directory being named
`aec-bench`. One Azure reviewer test passed alone on both ASW-5 and the
baseline, which identifies a full-suite order dependency. These wider
repository defects remain visible but do not falsify the ASW-5 claims.

## Retained later steps

A human-grounded maintenance closeout and return-to-service review is retained
for conditional ASW-6A-R. The first review object is the named Pump A case pack:
condition and defect history, work order and scope, work and resource records,
inspection and intervention evidence, functional checks, provisional return and
closeout, post-maintenance verification, restrictions, obligations, handover
lineage, and the applicable FMECA and maintenance-schedule basis. A controlled
review issue belongs in a fallible record, claim, decision, or omission. It must
not corrupt authoritative world state. This review is not part of ASW-5 and has
no model-provider authority from this rule freeze.

State-addressable rollout fan-out is retained for conditional ASW-7A. It will
allow a later study to select one verified full-world state and create many
isolated agent continuations from it. The world can remain fixed to measure
agent variation, or a declared future-world change can form a separate
treatment. This capability is not part of ASW-5 and receives no provider
authority from this rule freeze.

## Artifact layers

- `logic/claims.yaml` records the claims that ASW-5 must test.
- `logic/experiments.yaml` records the provider-free test programme.
- `evidence/index.yaml` binds the approved rules and compatibility boundary.
- `evidence/current-test-status.md` records the final focused, cumulative, and baseline-comparison test evidence.
- `trace/exploration_tree.yaml` records the decision path.
- `staging/observations.yaml` keeps later research questions provisional.
