# ABOUTME: Defines the current registered interactive-world runtime boundary and supported entry points.
# ABOUTME: Separates task-owned world semantics from shared dispatch, durability, rollout, transport, and evaluation routing.

# Interactive-World Runtime

| Field | Value |
| --- | --- |
| Class | Protocol |
| Status | Current |

This protocol describes the implemented continual-world boundary at the current
repository revision. It is the authority for registered interactive-world
routing. The [ASW-8 consolidation record](../history/asw8-runtime-consolidation.md)
explains how the current path replaced its parallel predecessors.

## Scope

The protocol applies when an agent repeatedly observes task-owned state and
takes actions that change a world. It covers registration, exact profile
resolution, actor and host-control calls, session bindings, optional rollout
groups, local durability primitives, Harbor routing, and registered evaluation.

It does not make snapshots, branching, rollout groups, Harbor, cloud execution,
or durable sessions mandatory for every interactive world.

## Registered definitions and profiles

`ContinualWorldDefinition` joins content-pinned identity to task-owned ports. A
definition declares one or more immutable profile references and can register
only the capabilities it supports:

- profile loading;
- actor and host-control execution;
- branch materialization;
- Harbor session execution; and
- evaluation.

`ContinualWorldCatalogue` rejects duplicate world IDs and duplicate Harbor
execution kinds. New work resolves the current definition by world ID. Recovery
resolves the exact definition version and content hash recorded by the run.
Profile loading requires an exact world ID, profile ID, profile version, and
profile content hash.

The default composition catalogue registers two real consumers:

- the wastewater pump-station stewardship world, including execution, branch,
  Harbor, and evaluation ports; and
- the SSC-03 hydraulic interaction world, including its real lifecycle
  profiles and branch port.

Concrete imports exist in the composition root. The task-neutral package under
`src/aec_bench/task_world_templates/continual/` imports neither world.

## Ownership boundary

| Owner | Owns | Does not own |
| --- | --- | --- |
| Shared contracts | Definition/profile references, actor/control envelopes, snapshot references, and rollout records | Task fields, action names, verifier targets, or provider credentials |
| World kernel | Accepted-transition and action-rejection values | Task actions, state, observation, evaluation, persistence, limits, or provider transport |
| Continual runtime | Catalogue resolution, common envelope validation, actor dispatch, host-authority checks, optional rollout coordination, and shared local durability surfaces | Pump or hydraulic transition semantics |
| Registered execution port | Opening or resuming the task's canonical actor session and invoking task-owned controls | Generic provider selection or evaluation policy |
| Task world | State, clocks, observations, actions, controls, events, projections, transition rules, task persistence meaning, and verification | Main-agent dispatch or generic rollout storage |
| Profile | One content-pinned starting situation and its task-owned data | Alternate runtime or persistence rules |
| Harbor port | Task-neutral bridge identity plus task-owned session translation | Provider secrets in serialized task configuration |
| Evaluation port | Task-owned interpretation of one verified run | Trial persistence or report rendering |

Task state remains opaque at the shared boundary. The runtime can validate and
route an opaque task payload without interpreting its fields.

## Functional world kernel

`src/aec_bench/task_world_templates/continual/world_logic.py` defines the
smallest shared in-process behavior:

- `Transition` returns the accepted next state and any world-defined terminal
  output, plus an optional terminal reason; and
- `ActionRejected` reports an invalid action without returning a replacement
  state.

These are internal Python values and structural protocols, not persisted
schemas or a public plugin API. They contain no session, filesystem, ledger,
snapshot, rollout, provider, model, cost, or training fields.

The two real consumers did not fit one structural protocol without artificial
adapters, so initial state, observation, transition functions, codecs, and
evaluation remain concrete task-owned functions. The reusable conformance
helper accepts those functions directly. Evaluation stays separate from
transition and persistence.

Two real task-owned behaviors currently establish the shared shape:

- SSC-03 executes one deterministic hydraulic scenario through the kernel,
  exposes a bounded progress observation, terminates after the scenario, and
  selects the canonical hydraulic result through a separate evaluator. The
  existing lifecycle operation and package execution paths call this behavior.
- The pump station advances one coupled physical operating interval through
  the shared result values. Its existing actor projection exposes pump clocks,
  availability, assignment, and running sets without latent pump condition.
  The registered actor path reaches this behavior when `continue_operation`
  advances physical time.

The pump transition receipt, durable commit, information-set binding, and
complete actor view remain outside the kernel because they belong to task
orchestration, recording, and the richer task projection. SSC-03 still uses its
evidence-lifecycle and rollout adapter rather than claiming a pump-style actor
session.

## Actor authority

`ContinualWorldActorRequest` supports `capabilities`, `observe`, and `invoke`.
It resumes an existing session and binds an action to the exact definition,
profile, run, episode, branch, tenure, sequence, state, and commit selected by
the session.

Actor observations bind the public view and information set to that same world
position. An action is available only when it appears in the task-owned actor
capability catalogue. The result binds the exact request, preserves its
pre-state, and returns a validated next observation.

Actors never receive host controls through this envelope.

## Host-control authority

`ContinualWorldControlRequest` is a separate envelope. Every call carries a
host authority ID that must be in the execution context's authorized principal
set. The nested task control must name the same world and authority as the outer
request.

The current shared operations are:

