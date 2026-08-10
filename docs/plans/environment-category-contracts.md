# Environment Category Contract Plan

| Field | Value |
| --- | --- |
| Class | Plan |
| Status | Historical |

## Purpose

This plan separates the minimum meaning of an interactive world or finite
lifecycle from the additional features of the current examples.

It does not define a common environment base class or a shared state machine.
It records what exists, who owns it, how many real consumers use it, and
whether it should stay, move, simplify, or wait. It then drafts the smallest
behavioural contracts supported by that evidence.

The Finite Lifecycle contract is supported by stormwater and structural review
tasks. The Interactive World contract is supported by wastewater pump-station
stewardship and dam seepage monitoring.

## Evidence limits

The current evidence is uneven:

- the world catalogue contains wastewater pump-station stewardship and dam
  seepage monitoring;
- RS1 and RS2 are profiles of that same world and use the same executable
  build;
- the lifecycle catalogue contains drainage-model review, hydraulic interaction
  review, hydraulic design response, and facade submittal review;
- the first three lifecycles belong to the stormwater family and facade
  submittal review belongs to structural engineering;
- drainage-model review has no operation protocol;
- the other two lifecycles share a source-bound hydraulic operation protocol.

The seepage task is a separate World family with its own state, evidence
actions, observation, completion, and evaluation. It proves the World minimum
without pump persistence, controls, rollouts, or provider integration. The
structural facade lifecycle uses the same finite progression with different
evidence, result fields, and verification, so the lifecycle minimum is also no
longer inferred from one engineering family.

## Classification

| Class | Meaning |
| --- | --- |
| Platform rule | Required by AECBench validity, identity, execution, evidence, or reporting |
| Category minimum | Required for something to be an interactive world or finite lifecycle |
| Optional capability | Needed by a supported subtype, but not by every member of the category |
| Domain behaviour | State, calculations, actions, evidence, or verification owned by one task family |
| Integration | Adapter, provider, transport, or harness composition |
| Experiment | Treatment, comparison, qualification, or research orchestration |

The action labels mean:

- **Stay**: the present owner is correct.
- **Move**: the present owner conflicts with the component's meaning.
- **Simplify**: keep the behaviour but reduce an unnecessary shape or name.
- **Wait**: there is not enough evidence to extract, move, or generalise it.

## Shared platform components

These components are common benchmark rules. They do not justify one world and
lifecycle runtime.

| Component | Class | Current owner | Consumers | Action |
| --- | --- | --- | --- | --- |
| Task and environment visibility | Platform rule | `contracts`, tasks, and environment owners | All execution families | **Stay.** Keep public and holdout material explicit. |
| Exact executable and input identity | Platform rule | World and lifecycle definitions plus compiled evidence | Worlds, lifecycles, harness, and trial finalisation | **Stay.** Each execution family can use its own identity shape. |
| Failure, incomplete, termination, and truncation facts | Platform rule | Execution owner and `OutputRecord` | All reportable runs | **Stay.** Session completion must not imply task completion. |
| Usage and cost | Platform rule | Harness and `CostRecord` | All reportable runs | **Stay.** Per-session evidence can support, but not replace, the aggregate authority. |
| Verification and evaluation | Platform rule | Task verifier and evaluation | All task families | **Stay.** Runtime progression must not score itself. |
| Trial and artifact evidence | Platform rule | `TrialRecord`, ledger, and producing domain | All reportable runs | **Stay.** Owner-specific evidence remains separate. |
| World and lifecycle catalogues | Platform registration | Separate composition roots | Their own execution families | **Stay separate.** Do not create a universal environment registry. |
| Static `TaskDefinition` loading | Task-authoring rule | `tasks` and task contracts | Artifact and workspace tasks | **Stay.** Do not use it as a common environment base. |

## Interactive-world component map

### Proven minimum and platform shell

