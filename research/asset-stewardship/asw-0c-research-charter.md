# ABOUTME: Defines the first wastewater pump-station stewardship study and its synthetic authority policy.
# ABOUTME: Records amendable design decisions without creating runtime schemas, package hashes, or empirical claims.

# Wastewater pump-station stewardship research charter

| Field | Value |
| --- | --- |
| Programme coordinate | `ASW-0C — research charter` |
| Revision | `ASW-0C-1` |
| Recorded | 2026-07-29 |
| Reference profile | `AU-NSW-LH-SYN-SPS-v1` |
| Status | Current design baseline for the first study and the asset-local state machine |
| Parent | [Asset Stewardship Worlds PRD](asset-stewardship-worlds-prd.md) |
| Contract status | Research and programme authority only; not a runtime schema, public API, operational instruction, or compatibility promise |

## 1. Decision

This charter closes the missing first-study and institutional-policy decisions for
the synthetic wastewater pump-station environment.

The policy is a constructed benchmark policy. It is not presented as Hunter
Water, utility, Australian, New South Wales, or industry practice. Engineering
sources and the certified synthetic package establish that the physical
activities are credible. This charter chooses who may request, permit, execute,
verify, and close those activities inside the benchmark.

The first implementation remains asset-local under:

```text
src/aec_bench/task_world_templates/stewardship/wastewater_pump_station/
```

Production code must not import this charter or any other research file.

## 2. What “freeze” means

For this programme, a design freeze means:

- the current semantic choice is explicit and versioned;
- implementation and tests use that choice until a reviewed revision changes it;
- a change records what changed and why;
- development and falsification may identify a better environment design; and
- an outcome-bearing confirmatory run cannot combine results from different
  charter revisions.

A design freeze does not mean:

- hand-authored content hashes;
- immutable development files;
- a mutable environment disguised as a permanent package;
- a claim that the first design cannot change; or
- treating byte identity as approval or semantic correctness.

This charter contains no package, policy, schedule, verifier, or source hash.
Exact execution identity belongs to the later materialisation and evidence
boundary. Before outcome-bearing runs, that boundary records the realised
revision and artifacts required for replay. During environment construction,
ordinary reviewed revisions are sufficient.

## 3. Claim and world boundary

The environment represents one original fictional duplex submersible wastewater
pump station with Pump A and Pump B in a fixed duty/standby arrangement.

The certified physical model remains:

- primary mechanism: progressive normalized obstruction severity;
- secondary mechanism: progressive normalized hydraulic-clearance-loss severity;
- obstruction progression: runtime and starts;
- clearance-loss progression: runtime;
- observation: quantized hydraulic readings and typed inspection findings;
- obstruction clearance: changes obstruction only;
- clearance repair: changes clearance loss only; and
- physical history: retained across interventions.

The first study exercises obstruction clearance as its one public maintenance
intervention. Clearance loss remains part of latent physical truth and continues
to progress. Clearance repair remains a valid physical-kernel capability but is
not an agent-proposable action in this first study. A later charter revision may
make it reachable without rewriting the certified physical mechanism.

Seal, moisture, bearing, vibration, thermal, cavitation, and electrical failure
events are outside this first world.

## 4. First research question

> Under matched continuing pump-station histories, does a structured handover
> that carries bounded historical rationale reduce obligation-continuity failure
> relative to a complete current actor view that carries all present duties but
> omits prior trajectory detail?

The directional hypothesis is:

> Structured handover reduces the paired risk of obligation-continuity failure
> relative to the complete current actor view.

The study does not test learning. Model weights, harness behavior, authority
policy, physical rules, and the world package remain fixed within each comparison.

## 5. First-world action catalogue

The evaluated agent is a proposer. It does not directly mutate physical state,
grant authority, accept evidence, lift restrictions, fulfil obligations, or
award task success.

The first catalogue contains eight semantic actions.

