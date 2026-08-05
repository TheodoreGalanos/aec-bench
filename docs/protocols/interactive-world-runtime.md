# ABOUTME: Defines the current registered interactive-world runtime boundary and supported entry points.
# ABOUTME: Separates task-owned semantics from the episode shell, optional rollout, transport, and evaluation.

# Interactive-World Runtime

| Field | Value |
| --- | --- |
| Class | Protocol |
| Status | Current |

This protocol is the authority for the current registered interactive-world
path. There is one live actor shape, one pump runtime, and no historical
runtime dispatcher.

## Registration and identity

`ContinualWorldDefinition` contains only:

- a `WorldBuildRef` for the exact executable source artifacts;
- the current content-pinned profile references; and
- the task-owned profile loader.

`WorldBuildRef.artifact_sha256` hashes a stable manifest of exact Python source
file bytes. It is executable-artifact identity, not a hash of callable source
text and not a general application ID. A profile hash identifies the exact
task-owned data selected for an episode.

`ContinualWorldCatalogue` resolves a current definition by world ID or by its
exact build reference. It does not register execution, evaluation, provider,
Harbor, or branch ports. Those capabilities are composed by their owners at
the call site. The task-neutral continual package imports no concrete world.

The current catalogue has two real consumers: the wastewater pump-station
world and the SSC-03 hydraulic interaction world.

## Ownership

| Owner | Owns | Does not own |
| --- | --- | --- |
| Shared contracts | Current build/profile references, actor call, installed control union, snapshot reference, and rollout records | Task actions, state, provider settings, or evaluation |
| World kernel | Accepted transition and action rejection values | Sessions, persistence, limits, or scoring |
| Episode shell | Live state, step, opaque decision, limits, terminal/truncated status, and recorder calls | World semantics, provider behavior, persistence layout, or evaluation meaning |
| Registered task world | State, observations, actions, controls, clocks, persistence meaning, and verification | Generic provider selection |
| Rollout coordinator | Ordered durable rollout publication through an explicitly supplied branch capability | Actor sessions, task treatments, models, or evaluation |
| Harbor integration | Pump-specific task export and session transport | Neutral world registration |
| Evaluation | Independent interpretation of verified run evidence | Live transition behavior |

## World behavior and episode composition

`world_logic.py` defines the small in-process `Transition` and
`ActionRejected` values. State, observation, action, terminal output, codecs,
and evaluation remain task-owned.

The episode shell receives private task callables for observation, transition,
and available actions. It imports no concrete world, does not branch on
`world_id`, and never calls evaluation during a transition. The hydraulic and
pump worlds use the same result values without being forced into a public
universal world protocol.

The shell is the sole owner of live state and step advancement during a call.
An accepted transition advances once after the recorder succeeds. A rejected
action retains state, step, and decision. World termination and host
truncation remain distinct.

The pump world binds one task-owned functional core to that shell:

- `initial_state()` constructs the certified canonical
  `PumpStationStewardshipState`;
- `observe()` derives the actor view from that state and explicit host step;
- `transition()` consumes one of the 12 typed pump actions; and
- `evaluate()` consumes canonical terminal state plus explicit verified step
  evidence, outside the live transition.

Pump state owns physical condition, clocks, assignment, work, resources,
evidence, restrictions, and obligations. It does not own the episode step,
opaque decision, request correlation, repository location, or content digest.

## Actor boundary

`ContinualWorldActorRequest` is the one current unversioned installed actor
shape. It is not content-addressed:

- `capabilities` and `observe` carry no action payload;
- `invoke` carries `request_id`, opaque `decision_id`, task-owned
  `action_name`, and strict `arguments`; and
- obsolete version, session, definition, profile, and actor-binding fields fail
  current validation.

| Actor-visible | Host-only |
| --- | --- |
| Action catalogue and input schemas | World build and profile |
| Opaque decision ID and public task view | Run, episode, branch, state, commit, step, actor, and tenure identity |
| Request ID, action name, and arguments | Repository path, lock, selected pointer, and information-set binding |
| Task receipt and next observation | Full task state and persistence transaction |

The pump actor command reopens the selected run from `--run-dir` for every
call. The repository lock and selected pointer resolve concurrent and
separate-process calls; no public binding or in-memory session coordinator is
required. The host derives the decision ID from the selected build, profile,
run, episode, branch, actor, step, and state. A changed selected state makes a
prior decision stale.

Exact retries are keyed by request identity and complete command content.
Changed content under the same request ID is rejected.

## Host controls

The installed control command parses a strict discriminated union. Its current
operations are:

- inspect task-owned control capabilities;
- execute one task-owned control;
- create a rollout group;
- inspect rollout-group status;
- inspect a completed rollout group; and
- resolve a child-run reference.

The current pump root controls are `operations_review`, `process_outcome`,
`common_boundary`, and `coupled_treatment`. They remain task-owned ordinary
Python values. Session host operations are `create_session`, `open_session`,
`resume_session`, `inspect_progress`, `snapshot`, and `verify`. Actor calls
cannot carry either control family.

## Persistence and recorder boundary

The pump run stores one current unversioned shape. The manifest records the
selected build entry point and executable-artifact digest, the current profile
identity, and the task/run identities needed for replay. Commands, receipts,
states, commits, and pointers use current strict dataclasses and the
current-only codec.

