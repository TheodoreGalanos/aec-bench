# Prime and Interactive-World Boundary Study

| Field | Value |
| --- | --- |
| Class | Plan |
| Status | Historical |

This file records the source layout before the repository architecture
cutover. Use [Architecture](../ARCHITECTURE.md) for the current owners and
[the implementation plan](repository-architecture-implementation.md) for the
accepted migration.

## Purpose

This plan saves the current architecture analysis before AEC-Bench selects a
second interactive-world task for Prime Agent.

It records current implementation facts and the study needed to identify a
real shared Prime-world boundary. It does not approve a package move or a new
generic world framework.

The source audit used the current working tree based on commit
`f771467b7ed7a964e6e249d23fae8700cae2f7a8`. The working tree also contained
uncommitted Prime-refinement and pump-profile work.

## Tasks and task worlds

A task defines the work:

- objective;
- actor-visible inputs;
- allowed tools;
- required output;
- completion rules; and
- verification.

A task world defines the environment:

- causal state;
- actor observations;
- available actions;
- state transitions;
- time and external events;
- host-only controls; and
- replay and verification meaning.

The high-level distinction is:

```text
task
    What must the agent achieve?

task world
    What environment does the agent act inside?
```

An artifact task normally stages one workspace and checks the final
submission. An interactive task repeatedly observes and changes world state.
The objective and the world remain separate so one world can support different
objectives and profiles where the task design requires it.

The current execution-family distinction is defined in
[Architecture](../ARCHITECTURE.md#product-flow), and the current authoring
boundary is defined in [World authoring](../world-authoring.md#minimum-interactive-world).

## Current `task_world_templates` map

The top-level package is a mixed ownership area. Its current subpackages do not
represent four versions of one abstraction.

| Area | Current responsibility | Time structure |
| --- | --- | --- |
| `continual` | Task-neutral episode, registration, rollout, and durability support | Repeated decisions |
| `hydraulics` | Deterministic hydraulic source, calculation, package, and verifier behavior | One bounded calculation run |
| `lifecycles` | Finite evidence workflows with releases, operations, submissions, and checkpoints | Ordered checkpoints |
| `stewardship` | Persistent operational task worlds; currently the wastewater pump station | Long-running causal state |

### `continual`

`task_world_templates/continual` was shared
runtime code, not a task template. It owns the live episode shell, decision
freshness, limits, accepted-transition and rejection values, exact build and
profile registration, and optional rollout support.

It does not own concrete pump or hydraulic state, actions, observations,
controls, or evaluation.

### `hydraulics`

`task_world_templates/hydraulics` was a
deterministic domain engine. It owns hydraulic source data, bounded calculation
requests, results, source revisions, interventions, package identity, reports,
and verification.

It can run without a model, Prime, or an evidence lifecycle. Lifecycle tasks
can use it as a task-owned calculation capability.

### `lifecycles`

`task_world_templates/lifecycles` contained
finite evidence tasks. The current SSC-03 hydraulic interaction flow releases
information and accepts submissions at three ordered checkpoints:

```text
baseline analysis
    -> revision analysis
    -> closeout review
```

These tasks can call the hydraulic engine through bounded operations. They end
after their declared checkpoint sequence. They are not persistent asset
simulations.

The current lifecycle implementation is physically split between
`task_world_templates/lifecycles` and evidence-lifecycle code in
`meta_harness`. This is a review point for later organisation work.

### `stewardship`

[`stewardship`](../../src/aec_bench/worlds/stewardship/) contains
the persistent wastewater pump-station world. It owns pump condition, service,
operating exposure, resources, backlog, evidence, restrictions, obligations,
actor actions, host controls, durable state, replay, verification, evaluation,
and the RS1 and RS2 profiles.

It uses the shared `continual` episode shell, but its engineering meaning stays
inside the pump task package.

## Current execution relationships

```text
SSC-03

hydraulics
    -> lifecycle task
    -> evidence-lifecycle coordination
    -> continual build and profile registration
```

```text
Wastewater pump station

stewardship task world
    -> continual episode and registration
    -> concrete Harbor or Prime composition
```

Both definitions are in the continual-world catalogue. They do not yet use the
same actor host, Prime session lifecycle, host continuation, or completion
rules. Catalogue registration alone does not prove a generic Prime journey.

## Prime ownership finding

`adapters/prime_agent.py` is the artifact-task adapter. The broader
`prime_agent` package owns the upstream process and protocol integration.

The generic `prime_agent` package owns Prime process, protocol, isolation,
generic skill, and session-evidence behavior. The concrete pump composition is
now under:

```text
harness/pump_station_prime/
    session.py
    journey.py
    evidence.py
```

The pump task does not import this harness package. Read-only pump treatment
analysis is under `experimentation/qualification`. This ownership move does not
create a general Prime-world journey framework.

## Why a second Prime task comes first

The next task must show which parts of the current pump integration repeat
without adding speculative ports.

The study will test whether both tasks genuinely share:

- one scoped actor transport;
- one Prime ACP session lifecycle;
- one session-to-world completion distinction;
- one limit and accounting policy;
- one continuation and recovery shape; and
- one safe evidence aggregation pattern.

Task-owned action meaning, host-control selection, completion rules,
verification, and evaluation stay outside any shared Prime-world runtime.

## Second-task work plan

1. Select the second Prime task and state why it tests the required boundary.
2. Map its objective, state, actor operations, host-only authority, completion,
   verification, and evaluation.
3. Reuse current contracts only where their meaning matches without task-type
   branches.
4. Implement the smallest benchmark-valid Prime session for the task.
5. Run one focused smoke test and retain Prime and world evidence separately.
6. Compare the second integration with the pump session and journey modules.
7. Classify each repeated part as Prime protocol, shared orchestration,
   task-owned behavior, or accidental similarity.
8. Propose extraction only for behavior with the same owner and semantics in
   both tasks.

## Open questions

1. Which existing or new world is the best second Prime task?
2. Must it cross a host-control boundary, or is one bounded interactive session
   enough for the first comparison?
3. Can it use the current actor request and result boundary unchanged?
4. Which current pump modules are genuinely shared after the second task runs?
5. Should `continual` remain under `task_world_templates`?
6. Should the evidence-lifecycle runtime remain in `meta_harness`?

## Current decision boundary

Do not create a general `dynamic_world`, `prime_world`, or world-journey
framework from the pump implementation alone.

First select and run a second Prime task. Then compare the two concrete paths.
Extract only code that has the same owner and behavior in both paths.
