<!-- ABOUTME: Records the ASW-3C architecture and promotion-candidate review. -->
<!-- ABOUTME: Freezes review evidence without extracting shared stewardship code. -->

# ASW-3C architecture and promotion-candidate review

## Decision

ASW-3C passes as a review-only stage.

The accepted ASW-4 input stays at the existing pump-station implementation. This
stage does not move code, change a schema, add a compatibility promise, or create
a shared stewardship runtime.

One mechanic is a later promotion candidate: atomic publication of a continuing
world run. The candidate is the transaction mechanic, not the pump-station types
or file names. Promotion is not yet allowed. It needs a second task-world
consumer or an unavoidable stable host boundary. It also needs a separate stage
after the ASW-4 programme checkpoint.

All other live pump-station abstractions stay local. Three proposed generic
abstractions are abandoned.

## Review authority

| Item | Frozen value |
| --- | --- |
| Source commit | `4cacff30daf15b4fd7bdb66ca3a3e7db100773b9` |
| Source tree | `e2577c085e5e1c0c53d1c88781b5b410ac07e236` |
| Source branch | `feat/wastewater-pump-station-asw-3c` from merged PR 51 |
| Programme rule | ASW-3C in `asset-stewardship-worlds-prd.md` |
| Review date | 2026-07-30 |
| Runtime changes allowed | None |
| Shared extraction allowed | None |
| Study implementation allowed | None |

The review unit is an abstraction family with one owner and one purpose. It is
not each class name. This keeps one decision for related values that must move or
stay together.

## File allowlist

Only these paths can differ from the frozen source:

1. `.gitignore`
2. `research/asset-stewardship/asw-3c-architecture-and-promotion-review.md`

Any source, test, workflow, contract, or generated study file is outside this
stage.

## Dependency review

### Required direction

```text
shared contracts
  <- pump-station world
shared contracts + pump-station boundary + adapters
  <- direct and Harbor host composition
immutable host evidence
  <- evaluation
frozen eligible evidence
  <- study-local analysis
```

### Live findings

| Check | Live evidence | Result |
| --- | --- | --- |
| Physical and operating rules do not import host, adapter, CLI, evaluation, or study code | `physical_*`, `stewardship_*`, `world_run*`, and `world_session.py` import shared contracts or other pump-station modules only | Pass |
| Production code does not import the research generator or certifier | No production import points to `research/`, the family generator, or the certifier | Pass |
| Shared contracts do not import pump-station code | `contracts/world_session.py` and `contracts/trial_record.py` use only shared contract types | Pass |
| The direct session crosses one explicit shared boundary | `PumpStationWorldSession` maps its local snapshot to `StewardshipStateSnapshotRef` and returns `WorldSessionResult` | Pass |
| Provider code stays outside the physical world | Adapter and host imports occur only in `harbor_session.py`, which is the task-specific outer composition module | Pass |
| Harbor import uses an explicit execution kind | The registry selects `stewardship_world_session` from a fixed allowlist and lazy-loads the task extension | Pass |
| Evaluation reads immutable world evidence | `evaluation/stewardship.py` reloads the run, replays it, and derives gates and liabilities | Pass |
| Evaluation does not change world state | No pump-station world module imports `evaluation`; the evaluator has no transition or publication operation | Pass |
| The first study has no implementation edge | No continuity-study package or study schema exists in production code | Pass |
| ASW-3C adds no dependency edge | The allowlist contains only this record and its ignore exception | Pass |

The task-specific Harbor importer calls the evaluation-owned function after it
has verified the imported run. This is outer composition. It does not place
evaluation rules in the core importer registry or in the pump-station world.
This arrangement must not be used as evidence for a generic stewardship
importer.

## Contract register