| Component | Class | Current owner and consumers | Action | Evidence |
| --- | --- | --- | --- | --- |
| Authoritative task state, actor observation, valid actions, deterministic transition, rejection, and domain termination | Category minimum | Pump and dam seepage task functions; two world families | **Stay task-owned.** | Current authoring guide and world conformance proofs |
| `Transition` and `ActionRejected` | Category minimum | `worlds/runtime/world_logic.py`; pump, seepage, and episode shell | **Stay.** This is the smallest useful shared world value. | Rejections leave state unchanged; accepted transitions carry the next state and output |
| Live state, opaque decision, accepted-step advancement, limits, truncation, and recorder ordering | Platform shell | `worlds/runtime/episode.py`; pump runtime plus direct seepage composition | **Stay, then simplify.** Keep freshness, separate termination and truncation, and record-before-advance. Review unused accounting and lifecycle methods separately. | Runtime tests and both world proofs |
| Build identity, content-pinned profiles, loading, and catalogue resolution | Platform rule | `worlds/runtime/definition.py`, `worlds/catalogue.py`, and world identity contracts | **Stay.** Do not add persistence or stewardship meaning. | Required by reproducibility and exact recovery |
| Installed actor calls and results | Platform boundary | `contracts/continual_world.py` and the actor part of `contracts/world_interface.py`; pump CLI, Prime, and Harbor | **Stay as the current installed boundary.** Do not call its exact transport shape universal yet. | One world, used across real process boundaries |
| Behavioural conformance helper | Category and platform proof | `tests/worlds/world_conformance.py`; pump and seepage worlds | **Stay.** | Deterministic initialization, safe observation, rejection safety, transition replay, and evaluation |

### Optional stewardship and pump components

| Component | Class | Current owner and consumers | Action | Evidence |
| --- | --- | --- | --- | --- |
| World-session and host-control models | Optional stewardship capability | `contracts/world_session.py` and the control part of `contracts/world_interface.py`; pump integrations only | **Move or narrow later.** The only execution kind and snapshot type are stewardship-specific. | One world family; current installed and persisted boundary |
| Branch and rollout coordination | Optional persistence capability | `worlds/runtime/branch_port.py`, `rollout_control.py`, `rollout_repository.py`, and rollout contracts; pump only | **Wait.** It is task-neutral in code but has no second world consumer. A later move to the pump owner is possible. | One world family; RS1 and RS2 do not count twice |
| Pump physics, work, clocks, state, actions, and views | Domain behaviour | Pump world | **Stay.** | Shared runtime has no pump import |
| Pump profiles and reference packages | Domain data with platform identity | Pump world | **Stay.** Review provider metadata separately. | Two profiles of one executable world |
| Pump run repository, replay, recovery, and serialization | Optional persistent-world capability plus domain behaviour | Pump world | **Stay pump-owned.** Do not extract a universal world repository. | Canonical replay authority for pump runs |
| Temporal documentary evidence | Optional domain capability | Pump `temporal_evidence` package | **Stay pump-owned.** | One real actor evidence surface |
| Host controls and deterministic continuation policy | Optional domain capability | Pump `world_control.py` and `host_continuation.py` | **Stay pump-owned.** | Eligibility and completion depend on pump state |
| Pump rollout adaptation | Optional domain integration | Pump `continual_rollout_adapter.py` and rollout models | **Stay while shared rollout ownership waits.** | One concrete adapter into the optional rollout API |
| Pump verifier and evaluator | Domain evaluation | Pump world | **Stay pump-owned.** | Uses canonical replay outside the transition |
| Fixed reference controller | Domain driver or qualification support | Pump `reference_controller.py`; Harbor reference execution | **Wait.** It drives the world and is not world behaviour. Decide its permanent role when that path next changes. | One current integration caller |
| Prime pump session, proxy, guidance, evidence, and journey | Integration | `harness/pump_station_prime` | **Stay concrete.** Do not extract a generic journey from one world. | One Prime world integration |
| Harbor pump export, execution, verification, and import | Integration | `harness/pump_station_harbor` | **Stay concrete.** | One Harbor world integration |
| Prime trajectory and refinement studies | Experiment | `experimentation/qualification` | **Stay.** | Consumes world evidence without owning world semantics |

## Finite-lifecycle component map

### Current definitions

| Definition | Checkpoints | Operations | Variants | Deterministic smoke environment |
| --- | ---: | ---: | ---: | ---: |
| Drainage-model review | 3 | No | 4 | No |
| Hydraulic interaction review | 3 | Yes | 4 | Yes |
| Hydraulic design response | 4 | Yes | No | Yes |
| Facade submittal review | 3 | No | No | No |

All four definitions use a linear checkpoint order. No current task proves a
parallel or branching checkpoint graph.

### Ratified minimum and platform shell