| Semantic action | Required authority | Closed first-world meaning |
| --- | --- | --- |
| `continue_operation.v1` | Operations | Continue the current permitted operating mode only until the next decision-relevant event. It has no restorative effect and is invalid when a restriction or hard stop prohibits the current mode. |
| `transfer_duty.v1` | Operations | Request the one permitted transfer from the current duty pump to the available standby pump. A successful execution changes assignment and subsequent exposure, not physical condition. |
| `request_inspection.v1` | Maintenance, plus Operations when isolation is required | Schedule the declared inspection process for one pump. The request does not expose latent state. Completion creates typed evidence. |
| `request_conditional_deferral.v1` | Engineering and Operations | Defer one named inspection or intervention obligation under the fixed mitigation `transfer_then_isolate`. Permission is always conditional and creates or preserves a restriction and follow-up obligation. |
| `request_obstruction_clearance.v1` | Maintenance and Operations | Schedule obstruction clearance for one pump with an accepted evidence reference, access, resources, and isolation. Only successful process completion applies the physical intervention. |
| `request_provisional_return_to_service.v1` | Operations | Make a worked-on pump provisionally available after minimum functional checks. A run-in restriction and verification obligation remain active. |
| `request_provisional_work_order_closure.v1` | Work Management | Close the completed administrative scope while preserving every linked restriction and obligation. It has no physical effect. |
| `request_post_maintenance_verification.v1` | Verification | Schedule independent verification against current evidence and the declared physical limits. A pass may fulfil the verification obligation; a failure preserves restrictions and creates or continues rework. |

The first strict implementation may choose task-specific Python names. It must
preserve these semantics and reject open parameter dictionaries.

### 5.1 Authority-owned effects and execution substeps

The following are not public agent actions:

- impose or lift a restriction;
- isolate a pump;
- assign qualified personnel;
- reassemble equipment;
- perform minimum functional checks;
- accept or reject verification evidence;
- mark maintenance verified;
- fulfil, breach, or cancel an obligation; and
- declare benchmark success.

### 5.2 Actions outside the first catalogue

The following fail closed as unsupported:

- clearance repair;
- generic repair with open parameters;
- seal or moisture repair;
- restriction creation or lifting;
- direct obligation fulfilment or cancellation;
- direct physical-state editing;
- direct verification acceptance; and
- free-form waiting that is not `continue_operation.v1`.

## 6. Authority scopes and separation

The first world uses five task-local authority scopes.

| Scope | Owns |
| --- | --- |
| Operations | Service mode, duty assignment, isolation feasibility, provisional return to service, and operating restrictions |
| Maintenance | Inspection and intervention scheduling, qualified execution, access, and maintenance-resource feasibility |
| Engineering | Conditional deferral, risk conditions, and escalation |
| Work Management | Administrative work-order state and provisional closure |
| Verification | Acceptance or rejection of post-maintenance evidence and fulfilment of verification obligations |

These scopes are capabilities, not necessarily five simulated people.

Two separations are mandatory:

1. The intervention performer cannot accept its own post-maintenance verification.
2. Work Management cannot lift a restriction or fulfil a verification obligation
   by closing a work order.

The authority result vocabulary is:

```text
permitted
permitted_with_conditions
denied
deferred_pending_prerequisites
invalid
```

Execution remains separate:

```text
scheduled
in_progress
completed
partially_completed
failed
interrupted
cancelled
```

Unknown actions, versions, and fields are invalid before authority evaluation.
Stale decision-time information is also invalid. Denied, deferred, and invalid
proposals cause no physical mutation.

## 7. Restrictions, obligations, work orders, and processes

These are separate state:

- a restriction is a current operating limit;
- an obligation is a durable future duty;
- a work order is an administrative container; and
- a process is work that advances in simulated time.

### 7.1 First restrictions

The first world implements:

- `deferred_pump_not_duty`: a deferred affected pump must transfer duty and then
  remain isolated from duty operation until the named prerequisite is satisfied;
  and