- inspect host-control capabilities;
- execute one task-owned control;
- create a rollout group;
- inspect rollout-group status;
- inspect a completed rollout group; and
- resolve one child-run reference.

Task controls cannot request raw state mutation. Their closed operation set,
arguments, effects, and receipts remain task-owned.

## Sessions and persistence

The shared session contracts validate execution kind, open mode, session,
tenure, run, episode, branch, and snapshot identity. The registered execution
port opens the task's canonical session implementation. This preserves one
task-owned run and repository rather than creating a generic duplicate beside
it.

For the registered pump world:

- one selected run pointer names the current immutable commit;
- actor observations can advance session-visible information without creating
  a world transition;
- actor and control transitions publish task-owned commands, receipts, state,
  and commits through the existing pump repository;
- physical time advancement calls the task-owned world kernel before the
  resulting domain receipt is staged;
- an exact retry returns the stored effect when its complete identity matches;
  and
- replay reloads durable inputs and uses the manifest-bound task model.

The shared durability module exposes proven host-local primitives for confined
locking, immutable bytes, durable file replacement, and durable directory
creation. Callers retain the policy for what a pointer, transaction, commit, or
record means. These primitives assume a cooperative local POSIX filesystem;
they are not distributed locking or object-store transactions.

## Optional branches and rollout groups

A definition supports chosen-point branching only when it registers a branch
port. The shared rollout coordinator then:

1. validates one exact group request and parent snapshot;
2. asks the task port to verify the origin;
3. publishes ordered child requests under a confined host-private root;
4. materializes or exactly recovers each isolated child;
5. asks the task port to verify each child;
6. publishes immutable child receipts and ordered lineage; and
7. exposes a child-run reference only after the complete group is ready.

The coordinator does not open an actor session, choose a model, apply a task
treatment, or inspect task state. Parent, child, and sibling runs remain
isolated. Reusing an identity with different content is a conflict.

## Evaluation registration

A definition can register an evaluation port independently of its execution
and branch ports. The pump-station Harbor importer resolves the content-pinned
definition and profile, then calls the registered evaluator for either a
`complete_journey` or `bounded_continuation`. The evaluator recomputes
task-owned results from durable run evidence and imported artifact hashes.

Evaluation remains separate from transition execution. A world action cannot
assign its own benchmark reward.

## Supported entry points

| Entry point | Current behavior |
| --- | --- |
| Python catalogue | `default_continual_world_catalogue()` resolves registered definitions and Harbor ports. |
| Python actor/control dispatch | `dispatch_continual_actor()` and `dispatch_continual_control()` validate the common envelopes and route to registered owners. |
| Installed JSON | `aec-bench task pump-station-world actor-interface` and `control-interface` execute registered pump-world requests. |
| Legacy installed JSON | `aec-bench task pump-station-world interface` remains the supported V1-V3 pump boundary and rejects registered V4 runs. It is not a second V4 runtime. |
| Harbor agent | The main agent resolves a unique execution kind through the catalogue and delegates to the registered Harbor port. |
| Harbor import | Pump-world import resolves the registered evaluation port and builds canonical trial evidence. |

SSC-03 uses the shared definition/profile and rollout contracts through its
evidence-lifecycle implementation. It does not claim every optional pump-world
entry point.

## Failure semantics

The boundary fails closed when:

- a definition or profile is unknown, stale, or content-mismatched;
- an actor request does not match the resumed session and snapshot;
- an action is absent from the task-owned capability catalogue;
- a host authority or nested control identity differs;
- a requested optional port or rollout repository is absent;
- a rollout origin, child, receipt, lineage, or confined path fails validation;
- immutable publication collides with different bytes; or
- registered evaluation authority is incomplete.

Task errors retain their task-owned error boundary. Transport and provider
failures remain failures; dispatch does not manufacture a successful world
transition or evaluation.

At the in-process behavior boundary, a rejected action does not return a new
state. A valid transition can terminate a world. Runtime limits and external
interruptions are not world termination.

## Proof

The following focused tests define the current boundary:

- [catalogue and two-consumer registration](../../tests/task_world_templates/continual/test_catalogue.py)
- [catalogue-driven actor, control, installed JSON, and rollout dispatch](../../tests/task_world_templates/continual/test_catalogue_driven_interface.py)
- [shared durability behavior](../../tests/task_world_templates/continual/test_durability.py)
- [rollout record contracts](../../tests/task_world_templates/continual/test_rollout_contract.py)
- [SSC-03 rollout use](../../tests/task_world_templates/continual/test_ssc03_rollout_control.py)
- [SSC-03 world-kernel conformance](../../tests/task_world_templates/continual/test_hydraulic_world_conformance.py)
- [pump physical world-kernel conformance](../../tests/task_world_templates/continual/test_pump_station_world_conformance.py)
- [registered pump session interfaces](../../tests/task_world_templates/stewardship/wastewater_pump_station/test_registered_world_session_interfaces.py)
- [registered Harbor routing](../../tests/task_world_templates/stewardship/wastewater_pump_station/test_registered_world_harbor.py)
- [registered rollout orchestration](../../tests/task_world_templates/stewardship/wastewater_pump_station/test_registered_rollout_orchestration.py)
- [replay and evaluation integration](../../tests/task_world_templates/stewardship/wastewater_pump_station/test_world_run_replay_evaluation_e2e.py)