| Component | Class | Current owner and consumers | Action | Evidence |
| --- | --- | --- | --- | --- |
| Lifecycle identity, finite ordered checkpoints, and unique checkpoint identity | Category minimum | `contracts/evidence_lifecycle.py`; all four definitions | **Stay.** | Four real definitions across two engineering families |
| Release, one active checkpoint, accepted submission, host advance, and terminal completion | Category minimum plus platform validity | `lifecycles/runtime/lifecycle.py` and `state.py`; all four definitions | **Stay.** | Shared by two lifecycles without operations and two operation lifecycles |
| Release, instruction, and JSON submission paths and required fields | Optional staged-evidence subtype | `EvidenceCheckpointSpec`; all four definitions | **Stay for evidence lifecycles.** Do not place these file conventions in the minimum finite-lifecycle contract. | Four current tasks with task-owned result shapes |
| Earlier-checkpoint dependencies | Claimed graph capability | `EvidenceLifecycleSpec`; all four tasks use a simple chain and runtime selects the next list item | **Wait or simplify.** Do not claim general graph execution. | No real non-linear consumer |
| Attempts, immutable accepted submissions, explicit failure, publication, and recovery | Platform rule | Lifecycle runtime and durable stores | **Stay.** These protect benchmark validity, not category meaning. | Current lifecycle execution paths |
| Catalogue registration | Platform registration | `lifecycles/catalogue.py` | **Stay.** Direct composition is clear. | Three registered definitions |
| Compiled package, spec, variant, and implementation identity | Platform rule | `lifecycles/compiled.py` and catalogue | **Stay.** Stage 3 replaced the partial file lists with shared and task-owned executable source roots. | The inventory covers lifecycle progression, evidence storage, verification, operations, and task calculations |
| Fresh or persistent model context and visibility policies | Integration and experiment treatment | `lifecycles/runtime/episode.py` and `harness/lifecycle_local.py` | **Stay outside the lifecycle minimum.** | Local harness, studies, and Prime fresh sessions |

### Optional lifecycle capabilities and domain components

| Component | Class | Current owner and consumers | Action | Evidence |
| --- | --- | --- | --- | --- |
| Conditional evidence requests | Optional staged-evidence capability | `ConditionalEvidenceSpec` and `lifecycles/runtime/request_*` | **Wait.** It is documented and tested, but no registered lifecycle uses it. | No real task consumer |
| Public operation catalogues, prerequisites, budgets, execution, records, and snapshots | Optional computational-lifecycle capability | `ConditionalOperationSpec` and `lifecycles/runtime/operation_*`; hydraulic review and design response | **Stay, then isolate.** Two real consumers prove family reuse, not a universal lifecycle operation contract. | Two hydraulic tasks |
| Revisioned physical and visible source model | Optional source-bound computational capability | Lifecycle operation protocol and state | **Keep out of the minimum contract.** | Both operation consumers use the same hydraulic source model |
| Branch and revisit | Optional lifecycle or experiment capability | Lifecycle runtime and studies | **Stay optional.** | No evidence that every finite lifecycle requires it |
| Drainage-model specification, variants, materializer, and verifier | Domain behaviour | `lifecycles/stormwater_design` | **Stay.** | Proves the shared progression path without operations |
| Hydraulic-review specification, variants, materializer, operations, and verifier | Domain behaviour | `lifecycles/stormwater_design` | **Stay.** | One revision-review lifecycle |
| Design-response specification, selection, materializer, operations, and verifier | Domain behaviour | `lifecycles/stormwater_design` | **Stay.** | One intervention lifecycle |
| Hydraulic models, calculations, packages, reports, revisions, and interventions | Shared family capability | `lifecycles/stormwater_design/hydraulics` | **Stay in the family.** Do not create a global engineering package until another benchmark owner needs the same stable behaviour. | Two lifecycle consumers in one domain family |
| Deterministic smoke actors | Optional qualification capability | `design_response_smoke.py` and `hydraulic_review_smoke.py` | **Stay optional.** | Proves execution, not category generality |
| Local lifecycle tools and adapter execution | Integration | `harness/lifecycle_local.py` | **Stay, but remove hydraulic assumptions during the ownership cleanup.** | Shared lifecycle harness with current domain leakage |
| Prime hydraulic-review endpoint, skill, and checkpoint sessions | Integration | `harness/hydraulic_review_prime` | **Stay concrete.** Do not generalise before a second Prime lifecycle integration exists. | One Prime lifecycle integration |
| Prime Lab lifecycle export and environment | Integration | `prime_lab` | **Stay.** Consume declared lifecycle capabilities instead of hydraulic file names. | External Prime package path |
| Lifecycle calibration, ablation, transfer, and finalisation | Experiment | `experimentation/lifecycle_studies` | **Stay.** | Consumes canonical evidence and does not own progression |

## Stage 2 behavioural contracts

These contracts describe behaviour. They do not define a Python API, a common
state model, a production base class, an exact transport, or one environment
runtime.

The distinction is:

```text
category meaning
    what makes this an Interactive World or Finite Lifecycle

AECBench execution rules
    what makes one run valid, reproducible, and reportable

optional capabilities
    features which a concrete task can add when it has a real need
```