An actor command stores the typed pump action and its host-owned decision
binding once. It does not store a second proposal, argument JSON copy, or
duplicate information-set artifact. Replay derives the expected actor view
from the parent state and re-applies the typed action directly.

The recorder stages command, receipt, state, and commit, then publishes the
selected pointer last. If recording or pointer publication fails, the call
does not report a successful action. Recovery completes the same staged effect
or leaves the prior selected state authoritative.

No released, published, or supported run artifact requires an older pump
world-run format. The repository therefore has no V1-V4 selector, migration,
historical digest profile, compatibility alias, or historical decoder.

The exact static package artifacts retained by the repository are:

- `reference_package/`;
- `reference_packages/au-nsw-lh-syn-sps-v2/`; and
- `reference_system/asw-8-rs1/`.

Their existing descriptors and byte-integrity checks remain at their task
package readers. They do not require an old executable world runtime.

## Optional capabilities

Branching and rollout are absent unless a caller supplies a concrete branch
capability. `PumpStationContinualWorldBranchPort` and
`Ssc03HydraulicContinualBranchPort` are the two current implementations of the
narrow structural boundary.

The shared rollout coordinator validates a group and origin, materializes or
recovers ordered isolated children, verifies each child, and publishes exact
receipts and lineage. It does not select a provider, open an actor session,
apply a treatment, or evaluate a child.

Evidence-lifecycle composition is concrete and task-owned. The lifecycle
composition root calls each retained task's materializer, verifier, optional
operation resolver, and optional smoke environment directly. A lifecycle
without interactive operations carries no placeholder resolver or
smoke-environment port, and there is no shared lifecycle adapter protocol.

Harbor export, agent execution, and import use the concrete pump integration
owned by the harness. That integration calls the pump functional core and
durability owner directly; the neutral world definition contains no provider
or Harbor port. Evaluation is called by the importer after durable run
verification, never by live world transition code.

## Trial evidence boundary

The pump repository and its artifact inventory remain the replay authority.
Harbor import verifies that task-owned evidence, evaluates the verified run,
and attaches the inventory to `TrialRecord.episode_artifact`. It does not copy
snapshots, transition counts, temporal evidence, or replay identity into a
shared world-execution projection.

`OutputRecord` records whether execution terminated normally or was truncated,
plus the current completion, stop, or failure reason. `CostRecord` owns
aggregate calls, tokens, cache usage, advisor usage, and estimated cost. Public
experiment and leaderboard exports select report fields only; they do not
publish episode state, verifier paths, sealed identifiers, provider
configuration, or recovery data.

## Supported entry points

| Entry point | Current behavior |
| --- | --- |
| Python catalogue | Resolves current build/profile registration only. |
| Installed actor JSON | `aec-bench task pump-station-world actor-interface` calls the pump episode host. |
| Installed control JSON | `aec-bench task pump-station-world control-interface` calls pump controls or explicit rollout composition. |
| Harbor agent | Loads the pump bridge and calls the pump session owner directly. |
| Harbor import | Verifies pump artifacts and calls the pump evaluator directly. |

SSC-03 uses the same build/profile and optional rollout contracts through its
existing evidence-lifecycle owner. A minimum lifecycle need not support
operations, snapshots, branching, rollout, Harbor, or provider adaptation.

## Failure semantics

The boundary fails closed for unknown or stale build/profile identity, stale
decisions, unavailable actions, unauthorized controls, invalid rollout
identity, immutable-byte collisions, repository corruption, and incomplete
verification evidence. Transport and provider failures remain failures; they
cannot manufacture a successful transition or evaluation.

## Proof

- [catalogue and two real definitions](../../tests/task_world_templates/continual/test_catalogue.py)
- [episode state, decisions, limits, and recorder](../../tests/task_world_templates/continual/test_episode.py)
- [rollout contracts](../../tests/task_world_templates/continual/test_rollout_contract.py)
- [SSC-03 rollout](../../tests/task_world_templates/continual/test_ssc03_rollout_control.py)
- [world-kernel conformance](../../tests/task_world_templates/continual/test_hydraulic_world_conformance.py)
- [separate-process actor resolution](../../tests/task_world_templates/stewardship/wastewater_pump_station/test_actor_interface_transport_e2e.py)
- [pump transition retry and recovery](../../tests/task_world_templates/stewardship/wastewater_pump_station/test_registered_world_run_transitions.py)
- [pump functional core](../../tests/task_world_templates/stewardship/wastewater_pump_station/test_functional_core.py)
- [current pump serialization](../../tests/task_world_templates/stewardship/wastewater_pump_station/test_world_run_serialization.py)
- [registered Harbor path](../../tests/harness/test_pump_station_harbor.py)
- [registered rollout child through Harbor](../../tests/harness/test_pump_station_rollout_child_harbor.py)
- [verified pump TrialRecord import](../../tests/harness/test_stewardship_harbor_import.py)
- [public report visibility](../../tests/communication/test_standalone.py)
- [registered rollout](../../tests/task_world_templates/stewardship/wastewater_pump_station/test_registered_rollout_orchestration.py)