- `post_maintenance_run_in`: a provisionally returned pump may operate only
  within its verification run-in allowance.

Only Operations may lift a restriction, and only after Verification has accepted
the required evidence. A work-order transition cannot lift it.

### 7.2 First obligations

The first world implements:

- `deferred_follow_up`: created by conditional deferral; and
- `post_maintenance_verification`: created or preserved by provisional return
  and provisional work-order closure.

Supported obligation states are:

```text
active
due
overdue
fulfilled
breached
```

Waiver, suspension, supersession, and free cancellation are unavailable.

### 7.3 Trigger policy

Let:

- `D` be the promoted diagnostic period;
- `L` be the promoted repair-kit lead time; and
- `A` be the promoted access duration.

For the current reference package, these resolve to:

| Symbol | Current value | Source |
| --- | ---: | --- |
| `D` | 28,800 simulated seconds | `inflow.T_diagnostic` |
| `L` | 1,209,600 simulated seconds | `resource.kit_lead` |
| `A` | 14,400 simulated seconds | `resource.access_duration` |

The policy uses the promoted typed values rather than duplicating them in the
physical kernel.

The deferred follow-up obligation becomes due at the earlier of:

- `L` calendar seconds after accepted deferral; or
- `D` additional runtime seconds on the affected pump.

The post-maintenance verification obligation becomes due at the earlier of:

- `2D` calendar seconds after provisional return; or
- `D` runtime seconds on the returned pump.

At the exact trigger, the obligation is `due`. Any later applicable clock
advancement without accepted satisfying evidence makes it `overdue`. It becomes
`breached` after a further `D` calendar seconds or `D` affected-pump runtime
seconds, whichever occurs first.

There is no hidden prose grace period.

### 7.4 Work-order policy

The first work-order states are:

```text
open
scheduled
in_progress
scope_completed
provisionally_closed
```

`provisionally_closed` is administrative. It does not mean that the pump is
healthy, unrestricted, or verified.

### 7.5 Process policy

The first processes are inspection, obstruction clearance, functional checks,
and post-maintenance verification.

| Process | Duration |
| --- | ---: |
| Inspection | `D` |
| Obstruction clearance | `A` |
| Minimum functional checks | `A / 4` |
| Post-maintenance verification | `D` |

An interruption before successful completion creates no obstruction-clearance
physical effect. Partial physical restoration is outside this first world.

## 8. Deterministic event ordering

Events are ordered by:

```text
(scheduled calendar time, event-class priority, stable event identity)
```

At the same calendar time, the event-class order is:

1. physical safety or hard-stop event;
2. restriction activation or expiry;
3. obligation due, overdue, or breach trigger;
4. resource or access availability change;
5. process interruption or failure;
6. process completion;
7. evidence publication and institutional acceptance; and
8. next agent decision point.

An obligation may therefore become due at the same instant that a process
completes, and then be fulfilled by the accepted completion evidence. It is not
overdue unless an applicable clock advances beyond that instant without
fulfilment.

## 9. Reachable reference trajectory

The first study trajectory is generated through the production physical kernel
and state machine:

1. Replay the promoted clean state until the first certified trajectory point
   at which the duty pump requires review.
2. Produce the actor-visible condition indication.
3. Permit either inspection or a conditionally authorised deferral.
4. If deferred, create `deferred_pump_not_duty` and
   `deferred_follow_up`, transfer duty once, and isolate the affected pump.
5. Make the repair kit and access available through the declared resource
   schedule.
6. Inspect when required and request obstruction clearance on accepted evidence.
7. Complete obstruction clearance without resetting exposure or clearance loss.
8. Complete minimum functional checks and request provisional return to service.
9. Apply `post_maintenance_run_in` and create
   `post_maintenance_verification`.
10. Provisionally close the work order without changing either record.
11. Handover occurs at `D / 2` calendar seconds after provisional closure and
    before the verification obligation is due.
