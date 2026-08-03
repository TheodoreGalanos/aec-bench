# ABOUTME: Records why ASW-8 moved continual worlds onto one registered runtime and transport path.
# ABOUTME: Preserves completed migration rationale without making the implementation sequence current authority.

# ASW-8 Runtime Consolidation

| Field | Value |
| --- | --- |
| Class | Historical |
| Status | Historical |

This document is non-normative. The current contract is the
[interactive-world runtime protocol](../protocols/interactive-world-runtime.md).

## Why this work existed

The ASW-8 pump-station reference system exposed a repository-wide boundary
problem. A persistent world needed task-owned transition semantics, durable
state and events, separate actor and host-control interfaces, branching,
rollouts, Harbor transport, and evaluation. Building each of those as
pump-specific infrastructure would have left the repository with two runtime
stacks and made the example impossible to reuse safely.

The original implementation therefore became a consolidation exercise: define
one registered continual-world boundary, preserve accepted pump artifacts, and
move transport and evaluation onto that boundary.

## Problems corrected during the branch

The initial branch and its review found several gaps:

- shared contracts existed before all execution paths used them;
- the pump opening state and staged publication needed stronger durability;
- file and directory writes used parallel low-level implementations;
- registered V4 worlds still passed through task-specific session and
  transition routes;
- rollout reading and orchestration duplicated package/runtime logic;
- CLI and Harbor transport could bypass the registered catalogue;
- evaluation did not yet consume bounded registered-world rollouts.

These were implementation gaps, not accepted permanent architecture.

## Corrective merge sequence

The corrective work was merged into the ASW-8 branch before pull request #74
reached `main`.

| Pull requests | Completed role |
| --- | --- |
| #75, #77 | Defined the continual-world boundary and registered contracts |
| #78-#82 | Consolidated locking, durable bytes, atomic replacement, directories, and staged publication |
| #83-#85 | Persisted opening state and routed registered V4 transitions and sessions through the shared run |
| #86-#87 | Added chosen-point rollout orchestration and removed parallel rollout/package readers |
| #89-#90 | Consolidated the canonical journey and routed CLI/Harbor transport through registered ports |
| #91 | Evaluated bounded continual-world rollouts through registered evaluation |

The aggregate landed on `main` in pull request #74. The branch history is the
provenance for the sequence; it is not a set of outstanding merge gates.

## Durable decisions

The migration left these decisions in the current system:

- world definitions are registered at composition boundaries;
- task code owns state, actor action semantics, events, projection, and verifier
  rules;
- the runtime owns generic persistence, sessions, branching, rollout
  orchestration, and ports;
- actor actions and host controls remain separate validated envelopes;
- optional capabilities are explicit ports, not assumed features of every
  world;
- the default catalogue has two real consumers: the pump-station world and the
  SSC-03 hydraulic-interaction world;
- CLI, Harbor, replay, and evaluation use the registered boundary rather than a
  second task-specific stack;
- accepted artifact bytes and replay behaviour are protected by tests while
  internal implementation remains replaceable.

## Current outcome

The consolidation is complete for the path described above. Future work should
start from the current protocol and live implementation. Reopening this history
is useful only when a change would introduce another durable repository, run
type, replay path, combined actor/control interface, or transport bridge.
