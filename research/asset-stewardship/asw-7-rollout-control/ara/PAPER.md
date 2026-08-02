---
ara_schema_version: "0.1"
title: ASW-7 state-addressable rollouts and governed physical treatments
---

# ASW-7 state-addressable rollouts and governed physical treatments

## Decision

Theo approved ASW-7A and ASW-7B as one end-to-end implementation on
2026-08-02. The implementation keeps lineage, origin selection, sibling
identities, treatment labels, treatment parameters, and future activation
private to the host. An actor receives only one child world and the normal
pump-station view and tools.

The implementation does not add a new world-state version. A child begins from
the complete selected parent state. A realised treatment is a durable
host-control transition in that child. The existing immutable commit chain and
independent verifier replay the effect from the private activation request.

## Result

The final provider-free affected-path gate passed 26 focused tests. It covers current-origin
validation, single-child and group creation, fixed-condition lineage, partial
group status, interrupted group recovery, parent and sibling isolation,
independent actor sessions, six closed physical treatment classes, delayed
clock activation, exact retry, negative public leakage, installed JSON, local
Harbor, and replay verification.

One additional native-tool regression proves that an agent-facing tool removes
the transport-only evidence-reliance field before proposal validation. Five
focused temporal-evidence tests passed after this repair. The four
rollout-control tests passed again after the final event-schedule digest profile
repair.

Theo approved one bounded four-turn Bedrock agent check. Amazon Bedrock rejected
the first provider call because the local AWS security token was invalid. The
attempt used 0 input tokens and 0 output tokens. No model inference occurred.
The child treatment, parent isolation, replay verification, and privacy scan
passed before and after the rejected call. This is provider failure evidence,
not a successful agent result.

## Artifact map

- `logic/claims.yaml` separates provider-free claims from the rejected provider
  claim.
- `logic/experiments.yaml` records the repeatable mechanism and agent checks.
- `evidence/requirement-trace.md` maps each ASW-7 requirement to code and tests.
- `evidence/contract-register.md` records task-local ownership and visibility.
- `evidence/provider-free-gate.md` records the focused command results.
- `evidence/bedrock-agent-attempt.md` records the failed provider route and token
  use.
- `trace/exploration_tree.yaml` records the design choice, implementation, and
  provider dead end.