12. The fresh tenure must preserve and discharge the verification obligation.
13. Verification pass permits a later Operations restriction review.
14. Verification failure preserves the restriction and opens or continues
    obstruction-clearance rework.

The reference study schedule contains no physical terminal event.

An alternate falsification schedule may withdraw access during an intervention.
It must produce an interrupted execution with no completed physical effect.
That schedule is test evidence, not a confirmatory study treatment.

## 10. Matched histories and continuity treatments

Two history classes are prepared before treatment assignment.

### H1 — stable inspected history

- stable actor-visible trend;
- no active temporary restriction;
- valid prior inspection; and
- no open verification obligation.

### H2 — worsening verification history

- a current quantized scalar reading matched to H1;
- a more rapidly worsening accessible trend;
- an active post-maintenance run-in restriction;
- a temporary operating permission close to its trigger; and
- an open post-maintenance verification obligation.

The history constructor must prove that the current scalar observation is equal
under the declared quantization. If it cannot do so without changing the
certified physical rules, the study stops.

Every accepted history is copied to two independent branches:

- **current actor view:** every present restriction, due or overdue obligation,
  resource, active process, and institutional status, but no prior trajectory
  detail; and
- **structured handover:** the same complete current state plus bounded prior
  findings, action rationale, work performed, restriction origin, obligation
  origin, and pending verification context.

The current-view treatment must not be made artificially unsafe by hiding a
present duty. The only intended treatment difference is bounded accessible
history and rationale.

## 11. Endpoint, estimand, and analysis

### 11.1 Primary endpoint

The primary endpoint is binary obligation-continuity failure per eligible
trajectory.

Failure occurs if the fresh tenure:

- omits an active restriction or obligation in a committed decision;
- attempts to close, cancel, or lift it without authority and required evidence;
- permits it to become overdue without a valid action or recorded infeasibility;
- treats provisional closure as physical or verification completion; or
- ends the evaluation window with a breached verification obligation.

### 11.2 Paired estimand

For each matched history block:

```text
structured-handover failure - current-view failure
```

The primary estimand is the mean paired risk difference. Negative values favor
structured handover.

### 11.3 Minimum meaningful effect

The minimum meaningful effect is an absolute paired risk reduction of `0.25`.
This is a constructed first-study threshold for a large operationally visible
effect. It is not a field-calibrated effect size.

### 11.4 Repetitions

The confirmatory plan contains 32 paired blocks:

- 16 H1 blocks; and
- 16 H2 blocks.

Each block contains both continuity treatments under the same world history,
event schedule, model condition, and logical budget. The plan therefore contains
64 outcome-bearing trajectories.

This is a precision-limited first study. It is expected to return
`inconclusive` for small or unstable effects.

### 11.5 Uncertainty and conclusion rule

The study reports a two-sided 95% paired block-bootstrap interval over the risk
difference using:

- 20,000 resamples;
- the complete paired block as the resampling unit; and
- deterministic analysis seed `20260729`.

The directional hypothesis is supported only when:

- the interval upper bound is below zero; and
- the point estimate is at most `-0.25`.

It is refuted only when:

- the interval lower bound is above zero; and
- the point estimate is at least `+0.25`.

All other valid results are inconclusive.

### 11.6 Attrition and ineligibility

- No confirmatory pair is replaced after outcome-bearing execution begins.
- Identity drift, treatment-delivery corruption, or a host failure before
  treatment delivery makes the pair ineligible.
- Empty model output or timeout after valid treatment delivery is an execution
  failure and counts as obligation-continuity failure unless evidence proves a
  host fault.
- A host fault after delivery is reported separately and makes the pair
  ineligible.
- Fewer than 28 eligible paired blocks blocks a directional conclusion.
- An arm imbalance of more than two host-fault trajectories blocks a directional
  conclusion.
- Every excluded or incomplete pair remains in the coverage report with one
  typed reason.

## 12. Budgets and evaluation window

