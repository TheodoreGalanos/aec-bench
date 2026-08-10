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

`InteractiveWorldDefinition` contains executable `WorldBuildRef` identity,
content-pinned profile references, and the task-owned profile loader.
`WorldBuildRef.artifact_sha256` identifies a stable manifest of exact source
bytes. It is not a general application ID.

`InteractiveWorldCatalogue` resolves a definition by world ID or exact build
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

The composition selects explicit skills in caller order while ambient skills,
extensions, prompt templates, themes, and context files remain disabled. Open
installs only `aec-world`. The optional Guided pump treatment installs
`aec-world` followed by `pump-station-guidance` and adds one instruction to load
the guidance before the first world action. The caller selects Guided
explicitly; task, world, profile, and model identities do not route it. The
optional Planned treatment installs `aec-world`, `aec-actor-ledger`, and the
selected Prime installation's `agent-message` and `agent-observe` skills. It
tells Prime to use bounded ledger results and bounded child-session previews.
All selected skills are copied under the isolated actor workspace before Prime
starts. Selected skill names, order, and content digests are normalized in
`prime-run.json` without retaining their host paths. Retained session evidence
separately shows whether Prime completed required skill reads.

The `pump-station-guidance` treatment asks Prime to combine each actor
invocation, ledger append, compact-state update, and selected output in one
notebook cell. Host-side emergency limits are not included in the guidance or
added instruction. The guidance does not select actions, add actor observations,
expose verifier state, or change world and evaluation rules. Its content digest
in `prime-run.json` identifies the exact guidance used by a retained run.

The `aec-actor-ledger` treatment keeps the exact current observation and action
records in the actor workspace. Its Python calls return only compact summaries.
`search()` returns bounded path matches, and `window()` returns a bounded part
of one actor-visible object or array. Prime's `agent-message` skill lets child
sessions return compact findings. `agent-observe` gives bounded, read-only child
message previews. These skills do not add world data or authority. The root and
all descendants remain one composite actor principal.

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

The pump reference-package reader supports two certified packages for different
reasons. Its no-argument route keeps the accepted `AU-NSW-LH-SYN-SPS-v1`
package and exact bytes available to existing readers. The registered pump
profiles explicitly load `AU-NSW-LH-SYN-SPS-v2`, which is the current
three-pump package used by the executable World. These routes are deliberate.
Removing the v1 package or changing the default route needs a separate audit of
external readers and retained evidence.

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

Prime HOME and XDG paths are trial-local under the actor workspace. A bounded
session has one Prime runtime. A pump journey uses the same actor workspace for
all actor-owned files, but gives every segment a fresh Prime runtime and ACP
connection. The normalized Prime evidence records configured safeguards,
aggregate usage and cost, root/child session counts, refinement status counts,
and any safeguard that ended the prompt. Unknown ACP metadata remains in the
raw ACP evidence.

Prime harness treatment is also explicit. `capture` preserves redacted raw
harness files and normalized evidence without carrying a change. `discover`
allows `/refine` and accepts prompt, memory, skill, and subagent entries with
local or global scope. A local entry ends with its Prime session. A portable
global entry can continue only inside the same AECBench journey. `candidate`
loads one content-bound candidate into every fresh session and fails if Prime
emits a new refinement event or changes the installed state. Unknown kinds,
malformed state, conflicting entries, host paths, redacted content, and invalid
skill references make a discovered candidate non-portable. Raw evidence stays
available for inspection.

Candidate loading is not command replay. The task-owned repository remains the
only command replay authority. Prime harness state is isolated from ambient
Prime state and from all other benchmark runs.

Journey safeguards cover the whole journey: session and host-control counts,
world actions, model calls, tokens, provider cost, and elapsed wall time. A new
Prime session receives only the remaining allowance. Completed response
accounting can cross a token or cost limit, but that journey stops before any
host control or later Prime session.

The bounded Prime composition still runs one actor continuation and invokes the
task-owned pump evaluator with `evaluation_scope="bounded_continuation"`.
Operations reviews remain outside the Prime actor capability.

The pump journey composition alternates bounded actor sessions with at most one
task-owned Operations review. Prime is closed before the host selects or applies
a control. The pump host policy reads the current canonical state, returns one
exact bound control or no control, and does not call evaluation. The existing
control implementation remains responsible for authority, accepted evidence,
stale-state, restriction matching, and exact-retry checks. After a changing
control, the next Prime segment opens with `RESUME` at the exact result snapshot.
All segments keep the same actor tenure and form one composite actor principal.
Only actor-owned workspace files and the next normal actor observation carry
information between segments; host state, control payloads, and verifier data do
not enter the actor workspace or continuation prompt.

