# ABOUTME: Indexes maintained repository design documents by authority, class, status, audience, and owner.
# ABOUTME: Separates current requirements from proposals, history, research, and public user documentation.

# Repository Documentation

| Field | Value |
| --- | --- |
| Class | Guide |
| Status | Current |

This directory contains repository-owned design documentation. Start here when
you need to find the current architecture, a protected boundary, a detailed
protocol, or the history behind an implemented decision.

## Authority order

Use this order when sources disagree:

1. The current task and its accepted behaviour.
2. Applicable [invariants](INVARIANTS.md) and explicit protected contracts.
3. Documented public behaviour and supported persisted or published formats.
4. Current architecture and protocol documents.
5. Current implementation and tests as evidence of existing behaviour.
6. Proposed plans, historical records, and research.

Code and tests are necessary evidence of what the repository does. They do not
silently override an explicit protected contract. A deliberate contract change
must update the implementation, tests, and owning document together.

## Document classes

| Class | Purpose | Contains | Does not contain |
| --- | --- | --- | --- |
| Normative | Stable requirement | What must remain true | PR sequence or implementation diary |
| Architecture | Current ownership and dependency direction | Present flows and clearly labelled target direction | Full package inventory |
| Protocol | Detailed behaviour at one boundary | Inputs, outputs, failures, persistence, and proof | Unrelated system policy |
| Guide | Current contributor or operator procedure | Steps and navigation that work now | Unimplemented APIs presented as current |
| Decision | Consequential choice and rationale | Context, decision, and consequences | General backlog |
| Plan | Proposed future change | Scope, sequence, and acceptance | Claims about current behaviour |
| Historical | Completed or superseded work | Durable explanation and provenance | Active requirements |
| Research | Evidence and hypotheses | Experiments, findings, and uncertainty | Product guarantees unless promoted deliberately |

Every maintained design document states its class and status near its title.
The statuses currently used here are `Current`, `Normative`, and `Historical`.
Use `Draft`, `Proposed`, or `Research` when adding material that is not current
authority.

## Maintained documents

| Document | Class | Status | Audience | Owner |
| --- | --- | --- | --- | --- |
| [Documentation index](README.md) | Guide | Current | Contributors and agents | Repository maintainers |
| [Architecture](ARCHITECTURE.md) | Architecture | Current | Contributors and integrators | Repository maintainers |
| [Contracts](CONTRACTS.md) | Normative | Current | Boundary owners and consumers | Owning domains |
| [Invariants](INVARIANTS.md) | Normative | Normative | All contributors | Benchmark governance |
| [Project structure](PROJECT_STRUCTURE.md) | Guide | Current | Contributors and agents | Repository maintainers |
| [World authoring](world-authoring.md) | Guide | Current | Task and interactive-world contributors | Task, engineering, world, and lifecycle owners |
| [Interactive-world runtime](protocols/interactive-world-runtime.md) | Protocol | Current | World, runtime, and transport contributors | World runtime and registered worlds |
| [Staged evidence and publication](protocols/staged-evidence-and-publication.md) | Protocol | Current | Lifecycle and evaluation contributors | Lifecycle runtime and task owners |
| [Environment category contract plan](plans/environment-category-contracts.md) | Plan | Historical | World, lifecycle, task, and runtime contributors | Repository maintainers |
| [Prime and interactive-world boundary study](plans/prime-world-boundary-study.md) | Plan | Historical | Prime, harness, and task-world contributors | Repository maintainers |
| [Repository architecture study](plans/repository-architecture-study.md) | Plan | Historical | Repository maintainers and subsystem owners | Repository maintainers |
| [Repository architecture alignment implementation](plans/repository-architecture-implementation.md) | Plan | Historical | Repository maintainers and subsystem owners | Repository maintainers |
| [Documentation agent guide](AGENTS.md) | Guide | Current | Coding agents editing this directory | Repository maintainers |

## Repository design docs and public docs

These files describe repository ownership, engineering guarantees, and
implementation boundaries. Public installation, CLI, integration, and user
guides are published at [aecbench.com/docs](https://aecbench.com/docs). The
root [README](../README.md) is the concise public entry point.

Do not copy public guides into this directory. Update the public documentation
source when user-facing behaviour changes, and update repository design docs
only when their owned boundary changes.

## Plans and PRDs

Proposed roadmaps and PRDs belong to the issue, pull request, or working
workspace that owns their delivery. A proposal may be tracked under
`docs/plans/` when the repository deliberately accepts it as a maintained plan;
that directory is not created for appearance. A tracked plan must be labelled
`Proposed` and is not current behaviour unless the active task explicitly
selects it.

When implementation completes, update the current architecture, contract, or
protocol and then either delete the plan or retain a concise record under
`docs/history/` when its rationale remains useful. Historical records are
non-normative. Do not keep a completed plan in the current authority path.

## Research promotion

Research records evidence, experiments, hypotheses, and uncertainty. Research
becomes a product requirement only through an explicit decision that updates
the owning invariant, contract, architecture, or protocol and adds the tests
that prove it. A link from current documentation to research is context, not
promotion.