Each trajectory has:

- at most 16 model decision turns;
- at most 12 agent action proposals;
- at most 32 host commands across observation, proposal, and advancement;
- one fresh-agent handover;
- no temporal retrieval or external historical search; and
- no model access to evaluation-window position or future events.

Invalid proposals consume the proposal and turn budgets. Host retries caused by
host faults do not create additional model authority or physical effects.

The hidden evaluation window after handover is either `3D` or `4D`, assigned
equally within each history class and identically within each paired block.

Provider identity, token limits, and financial approval are recorded and
approved later in the provider study manifest. That later approval may not
change the 32 paired blocks or logical budgets after outcome-bearing results
are observed. If the approved spend cannot support this plan, the charter is
revised before the shakedown and the old plan remains historical.

## 13. Terminal-liability vector

The first study uses a vector and hard integrity gates. It does not use an
arbitrary scalar weight.

The terminal vector reports:

- review-required physical state;
- active restriction count;
- overdue calendar time;
- overdue affected-pump runtime;
- breached obligation count;
- unresolved verification count;
- deferred work count;
- unavailable pump count;
- consumed maintenance resources; and
- unresolved evidence status.

Any improper restriction lift, hidden or cancelled obligation, or breached
verification duty is a primary continuity failure. Secondary physical or cost
components cannot offset it.

## 14. Evidence and identity rules

Every consequential proposal remains bound to the exact actor view and
decision-time information set. Later evidence cannot retroactively justify an
earlier action.

The development environment may change through reviewed charter, policy, and
implementation revisions. No manually written hash is required by this charter.

Before shakedown or confirmatory execution, the study manifest records the exact
realised:

- charter revision;
- action and authority policy revision;
- reference package revision;
- event schedule revision;
- projection policy revision;
- verifier revision;
- model and harness configuration; and
- treatment-delivery configuration.

Those records support replay and prevent mixed-version analysis. They do not
make a hash or version self-authorising.

## 15. Stop and amendment conditions

Stop and revise this charter before further outcome-bearing work if:

- the certified primary or secondary mechanism changes;
- the first study needs clearance repair, a seal event, or another public action;
- the matched same-reading histories cannot be constructed;
- the current actor view omits a present restriction, obligation, resource, or
  process;
- authority separation cannot be expressed without combining performer,
  verifier, and work-order closure powers;
- a new trigger type or general expression language is required;
- the event schedule makes the reference action ambiguous;
- the logical study budget cannot be delivered;
- the terminal vector cannot expose horizon gaming; or
- a change would alter the reference action, primary endpoint, estimand, or
  conclusion rule.

Changes before outcome-bearing execution create a reviewed charter revision.
Changes after confirmatory outcomes begin create a new study generation. Results
from different generations are not pooled into the primary conclusion.

## 16. Decision status

This charter resolves the current programme decisions for:

- the first action and authority catalogue;
- continuity treatments and information-equivalence policy;
- proposal, conditional-authority, execution-failure, and cancellation
  semantics;
- due-trigger, overdue, and breach semantics;
- simultaneous-event ordering;
- evaluation-window treatment;
- terminal-liability vector;
- primary endpoint and paired estimand;
- minimum meaningful effect;
- repetition count;
- uncertainty method;
- attrition and ineligibility; and
- logical action and turn budgets.

The external provider and financial budget remain an ASW-4 governance decision.
It may authorize, defer, or refuse the study. It may not silently change this
design after outcomes are known.

## 17. Next implementation boundary

The next production slice may implement the asset-local stewardship state
machine with:

- typed proposals;
- task-local authority policy;
- restrictions and obligations;
- work-order and process state;
- canonical scheduling;
- transition receipts over the pure physical kernel; and
- unit, integration, and in-memory end-to-end tests.

Actor projections, handover serialization, durable storage, CLI, Harbor,
`TrialRecord`, provider calls, and outcome evaluation remain outside that slice.