### Rules shared by both categories

A benchmark-valid execution in either category follows these existing
AECBench rules:

| Rule | Required behaviour |
| --- | --- |
| Task ownership | The task owner defines domain meaning, completion, and verification. |
| Provider neutrality | Task state, actions, stages, outputs, and verification do not depend on an adapter, model provider, Prime, Harbor, or one harness. |
| Controlled visibility | The actor receives only the observation, material, tools, and prior evidence allowed by the task. Hidden inputs, verifier state, future material, and host controls remain host-only. |
| Exact identity | The run binds all outcome-affecting task inputs, configuration, limits, executable code, verifier code, and evaluation scope. |
| Boundary validation | Untrusted, persisted, and cross-process values are validated before use. |
| Authoritative evidence | Each accepted effect has one task or host authority. Provider output and transport logs do not replace task state or accepted lifecycle evidence. |
| Explicit outcome | Completion, truncation, failure, and incomplete recovery remain separate. A successful model turn or process exit does not imply task completion. |
| Independent evaluation | Task-owned verification supplies evidence. Evaluation owns validity, reward, and diagnostics outside live task progression. |
| Honest reporting | Trial and cost records refer to canonical execution evidence. They do not repair or reinterpret failed execution as success. |

These rules do not require worlds and lifecycles to share an implementation.

### Contract: Interactive World

An Interactive World is a task-owned causal process with a repeated feedback
loop:

1. Exact scenario inputs create one authoritative initial state.
2. The current state produces an actor-visible observation.
3. The actor selects a task-owned action.
4. The world rejects the action or produces one accepted transition.
5. An accepted transition establishes the next authoritative state and can
   change later observations, task evidence, or evaluation.
6. The loop continues until task-owned termination or a separate host outcome
   stops the episode.

A process is not an Interactive World only because it contains state or
ordered work. At least one accepted actor action must be able to affect a later
task-owned state, observation, evidence item, or evaluation result.

#### Category meaning

| Property | Requirement |
| --- | --- |
| Initial state | All outcome-affecting scenario inputs create one authoritative current state. |
| Observation | The current state has an explicit actor-visible projection. The projection does not expose hidden state and then rely on the transport to remove it. |
| Action | The task owns the permitted action meaning and validates action values at their boundary. |
| Transition | A valid action and all declared event or random inputs produce one next state and any task output. |
| Rejection | An unavailable or invalid action returns a stable rejection reason and leaves the current state unchanged. |
| Completion | The world declares its domain termination conditions, or declares that it has no natural terminal state and needs a bounded evaluation scope. |
| Evaluation input | The task declares which verified state, trajectory, and artifacts can be used to evaluate the selected scope. |

These are logical operations, not required function signatures. State and
action meaning remain in the concrete world. The transition does not persist
files, call a provider, advance an episode step, apply host limits, or score
itself.

#### World execution rules

The AECBench episode shell adds these rules around the task-owned world:

- outcome-affecting initialisation, event, and random inputs are explicit;
- an accepted action advances state and the episode step once;
- a rejected action leaves state, step, and current decision unchanged;
- stale action association is rejected when the episode uses opaque decisions;
- when a retryable action boundary exists, an exact retry returns the confirmed
  prior effect and does not apply it twice;
- required recording succeeds before an accepted advancement becomes current;
- task-owned termination and host truncation remain separate;
- deterministic transitions and final state can be replayed from exact inputs
  and action lineage; and
- any non-determinism is explicit, bounded, recorded, and included in the
  evaluation claim.

A terminated world rejects later actor actions. If an external effect might
have occurred but cannot be confirmed, the outcome is incomplete or unknown.
It is not an accepted transition.

#### Optional world capabilities

The minimum contract does not require:

- dynamic action catalogues or input schemas;
- host controls;
- autonomous clocks or events;
- durable persistence and recovery;
- snapshots, branches, or rollouts;
- multiple actors, tenure, or handover;
- temporal or documentary evidence;
- staged evidence;
- Prime, Harbor, ACP, or another provider transport;
- multi-session journeys; or
- experiment treatments and qualification drivers.

When host controls exist, they use a separate validated authority surface from
actor actions. Each other optional capability needs a current consumer, a
clear owner, and its own proof.

### Contract: Finite Lifecycle

A Finite Lifecycle is a bounded task process with a declared sequence of
stages. It coordinates stage-specific actor work and host-owned progression.
It is not an Interactive World only because it has state or ordered work.