| Boundary | Producer and consumer | Owner | Persistence and visibility | Compatibility | Evidence | Current state |
| --- | --- | --- | --- | --- | --- | --- |
| Approved station data and promotion manifest | Certified reference files -> strict reader -> physical kernel and exporter | Pump-station package and promotion authority | Immutable runtime input; public and host-private fields stay separate | Exact v1 files only; unknown files, fields, and versions fail closed | Package reader unit, integration, and E2E gates | Asset-local |
| Physical state and operating interval | Reference reader and session -> physical kernel -> stewardship state | Pump-station physical kernel | In memory, then inside immutable run state; host-private truth | Task-local v1 serializer; unknown versions fail closed | Physical unit, integration, and E2E gates | Asset-local |
| Proposed action and decision context | Agent tool call -> session -> state machine | Pump-station action model | Agent-visible request plus immutable host evidence | Closed action union; unknown actions fail closed | State-machine and semantic-attack gates | Asset-local |
| Operating approval decision | Pump-station policy -> state machine, receipt, and evaluator | Pump-station policy | Host decision; selected result is actor-visible and persisted | Policy version is bound to the run; unknown version fails closed | Policy, state-machine, replay, and version gates | Asset-local |
| Required follow-up, operating limit, work order, and timed process | State machine and event rules -> view, replay, and evaluator | Pump-station operating rules | Current items are actor-visible; full state is host-private and immutable | Task-local typed values; changes need a new rule or receipt version | State, handover, semantic-attack, and evaluation gates | Asset-local |
| Scheduled event and transition receipt | Event scheduler and state machine -> repository, verifier, and evaluator | Pump-station transition rules | Immutable run evidence; future events and latent state stay host-private | Receipt and transition-rule versions are bound and fail closed | Event, replay, version, and crash gates | Asset-local |
| Actor view and information-set binding | Projection code -> session -> proposal validation | Pump-station projection policy | Actor-visible bounded view with host-private source binding | Projection policy and content IDs bind the view | View, stale-view, redaction, and handover gates | Asset-local |
| Handover and continuity carrier | Prior tenure state -> projected current view -> next tenure | Pump-station projection policy; ASW-4 study owns treatment use | Actor-visible current view; treatment material is host-controlled | Keep task-local through the first study | Handover and carrier-orthogonality gates | Asset-local |
| Immutable run manifest, state, commit, receipt, and current pointer | World run -> repository -> session, verifier, importer, and evaluator | Pump-station run repository | Host-private content-addressed evidence; only `current.json` is a mutable selector | Serializer, snapshot, receipt, policy, and rule versions fail closed | Repository, crash, retry, reload, and version gates | Asset-local; mechanic is a boundary candidate |
| Dynamic state snapshot reference | Pump-station session -> host session and TrialRecord | Shared contracts own the task-neutral shape | Run-local and ledger-referenced; no latent state | `aecbench.stewardship-state-snapshot.v1`; strict reload | Contract, direct-session, Harbor, and TrialRecord gates | Repository contract |
| World-session request and result | Host -> pump-station session -> host and Entrypoint | Shared contracts | Run-local request/result, then immutable evidence | `aecbench.world-session.v1`; strict execution kind and open mode | Contract, direct-session, installed-CLI, and Harbor gates | Repository contract |
| Harbor export manifest and artifact inventory | Pump-station exporter -> Entrypoint, verifier, and importer | Pump-station Harbor integration | Exported public task data and host-owned immutable result evidence | Fixed inventory, hashes, sizes, and execution kind | Harbor integration, CLI E2E, verifier, and import gates | Asset-local integration contract |
| Harbor import extension | Fixed registry -> stewardship extension -> core TrialRecord builder | Harness import boundary | Host-side imported evidence | Fixed extension allowlist; unknown kinds fail closed | Import and Harbor TrialRecord gates | Existing boundary candidate |
| World execution and world provenance in `TrialRecord` | Verified direct or Harbor evidence -> builder -> TrialRecord reload | Shared TrialRecord contract | Append-only record with immutable artifact references | Additive current contract; strict nested validation | TrialRecord and Harbor parity gates | Repository contract |
| Stewardship metric vector, integrity gates, and terminal liability | Immutable run evidence -> evaluator -> evaluation result | Evaluation | Derived and recomputable; cannot change the run | Current evaluation schema; strict result reload | Evaluation unit, direct, Harbor, and reload gates | Repository contract with task-owned computation |
| SSC-03 lifecycle contracts | Existing lifecycle producers -> lifecycle host and verifier | Existing lifecycle and meta-harness owners | Existing checkpoint evidence | Frozen; stewardship does not reinterpret `COMPLETE` | Focused SSC-03 workflow gates | Existing repository contracts |
| Continuity-study manifest, plan, treatment record, reducer, and report | Frozen eligible TrialRecords -> ASW-4 study package | Study-local experiment package | Study-local immutable artifacts | Not implemented; ASW-4A must freeze v1 before use | ASW-4A provider-free fixtures | Conceptual |

## Promotion decisions

`Candidate` means “review again after ASW-4.” It does not mean “move now.”

