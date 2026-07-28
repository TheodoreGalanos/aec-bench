---
ara_schema_version: "0.1"
title: Wastewater pump-station stewardship research charter
---

# Research continuation summary

This artifact records how a programme-decision memo was converted into the
first wastewater pump-station stewardship charter.

The key correction is that the certified secondary physical mechanism remains
hydraulic clearance loss. The first study may omit clearance repair from its
public action catalogue without removing that mechanism from the physical world.

The charter uses amendable semantic revisions during development. It does not
make hand-written hashes a design requirement. Outcome-bearing study runs must
still record the realised revisions needed to prevent mixed-version analysis.

ASW-2A2 TDD exposed one schedule conflict. Revision `ASW-0C-2` moves inspection
before the repair access window because starting the `D`-long inspection at
`L` would make completion simultaneous with breach, which has higher event
priority.

ASW-2A3 implements actor-visible current state, bounded structured handover,
exact information-set binding, and pure verifier replay. Episode time and
actor-tenure time are separate. A handover starts a fresh tenure without
resetting the continuing station. Actor-visible identities use only permitted
projection content, so a hidden future-schedule change cannot become an
identity side channel.

ASW-2B adds a task-local durable world run under a host-supplied filesystem
root. Complete state, proposals, information sets, receipts, applied event
batches, and commit links are immutable. One lock-serialised atomic pointer
selects the current state. Snapshot and resume retain simulated duration and
all current stewardship duties. Retrying the same proposal across the selected
crash windows cannot duplicate a resource record or physical duty transfer.

This implementation computes content identities from realised artifacts. It
does not add hashes to the task policy or make the development environment
immutable.

Layers:

- `logic/claims.yaml` records the supported design claims.
- `trace/exploration_tree.yaml` records the decisions and corrected dead end.
- `evidence/index.yaml` points to the source notes.
- `staging/observations.yaml` retains the later provider-budget question.