The current evidence comes from three stormwater lifecycles and one structural
facade lifecycle. They use the same progression runtime with different task
evidence, submission fields, calculations, and verifiers.

#### Category meaning

| Property | Requirement |
| --- | --- |
| Finite structure | Before execution, the task declares a finite set of stages, an initial stage, permitted progression, and terminal completion. |
| Stable identity | The lifecycle and each stage have unique identities. |
| Current position | While actor work is open, no more than one stage is active. |
| Stage contract | Each stage declares its actor-visible objective, permitted work, and required result. |
| Controlled progression | A rejected result leaves the current stage and prior accepted results unchanged. |
| Accepted result | One accepted result completes the active stage once. It does not let the actor activate another stage. The host can apply only a task-declared progression. |
| Explicit completion | The lifecycle is complete only after the host accepts a terminal-stage result and records lifecycle completion. |
| Separate execution state | A model turn, process, or actor session ending does not complete a stage or lifecycle. |

These rules do not require file releases, JSON submissions, conditional
evidence, calculations, source revisions, retries, branches, or a specific
agent.

#### Lifecycle execution rules

The AECBench host adds these rules around the task-owned lifecycle:

- the host owns stage release, result acceptance, progression, failure state,
  and finalisation;
- the actor, adapter, and provider cannot select or advance the active stage;
- only the active stage material and permitted prior evidence are visible;
- future-stage material and hidden verification inputs remain host-only;
- an invalid, stale, foreign, or malformed result cannot advance the lifecycle
  or replace accepted evidence;
- accepted results and stage transitions have durable content identity;
- a retry does not accept the same result or apply the same task effect twice;
- the host can apply only task-declared stage progression;
- task verification uses canonical accepted evidence and runs outside
  progression; and
- provider, storage, identity, verification, and recovery failures remain
  failed or incomplete.

The exact executable identity must cover every implementation dependency that
can change release, progression, task operations, acceptance, or verification.
Stage 3 applies this rule through shared lifecycle source roots and separate
task-owned executable roots.

#### Current staged-evidence subtype

The present lifecycle definitions use a staged-evidence subtype:

- each stage is a checkpoint;
- each checkpoint declares release material, an instruction, a submission
  destination, and a public submission shape;
- the host releases only the active checkpoint material;
- the actor proposes a JSON submission for that checkpoint;
- the host validates checkpoint identity and declared fields;
- accepted submission bytes are content-bound and cannot change in that run;
  and
- the host can release the next checkpoint only after it accepts the current
  submission.

The current runtime follows one linear checkpoint list. Dependency metadata
does not prove branching, parallel execution, or an arbitrary stage graph.
File paths, Markdown instructions, JSON submissions, and package directory
names belong to this subtype, not to every Finite Lifecycle.

#### Optional lifecycle capabilities

The minimum contract does not require:

- conditional evidence requests;
- task-owned calculation or operation catalogues;
- a revisioned physical and actor-visible source model;
- task variants or deterministic package materialisation;
- fresh or persistent model context;
- different views of prior accepted evidence;
- checkpoint revisit or branch lineage;
- deterministic smoke actors;
- Prime, Harbor, or another execution integration; or
- calibration, treatment comparison, and transfer studies.

The current source-bound hydraulic operation protocol is a stormwater-family
capability. It is not a general lifecycle operation contract.

### Conformance and ratification

Conformance is proved through behaviour, not inheritance. Tests can connect a
task's real functions to shared assertions through test-only callbacks or
fixtures. Production code does not need a common base class or test adapter.

A conformance check tests only:

- the category minimum;
- the applicable AECBench execution rules; and
- optional capabilities which the task declares.

Conformance does not require a new content hash, identity field, or persisted
record. Add those only when they protect a named replay, evidence-integrity, or
reproducibility claim. Direct value and behaviour checks are sufficient for
test-local proof.

The world-owned proof checks:

- repeatable initial state and observation from the same complete inputs;
- an actor-safe observation;
- unchanged state after rejection;
- for a deterministic world, equal transitions, outputs, termination, and
  final state during replay;
- for a non-deterministic world, explicit bounded inputs and an evaluation
  claim which states the limitation;
- rejection after domain termination; and
- repeatable evaluation from canonical verified evidence outside the
  transition.

The AECBench episode-shell proof checks:

- one state and step advance for one accepted action;
- safe handling of stale decisions, exact retries, and recording failure;
- separate task termination and host truncation; and
- explicit limit and runtime failure reasons.

For a Finite Lifecycle, the minimum proof checks:

- complete and unique lifecycle and stage identities;
- one finite declared progression and no more than one active stage;
- no state change after an invalid result;
- exactly one stage completion for one accepted result;
- only task-declared host progression and no actor-owned advance;
- completion only after the terminal result and host finalisation;
- explicit failure and incomplete recovery; and
- repeatable verification from canonical accepted evidence outside
  progression.

The four registered lifecycles ratify the Finite Lifecycle contract across
stormwater and structural review. The pump and dam seepage worlds ratify the
Interactive World contract because:

1. both real members satisfy it without task-specific exceptions;
2. each uses its own domain types, actions, observations, and evaluation;
3. shared tests do not require a production base class or transport; and
4. the shared rules are category meaning or AECBench validity rules.

A second profile, test double, duplicate wrapper, renamed copy, or second
integration is not a second consumer. If a new task needs an exception, first
check whether the rule came from the first example and belongs in an optional
capability.

## Confirmed ownership and simplification findings

These findings are inputs to later stages. Stage 1 does not change their
protected formats or runtime behaviour.

### World findings

1. `contracts/world_session.py` has a generic name but supports only a
   stewardship execution kind and a `StewardshipStateSnapshotRef`.
2. The host-control part of `contracts/world_interface.py` depends on those
   stewardship session values. It is not part of a minimum actor world.
3. The shared rollout subsystem has only the pump as a real world consumer.
4. `contracts/evaluation_result.py` contains pump-specific stewardship metrics,
   including pump availability and maintenance-resource fields, in the central
   `EvaluationResult` contract. Do not repeat this pattern for another world.
   Moving it needs an approved persisted-format cutover.
5. RS1 and RS2 profile descriptors include provider metadata. Provider version
   changes must not change task-owned world identity without changing world
   meaning.
6. Parts of `worlds/runtime/episode.py` have no production caller in the current
   world path, including model-usage mutation and some manual stop methods.
   Confirm supported callers before deletion.
7. Registered profiles use the v2 pump reference package while the package
   reader still defaults to v1. Confirm retained certification and evidence
   requirements before changing or deleting v1.

### Lifecycle findings

1. The ownership cleanup replaced the hydraulic path used by shared lifecycle runtime, local
   harness, Prime Lab, and study code with the neutral
   `workspace/operations/current-source.json` projection. Source-bound
   operations remain an optional lifecycle capability.
2. The operation protocol assumes one revisioned source with physical and
   visible hashes, a `revision_id`, stale-source rejection, activation, and one
   current source before and after each operation. This is a valid optional
   subtype, not a finite-lifecycle minimum.
3. The ownership cleanup moved shared hydraulic evidence and smoke behaviour into named
   stormwater-family modules. Design response no longer imports private
   helpers from hydraulic review.
4. Stage 3 replaced the partial lifecycle executable inventory. The current
   digest includes the shared lifecycle substrate and each task's
   materialisation, operation, verification, and engineering sources. Smoke
   actors and provider or experiment code remain separate execution evidence.
5. The ownership cleanup moved lifecycle verification record models to `contracts`.
   Lifecycle progression no longer imports upward from evaluation.
6. Conditional evidence requests have no registered task consumer. Keep them
   outside the minimum contract and review their supported-boundary status
   before adding more machinery.

### Cross-cutting naming findings

1. `TaskDefinition.lifecycle` means publication status: proposed, active,
   deprecated, or retired. It does not mean a finite task lifecycle. Preserve
   the supported field until a separate contract change, but use "publication
   status" in new prose and identifiers.
2. `harness/process_runtime/world_runtime.py` uses "world" for generated
   problem representations and governance work. It is not an interactive-world
   runtime. Rename it when that area next changes.
3. The ownership cleanup removed the unused header-only `src/aec_bench/tasks/lifecycle.py`
   module.
4. Stage 6 replaced the shared category names with `InteractiveWorld*` without
   aliases. Optional continual actor, control, snapshot, branch, and rollout
   records keep their narrower names and saved fields.

## Stage 1 result

The present physical ownership is mostly sound:

- world behaviour remains with the pump world;
- lifecycle behaviour remains with the stormwater lifecycle family;
- Prime and Harbor compositions remain in the harness;
- experiments consume evidence without defining task semantics; and
- there is no tracked global engineering package without a real shared owner.

The main problem is not a missing common environment framework. It is that a
few optional or domain-specific shapes appear under shared names or inside
shared runtime code.

The minimum-contract stage must therefore:

1. describe the shared meaning without copying stewardship sessions, hydraulic
   source state, persistence, branching, or provider transport;
2. keep AECBench validity rules distinct from category meaning;
3. treat staged evidence, computational operations, persistence, stewardship,
   and journeys as optional capabilities; and