| Abstraction family | Decision | Reason and next control |
| --- | --- | --- |
| Strict approved-station-data reader and package models | Retain-local | The schemas bind one certified pump-station profile and its claim ceiling. |
| Pump, wet-well, exposure, environment, resource, and observation models | Retain-local | These values express the reference asset and its physics. Similar field names in another asset are not reuse proof. |
| Physical clock advance, degradation, capacity, transfer, and intervention functions | Retain-local | The equations and limits are profile-specific. |
| Proposed-action types and proposal context | Retain-local | The closed action set is part of this world’s operating rules. |
| Operating approval policy and decision types | Retain-local | The policy encodes pump-station access, evidence, and resource rules. |
| Required follow-up, operating limits, work orders, and timed processes | Retain-local | Their meanings and state changes are domain rules, not general workflow values. |
| Scheduled events and event-selection rules | Retain-local | The event types and ordering are part of this physical world. |
| Transition state machine and receipt payload | Retain-local | Receipt fields bind this action, policy, event, and physical-state model. |
| Actor view, redaction, and information-set binding | Retain-local | The visible fields and hidden truth are task policy. Keep the shared host result small. |
| Handover projection and continuity-carrier values | Retain-local | These are the first study treatment surface. Freezing a generic API before the study would couple the study to an unproved contract. |
| Pump-station replay verifier | Retain-local | It must remain independent from the agent, host claim, and stored pass flag, but its rules are task-owned. |
| Pump-station serializer and content identities | Retain-local | The encoded unions and version checks are tied to local types. Reuse the canonical method, not these schemas. |
| Atomic immutable publication, retry, reconciliation, and current-pointer mechanic | Candidate | It crosses an unavoidable host storage boundary and survived ASW-3B attacks. A later stage must prove a second consumer or stable host need, define neutral inputs, preserve old bytes, and include rollback. |
| Pump-station durable artifact types and directory names | Retain-local | The publication mechanic can be reviewed without promoting task types or paths. |
| Pump-station direct session and closed tool catalogue | Retain-local | The shared request, result, and snapshot reference already form the stable host seam. |
| Pump-station Harbor exporter, controller, verifier, and importer policy | Retain-local | They bind this task package, tool set, and verifier. The core Harbor registry stays generic. |
| Pump-station evaluation function and metric derivation | Retain-local | Metric meaning and terminal liability are part of this study object. Shared result containers are already sufficient. |
| Study-local continuity schemas | Retain-local | ASW-4A must create and freeze them under the experiment surface. They are not core contracts. |
| A new shared `task_world_templates/stewardship/runtime/` package now | Abandon | There is no second task-world consumer, and ASW-3C does not allow extraction. |
| A generic public counterfactual branch API | Abandon | ASW-3 needs private containment only. A public API would freeze unused fields and visibility rules. |
| Reuse of lifecycle checkpoint state or `COMPLETE` as physical-world state | Abandon | A finite evidence lifecycle and a continuing asset have different time and completion meanings. |

No live abstraction has a blocking repair recommendation. The ASW-4 study must
not make the publication candidate generic. A later promotion stage can produce
a repair decision if its compatibility matrix finds a conflict.

## Candidate conditions

The atomic publication mechanic can move only if a later, separate stage proves
all of these conditions:

1. A second task-world uses the same transaction semantics, or the host boundary
   cannot stay safe without one neutral implementation.
2. Neutral inputs do not import pump-station actions, state, receipts, views,
   evaluation, adapters, CLI code, or study code.
3. Historical pump-station v1 artifacts still reload through their current
   owner.
4. The new contract has one producer, one consumer, one owner, and an explicit
   version.
5. Crash, retry, collision, confinement, and unknown-version gates pass at both
   the old and new boundary.
6. The stage has its own exact file allowlist and rollback path.
7. The change occurs after the ASW-4 programme checkpoint.

## Focused verification

This review uses focused gates. It does not run the repository-wide test suite.

| Gate | Command scope | Result |
| --- | --- | --- |
| Pump-station unit and contract | Selected package, physics, state, view, repository, version, contract, and evaluation tests | Pass: 139 |
| Pump-station integration | Selected package, direct-session, Harbor import, and TrialRecord tests | Pass: 27 |
| Pump-station E2E | Selected physical, stewardship, handover, attack, crash, installed-CLI, and local Harbor journeys | Pass: 57 |
| Legacy SSC-03 | The two test groups from `.github/workflows/ssc03-hydraulic-world.yml` | Pass: 109 and 574; two declared provider-construction tests skipped because `ANTHROPIC_API_KEY` was absent |
| Lint | Pump-station and directly crossed contract, harness, evaluation, Entrypoint, and test paths | Pass |
| Changed-file format | Whitespace and patch check for the exact ASW-3C allowlist | Pass |
| Strict types | Pump-station and directly crossed contract, harness, evaluation, and Entrypoint paths | Pass: 29 source files |
| File allowlist | Exact status and diff-name check against the frozen source | Pass: two approved paths |

The credential skips are expected in this provider-free stage. A direct rerun
showed one Bedrock client-construction pass and two Anthropic skips with the
explicit reason `ANTHROPIC_API_KEY not set`. No provider call was made.

A wider Ruff format diagnostic found existing format drift in
`agents/entrypoint_agent.py` and
`tests/task_world_templates/stewardship/wastewater_pump_station/test_pump_station_harbor.py`.
Those files are outside this stage. ASW-3C did not change them. GitHub issue 52
records the separate repair.

## Exit assessment

| Gate | Assessment |
| --- | --- |
| Dependency and import review | Pass |
| Complete contract register | Pass |
| Explicit disposition for each abstraction family | Pass |
| Promotion candidate has later controls | Pass |
| Shared extraction | Absent |
| Compatibility change | Absent |
| Study implementation or provider call | Absent |
| Focused pump-station and legacy checks | Pass |
| Exact file allowlist | Pass |
| ASW-3C | Pass |

ASW-4A can start after this record is merged. ASW-4A must remain provider-free.