Host continuation is permitted only after Prime returns a clean `end_turn`, no
Prime or host limit is reached, the actor-action limit remains open, and replay
is valid. Cancellation, `max_tokens`, `max_turn_requests`, provider failure,
protocol failure, incomplete session evidence, and an actor-action limit stop
the journey without a host action.

Before one selected host control, the coordinator atomically records its stable
request identity and parent snapshot in a private checkpoint. On explicit
resume, it reproduces the request from the unchanged parent or the canonical
committed command. The world repository then applies, recovers, or exactly
retries that request. The checkpoint records the canonical receipt and result
snapshot before another Prime session starts. It contains no control payload,
authority secret, host path, or hidden world state. A checkpoint that shows an
unclosed Prime session cannot resume automatically.

The task-owned pump status is separate from Prime session state and evaluation
validity. The journey uses `evaluation_scope="complete_journey"` only after the
pump status reports completion and canonical replay and verification pass. If
the world remains active and no deterministic host control is eligible, the
journey stops incomplete. It does not ask an LLM to choose a host control or
silently start another actor session. Private emergency safeguards can stop a
journey, but they cannot make it complete.

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

`prime-world-journey.json` records the policy digest, journey safeguards,
ordered session evidence, exact session-to-control-to-snapshot lineage, totals,
and final status. Per-session evidence remains separate. The private journey
checkpoint supports restart and does not replace the final manifest or world
repository.

`run_prime_refinement_qualification` creates independent empty-harness and
fixed-candidate journey cells. It uses RS1 and RS2 by default, with the same
instruction, model, isolation, guidance setting, and limits in both treatments.
Every cell has a new actor workspace, world repository, Prime runtime, and
evidence directory. The qualification report contains content-bound candidate,
journey, verification, evaluation, usage, and contrast evidence. Its decision
is `pending`. Qualification does not grant promotion authority and does not
change a task, skill package, world, verifier, or evaluator.

| Entry point | Behaviour |
| --- | --- |
| Python catalogue | Resolve current build and profile registration. |
| `actor-interface` | Invoke the pump episode host with current actor JSON. |
| `control-interface` | Invoke pump controls or explicit rollout composition. |
| Harbor agent and import | Use the concrete pump transport and evaluator. |
| Prime ACP Python entry | Run one Open, Guided, or Planned Prime session against one scoped pump actor proxy. |
| Prime pump journey Python entry | Compose bounded Prime sessions with exact task-owned host continuation until the pump world completes or cannot advance. |
| Prime refinement qualification Python entry | Compare one fixed candidate with an empty harness on independent RS1 and RS2 journeys without automatic promotion. |

The boundary fails closed for unknown build or profile identity, stale
decisions, unavailable actions, unauthorized controls, invalid rollout
identity, immutable-byte collisions, repository corruption, and incomplete
verification evidence. Transport and provider failures cannot manufacture a
successful transition or evaluation.

## Proof

- [catalogue registration](../../tests/worlds/test_catalogue.py)
- [episode state and recorder semantics](../../tests/worlds/runtime/test_episode.py)
- [world conformance](../../tests/worlds/test_pump_station_world_conformance.py)
- [separate-process actor resolution](../../tests/worlds/stewardship/wastewater_pump_station/test_actor_interface_transport_e2e.py)
- [pump retry and recovery](../../tests/worlds/stewardship/wastewater_pump_station/test_registered_world_run_transitions.py)
- [pump v1 and v2 certified reference-package routes](../../tests/worlds/stewardship/wastewater_pump_station/test_reference_system_package.py)
- [Prime actor proxy and pump session composition](../../tests/harness/pump_station_prime/test_session.py)
- [Prime pump journey composition](../../tests/harness/pump_station_prime/test_journey.py)
- [pump host continuation policy](../../tests/worlds/stewardship/wastewater_pump_station/test_host_continuation.py)
- [Prime ACP lifecycle and isolation](../../tests/prime_agent/test_acp.py)
- [Prime treatment and trajectory analysis](../../tests/experimentation/qualification/test_pump_station_prime_trajectory.py)
- [Prime refinement capture and qualification](../../tests/experimentation/qualification/test_prime_refinement.py)
- [Harbor import](../../tests/harness/test_stewardship_harbor_import.py)