4. keep each contract non-normative until another domain tests it.

No production behaviour changes in Stage 1.

## Stage 2 result

The plan defined two behavioural contracts:

- Interactive World separates task-owned causal transitions from the episode
  shell and optional persistence, control, and integration features.
- Finite Lifecycle separates bounded stage progression from the current
  staged-evidence files and optional hydraulic operations.

Neither contract created a new production abstraction. Later stages added the
structural facade lifecycle and dam seepage World as the second-domain proofs.

No production behaviour changes in Stage 2.

## Stage 3 result

The lifecycle executable digest now covers:

- the shared lifecycle contracts and progression runtime;
- the evidence-storage helpers used by progression;
- lifecycle evaluation;
- each task's materialisation and verification code;
- task-owned operation resolvers; and
- the hydraulic implementation used by the two computational lifecycles.

An independent test walks task-owned lifecycle imports and rejects a registered
inventory which omits a lifecycle, operation, verifier, or engineering source.
Each current lifecycle also has a distinct executable identity.

Stage 3 changes executable provenance. It does not change lifecycle task
behaviour or add a common environment runtime. Existing disposable compiled
packages and local run evidence must be regenerated before comparison with new
results.

## Stage 4 result

The executable conformance checks now match the category contract split:

- the world-owned proof confirms that a rejected action leaves both the
  authoritative state and actor observation unchanged;
- the existing episode-shell proof separately covers accepted advancement,
  stale decisions, termination, truncation, limits, and recording failure;
- every registered lifecycle completes through the same shared progression
  runtime with its real task package and deterministic task evidence; and
- lifecycle verification produces the same result when it reads the same
  canonical accepted evidence again.

The shared lifecycle runtime tests continue to prove invalid-result safety,
host-only progression, immutable accepted submissions, recovery, and terminal
finalisation. These rules do not need separate runtime implementations because
all registered tasks use the same runtime without a task-specific progression
branch.

Stage 4 adds only test code and documentation. It does not add a production
interface, base class, environment runtime, or content identity. Existing
hashes remain only where current contracts use them for executable identity,
accepted evidence, or replay. The ownership cleanup must remove any hash which
cannot be tied to one of those named claims.

## Ownership cleanup result

The confirmed lifecycle ownership problems are now corrected:

- source-bound operations use the neutral
  `workspace/operations/current-source.json` projection;
- lifecycle verification records live in `contracts`, while evaluation keeps
  the scoring functions;
- shared hydraulic evidence and smoke helpers live with the stormwater
  lifecycle family instead of one concrete task;
- the design-response executable identity no longer includes unrelated
  hydraulic-review task modules; and
- the unused task lifecycle module is removed.

This is a direct internal cutover. Existing disposable lifecycle packages and
local runs which use `workspace/hydraulics/current-source.json` must be
regenerated. There is no compatibility reader and no parallel path.

The hash audit kept the existing operation hashes. Each selected hash protects
an active claim: exact request and result bytes, stale-source handling,
operation reuse, transition recovery, canonical evidence, or replay. The
cleanup does not add a new content-identity layer.

The cleanup does not change protected World session, actor, host-control,
replay, or evaluation formats. Stage 5 records the second-world proof and Stage
6 records the shared naming cutover. Conditional lifecycle evidence requests
remain outside the minimum contract because no current task uses them.

## Stage 5 result

Stage 5 added one second real consumer for each category. These are different
task families, not new profiles, wrappers, or integrations for the first task.

### Finite Lifecycle proof

The existing structural facade submittal task now has a three-checkpoint
Lifecycle:

1. source, calculation, and material review;
2. comment and boundary-exception review; and
3. final response review.

It reuses the current facade template engine and fixed source values. It has no
hydraulic operation resolver, source revision, variant, provider integration,
or production smoke actor. Its submission fields, findings, decisions, and
verifier are task-owned.

The task completes the review while correctly reporting
`not_ready_to_close`. This proves that lifecycle completion does not imply a
favourable engineering outcome.

The structural and stormwater tasks now prove the Finite Lifecycle minimum
across two engineering families. They need the same finite stage identities,
one active stage, host-owned progression, immutable accepted results, explicit
completion, and independent repeatable verification. Their calculations,
evidence, result fields, and verifier rules remain different.

No production base class, common task model, compatibility path, or new
runtime was added.

### Interactive World proof

Dam seepage monitoring is now a second registered Interactive World. It uses
one task-owned synthetic monitoring plan with scheduled seepage readings,
reservoir levels, rainfall, site-specific expected and alert flows, a
measurement-system condition, and downstream visual conditions.

