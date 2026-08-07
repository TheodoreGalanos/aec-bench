# ABOUTME: Defines the current registered interactive-world runtime and supported entry points.
# ABOUTME: Separates task-owned semantics from episode, persistence, rollout, transport, and evaluation.

# Interactive-World Runtime

| Field | Value |
| --- | --- |
| Class | Protocol |
| Status | Current |

This protocol owns the registered interactive-world path. There is one current
actor shape and no historical runtime dispatcher.

## Registration and ownership

`ContinualWorldDefinition` contains executable `WorldBuildRef` identity,
content-pinned profile references, and the task-owned profile loader.
`WorldBuildRef.artifact_sha256` identifies a stable manifest of exact source
bytes. It is not a general application ID.

`ContinualWorldCatalogue` resolves a definition by world ID or exact build
reference. It does not register execution, evaluation, providers, Harbor, or
branch implementations. Those capabilities are composed by their owners.

| Owner | Owns |
| --- | --- |
| World kernel | Accepted transitions and action rejections |
| Episode shell | Live state, step, opaque decision, limits, terminal or truncated status, and recorder calls |
| Registered world | State, observations, actions, controls, clocks, and persistence meaning |
| Evaluation | Independent interpretation of verified evidence |
| Rollout coordinator | Ordered child publication through an explicit branch capability |
| Harbor integration | Pump-specific export, session transport, and result import |

## Episode composition

The episode shell receives private callables for observation, transition, and
available actions. It imports no concrete world, does not branch on
`world_id`, and does not evaluate during a transition.

An accepted transition advances state and step once, after recording succeeds.
A rejected action retains state, step, and decision. Domain termination and
host truncation are separate outcomes.

Task state never owns the episode step, opaque decision, request correlation,
repository location, or content digest. See the
[authoring guide](../world-authoring.md) for the minimum world boundary.

## Actor boundary

`ContinualWorldActorRequest` is the current unversioned installed request. It
is not content-addressed:

- `capabilities` and `observe` carry no action;
- `invoke` carries a request ID, opaque decision ID, task-owned action name,
  and strict arguments; and
- session, definition, profile, and actor-binding fields are not actor input.

| Actor-visible | Host-only |
| --- | --- |
| Action catalogue and input schemas | World build, profile, and full state |
| Opaque decision and public task view | Run, episode, branch, step, actor, and tenure identity |
| Request ID, action, and arguments | Repository lock, selected pointer, and persistence transaction |
| Receipt and next observation | Verifier-only and recovery data |

The pump actor command resolves the selected run from `--run-dir` on every
call. The repository lock and selected pointer support concurrent and
separate-process calls without a public binding or in-memory session
coordinator. A selected-state change makes the prior decision stale. Exact
retries require the same request identity and command content.

Prime interactive sessions use an additional host-owned, single-episode
transport around the same `PumpStationEpisodeHost`. A random capability and a
Unix-domain socket authorize one strict `ContinualWorldActorRequest`; the proxy
returns the existing actor result models. The remote request has no run,
episode, branch, profile, actor, tenure, evaluation, verification, rollout, or
host-control selector. The proxy owns the world repository path and closes with
the Prime ACP session. Stale-decision and exact-retry decisions therefore remain
inside the existing episode host.

The Prime root process and its descendants receive the same scoped capability,
so they form one composite actor principal. Per-child action attribution is not
claimed without enforceable per-child capability scoping.

The composed entry point requires positive host limits for world actions,
model calls, aggregate tokens, aggregate provider cost, and elapsed wall time.
The actor proxy counts distinct invoke request content while allowing an exact
retry of the same request without another allowance. A changed request under an
existing request ID is not an exact retry and still reaches the existing host
conflict semantics when an allowance remains.

AECBench reads every Prime session JSONL artifact for the composite principal.
It cancels the active ACP prompt when a completed assistant response reaches a
model-call, token, or cost limit. Provider usage is known only after a response,
so that final response can cross the token or cost threshold. A provider request
already in flight when the host cancels can also report usage. The wall limit
covers ACP startup and prompting. Malformed, incomplete, missing, or
unsupported session accounting fails closed.

## Host controls

The installed control command parses a strict discriminated union for:

- capability inspection and one task-owned root control;
- rollout creation and status inspection; and
- completed-group and child-run lookup.

Pump root controls and session operations remain task-owned. Actor calls cannot
carry either control family.

## Persistence and recovery

The pump stores one current unversioned run shape. Its manifest binds build,
profile, task, and run identity. Commands store the typed action and host-owned
decision binding once; replay derives the actor view from the parent state and
reapplies that action.

The recorder stages command, receipt, state, and commit, then publishes the
selected pointer last. A failed record or pointer publication cannot report a
successful action. Recovery completes the staged effect or leaves the prior
selected state authoritative.

The repository has no historical pump runtime selector, writer, migration, or
decoder. Static task-package readers verify their own current artifacts; they
do not require an older executable runtime.

## Optional capabilities

Branching and rollout exist only when the caller supplies a concrete branch
implementation. The rollout coordinator validates the origin, creates or
recovers isolated children, verifies them, and publishes ordered receipts and
lineage. It does not select providers, open actor sessions, apply task
treatments, or evaluate children.

Evidence lifecycles compose task-owned materializers, verifiers, optional
operation resolvers, and optional smoke environments directly. Unsupported
capabilities are absent rather than represented by placeholder ports.

Harbor uses the concrete pump integration. The neutral world definition has no
provider or Harbor port. Harbor import verifies durable pump evidence before
calling evaluation.

Prime ACP evidence and actor transport evidence are secondary execution
evidence. The pump repository remains canonical replay authority. The actor log
contains timestamps plus actor-visible requests, results, and errors. It also
records malformed, unauthorized, and transport-level attempts using only a
safe operation label. It excludes the capability secret, endpoint and
repository paths, arbitrary malformed payload content, and hidden state.

Prime HOME and XDG paths are trial-local under the actor workspace. The
normalized Prime run evidence records configured limits, aggregate usage and
cost, root/child session counts, refinement status counts, and any limit that
ended the prompt. Unknown ACP metadata remains in the raw ACP evidence.

Same-user Prime execution is development-only and cannot produce
benchmark-valid evidence. The current benchmark-valid local path uses a macOS
Seatbelt profile applied to Prime and its descendants. It denies the AECBench
repository and private world persistence while allowing the isolated actor
workspace, Prime installation, and scoped socket. Platforms without an
equivalent enforced boundary fail closed.

## Trial evidence and entry points

The pump repository and artifact inventory are replay authority.
`TrialRecord.episode_artifact` references that verified inventory without
copying episode state into a second execution projection. `OutputRecord` owns
completion and failure facts; `CostRecord` owns aggregate usage and estimated
cost. Public reports select fields from these authorities rather than exposing
state, verifier paths, provider configuration, or recovery data.

| Entry point | Behaviour |
| --- | --- |
| Python catalogue | Resolve current build and profile registration. |
| `actor-interface` | Invoke the pump episode host with current actor JSON. |
| `control-interface` | Invoke pump controls or explicit rollout composition. |
| Harbor agent and import | Use the concrete pump transport and evaluator. |
| Prime ACP Python entry | Run one Open-mode Prime session against one scoped pump actor proxy. |

The boundary fails closed for unknown build or profile identity, stale
decisions, unavailable actions, unauthorized controls, invalid rollout
identity, immutable-byte collisions, repository corruption, and incomplete
verification evidence. Transport and provider failures cannot manufacture a
successful transition or evaluation.

## Proof

- [catalogue registration](../../tests/task_world_templates/continual/test_catalogue.py)
- [episode state and recorder semantics](../../tests/task_world_templates/continual/test_episode.py)
- [world conformance](../../tests/task_world_templates/continual/test_hydraulic_world_conformance.py)
- [separate-process actor resolution](../../tests/task_world_templates/stewardship/wastewater_pump_station/test_actor_interface_transport_e2e.py)
- [pump retry and recovery](../../tests/task_world_templates/stewardship/wastewater_pump_station/test_registered_world_run_transitions.py)
- [Prime actor proxy and world composition](../../tests/prime_agent/test_world.py)
- [Prime ACP lifecycle and isolation](../../tests/prime_agent/test_acp.py)
- [Harbor import](../../tests/harness/test_stewardship_harbor_import.py)