The actor can request confirmation readings, check the measurement system,
inspect the current downstream area, and submit either engineering-review
escalation or continued routine surveillance. Requested evidence changes later
observations. The World accepts either final engineering judgement and leaves
correctness to independent evaluation.

The task uses the existing `Transition`, `ActionRejected`, episode shell,
definition, profile, and catalogue boundaries. It adds no host controls,
persistence, replay repository, rollout, provider integration, journey, or
production base class. The pump and seepage tasks now prove the Interactive
World minimum with different domain state, actions, effects, and evaluation.

## Stage 6 result

The two behavioural contracts are now ratified in
[`CONTRACTS.md`](../CONTRACTS.md). The production names now match those
contracts:

- `InteractiveWorldProfileRef` owns exact task profile identity;
- `InteractiveWorldDefinition` binds one build to its supported profiles;
- `InteractiveWorldCatalogue` registers real Worlds at the composition root;
  and
- `default_interactive_world_catalogue` returns the current registrations.

The cutover is direct. There are no aliases, versioned replacements, or
parallel catalogue paths. `contracts/interactive_world.py` owns the minimum
build and profile identity. `contracts/continual_world.py` now owns only the
installed calls and optional persistent control and rollout records.

The shared `Episode` keeps step and wall limits, opaque decisions, safe
rejection, recorder ordering, task termination, and host truncation. Its
unused model-token accounting, cost accounting, manual cancellation, and
manual close methods are removed. Provider and journey usage limits stay with
their existing harness owners.

Saved pump field names and the current `ContinualWorldActorRequest`,
`ContinualWorldSnapshotRef`, control, branch, and rollout record families are
unchanged. Renaming or removing those saved boundaries needs a separate audit
of current replay and external readers.

No Lifecycle runtime change was needed in Stage 6. Two task families already
use the same finite progression without a task-specific runtime branch.

## Completion

This six-stage plan is complete. Any later installed actor boundary for a
non-pump World or saved pump-record cutover is a separate design change.

## Closeout evidence

The [import-graph evidence](../../tests/fixtures/architecture/import-graph-0126f007.json)
is pinned to merge commit `0126f007a33597d9519f46ce12078de84fabcbe1`.
It contains the full top-level package graph, module cycles for any top-level
cycle, composition-root back-imports, optional dependency leakage, source-tree
identity, and the isolated base-wheel import smoke. It found no top-level
strongly connected component, back-import, or optional dependency leak. The
base-wheel smoke passed.

The
[parent-versus-head regression report](../../tests/fixtures/architecture/regression-delta-d3fc70e5-7f2084e6.json)
compares parent `d3fc70e57727bad4266eaee57f0143bef199ab85` with head
`7f2084e6bbecee993929c498f17804348b866767`. Both commits ran with:

```text
PYTHONPATH=<worktree>/src python -m pytest tests -q --tb=no \
  --import-mode=importlib --junitxml=<result.xml>
```

The explicit import mode was needed because the historical commits contain
test files with the same base name in different folders. The current pytest
configuration now selects this mode by default.

The parent result was 7,460 passed, 92 failed, and 21 skipped from 7,573
tests. The head result was 7,480 passed, 92 failed, and 21 skipped from 7,593
tests. All 92 failures were retained from the parent. The head added no new
failure and removed no existing failure.

The retained failures remain active tests; they are not hidden or skipped by
this closeout. Their main owners and removal conditions are:

- contracts and experimentation own stale compatibility, schema, call-shape,
  and generated-identity expectations; remove this baseline when those tests
  are replaced or updated to the one current interface;
- lifecycle, Harbor, Prime, and Prime Lab integration owners must supply the
  current explicit operation resolver and supported transport boundary; remove
  their baseline entries when those integrations use the current contract; and
- harness and Prime security tests that require local sockets or macOS sandbox
  execution must run in an environment that permits those operations; remove
  those baseline entries when the required security boundary is available.

The exact retained test identities stay in the regression report. A later
change must compare against that evidence instead of treating the present
failures as new or silently dropping them.

The following bounded debts remain deliberate:

- installed sessions, controls, persistence, and rollouts remain optional
  stewardship capabilities with one real World consumer;
- `EvaluationResult.stewardship` remains a frozen persisted-format exception;
- conditional evidence remains experimental and has no registered lifecycle
  consumer;
- Prime journeys remain concrete until a second persistent Interactive World
  proves the same continuation semantics; and
- the v1 pump reference package and default reader route remain certified for
  retained readers, while registered pump profiles explicitly use the v2
  three-pump package.
