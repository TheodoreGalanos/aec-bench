# ABOUTME: Defines the ownership boundary and migration plan for continual task-world execution.
# ABOUTME: Separates reusable world-lifecycle machinery from task semantics and concrete profiles.

# Continual-World Runtime Boundary

| Field | Value |
| --- | --- |
| Status | Approved boundary and migration plan; implementation is not yet complete |
| Date | 2026-08-03 |
| First integration branch | `feat/asw-8-reference-system-implementation` |
| Reference implementation | Wastewater pump-station stewardship world |
| Second contract consumer | SSC-03 hydraulic interaction world |
| Merge rule | ASW-8 does not merge until every gate in this document passes |

This document corrects the runtime boundary exposed by the ASW-8 implementation.
It preserves the demonstrated pump-station behaviour and evidence. It does not
accept the parallel run, interface, rollout, agent, Harbor, replay, and
evaluation paths as the final architecture.

The correction is a controlled extraction and integration. It is not a
ground-up rewrite.

## 1. Governing rule

> The runtime manages how a world lives. The template defines what happens in
> that world. The profile selects one concrete starting situation.

The four ownership layers are:

| Layer | Owns | Must not own |
| --- | --- | --- |
| Continual-world runtime | Durable commands, immutable commits, snapshots, replay, recovery, idempotence, sessions, branches, rollout groups, and transport ports | Pump types, asset rules, task action names, task projections, or verifier targets |
| Stewardship capability | Obligations, work lifecycle, authority, evidence continuity, review, and governed intervention semantics | Filesystem publication, Harbor dispatch, provider selection, or generic branch storage |
| Pump-station task world | Pump physics, SCU rules, pump actions, event meaning, work generation, projections, and verifier logic | Main-agent dispatch, generic session storage, or generic rollout orchestration |
| RS1 profile | Opening state, event schedule, certified station package, temporal documents, and reference-controller objective | Runtime methods or alternate persistence rules |

## 2. Dependency boundary

The target dependency direction is:

```text
contracts
    |
    v
task_world_templates/continual
    |
    +---- task-owned world definition ports <---- pump station
    |                                      <---- SSC-03 hydraulic interaction
    |
    v
task_world_templates/continual_catalogue
    |
    +---- CLI
    +---- Harbor
    +---- agent execution
    +---- evaluation import
```

The shared runtime package must not import a concrete task world. A composition
root may import registered definitions and add them to the catalogue. Agents,
adapters, CLI commands, and Harbor dispatch consume the catalogue. They must
not branch on a task stage or profile name.

Shared boundary models remain under `src/aec_bench/contracts/`. The current
candidate target for reusable continual-world execution machinery is
`src/aec_bench/task_world_templates/continual/`. The two-consumer contract
tests must confirm that placement before promotion. Catalogue assembly remains
outside the core package so the core package has no pump or hydraulic import.

These paths are migration targets, not implemented public contracts. The
failing contract tests for both real consumers must confirm the smallest useful
boundary before a public runtime type, registry version, or migration API is
accepted.

## 3. Runtime contract

The continual-world runtime must provide these task-neutral operations:

- register a world and its supported profile versions;
- start, open, resume, inspect, snapshot, and verify a run;
- discover actor capabilities and return an actor-visible observation;
- invoke an actor action bound to the exact session, branch, snapshot, view,
  information set, and tenure;
- discover and invoke separate host-authorised controls;
- publish immutable commands, task receipts, states, and commits;
- recover an interrupted publication without repeating task effects;
- replay any selected immutable history through the registered task definition;
- create branches and rollout groups from an exact verified snapshot;
- preserve parent, child, and sibling isolation; and
- provide the same operation through direct Python, installed JSON, and Harbor.

A registered task definition supplies:

- profile validation and opening-state construction;
- state, command, receipt, and projection codecs;
- actor capability definitions and argument validation;
- actor observation and transition functions;
- host-control capability definitions and transition functions;
- replay-time task validation;
- task verification and semantic evaluation; and
- task-specific child treatment and inherited-evidence rules.

Task state stays opaque to the runtime. The runtime stores validated canonical
records and content identities. It does not inspect pump fields or calculate
task outcomes.

## 4. Promotion guard

Code is not promoted to the shared runtime because it appears reusable in one
template. Promotion requires:

1. a stable behaviour or boundary that both consumers require;
2. one failing contract test written before the extraction;
3. the pump-station implementation and one non-pump implementation;
4. no concrete task import in the shared package;
5. unchanged task-owned semantics and verifier results; and
6. an ownership and migration entry in this document.

The second consumer is the existing SSC-03 hydraulic interaction world. It
already has real source revisions, operations, snapshots, recovery, branches,
and verification. It must use its real kernel and records. A mock or a
pump-shaped demonstration does not satisfy this guard.

## 5. Current ASW-8 findings

The following corrections are already present in the ASW-8 branch and must be
preserved:

- the actor catalogue contains the v2 pump-station actions;
- the coupled repository inherits the existing local file lock;
- its generation publication flushes files and directories before atomic head
  replacement; and
- the real field-work action path calls the planned-outage admission rule.

The following boundary defects remain:

- a second run manifest, command chain, repository format, snapshot type, and
  replay function;
- v4 record constants that are not registered in the existing supported-version
  set or routed through the existing pump run;
- a combined local request that duplicates the separate actor and control
  envelopes;
- a second rollout runtime and rollout interface;
- a second agent session and Harbor bridge;
- a second verification and evaluation path; and
- direct ASW-8 branching in the main agent instead of registry dispatch.

These defects withhold architecture acceptance. They do not invalidate the
provider-free behaviour evidence already produced by the task world.

## 6. PR 74 ownership and disposition

Every changed PR 74 path is covered below. A grouped path applies to every file
that matches the stated pattern.

The audit accounts for all 97 changed files:

| Target owner | Files |
| --- | ---: |
| Shared continual-world runtime mechanics | 5 |
| Stewardship capability | 4 |
| Pump-station task semantics | 12 |
| RS1 profile | 7 |
| Transport and integration | 8 |
| Research-only | 47 |
| Test-only | 14 |
| **Total** | **97** |

### 6.1 Shared integration paths

| Current path | Owner | Disposition |
| --- | --- | --- |
| `agents/entrypoint_agent.py` | Agent transport | Replace task-stage branching with catalogue dispatch. Do not move task logic into the agent. |
| `src/aec_bench/cli/commands/pump_station_world.py` | CLI integration | Keep pump commands as thin aliases over continual-world actor and control operations. Resolve resume operations from immutable run metadata. |
| `src/aec_bench/harness/harbor_importing/stewardship.py` | Harness import | Keep the shared import envelope. Resolve the registered task verifier and recompute task evidence. |
| `tests/support/harbor_local_environment.py` | Test support | Keep only task-neutral Harbor setup. Move pump assertions to pump tests. |

### 6.2 Pump-station task semantics

| Current path | Owner | Disposition |
| --- | --- | --- |
| `actor_interface.py` | Pump-station task world | Keep v1 and v2 action catalogues and task argument validation. Invoke them through shared actor requests. |
| `physical_models.py` | Pump-station task world | Keep coupled physical records task-local. |
| `physical_kernel.py` | Pump-station task world | Keep coupled physical transitions and SCU accounting task-local. |
| `coupled_runtime.py` | Pump-station task world | Preserve its task semantics. Integrate them into stable policy, event, state-machine, and view modules. Do not promote pump records to the shared runtime. |
| `coupled_work.py` | Stewardship capability and pump task | Preserve work, pool, backlog, and generation rules. Integrate shared stewardship behaviour only after the second-consumer guard; keep pump rules task-local. |
| `coupled_world.py` | Pump-station policy | Move the outage-admission rule to the stable pump policy boundary and keep the real action-path call. |
| `coupled_temporal.py` | Pump-station temporal evidence | Integrate RS1 access into the existing temporal-evidence gateway and repository. |
| `stewardship_models.py` | Pump-station task world | Keep v4 task records and proposal types. Preserve v1-v3 decoding. |
| `stewardship_identity.py` | Pump-station task world | Keep profile-aware task content identity. Preserve historical hashes. |
| `temporal_evidence/corpus.py` | Pump-station task world | Keep the descriptor-selected RS1 builder and child public-corpus inheritance rules. |

### 6.3 Existing pump runtime paths to extend

| Current path | Owner | Disposition |
| --- | --- | --- |
| `world_run_models.py` | Pump adapter over continual runtime | Add the coherent v4 record set and manifest v2 without changing manifest v1. |
| `world_run_repository.py` | Pump adapter and extraction source | Keep as the authoritative durability path during extraction. Move only proven lock, publication, pointer, and recovery mechanics to the shared runtime. |
| `world_run_serialization.py` | Pump-station codec | Keep strict v1-v4 task codecs. Remove the state/projection profile collision. |
| `harbor_job.py` | Pump transport wrapper | Reduce to catalogue-driven Harbor dispatch after parity. |
| `reference_package_reader.py` | Pump-station package boundary | Extend the existing closed profile registry for v2. |
| `reference_package_reader_v2.py` | Duplicate package reader | Integrate required validation into `reference_package_reader.py`, then retire this file. |

The accepted design also requires changes to existing `world_run.py`,
`world_session.py`, `world_control.py`, `rollout_models.py`,
`rollout_repository.py`, `rollout_control.py`, `rollout_interface.py`,
`local_interface.py`, `harbor_export.py`, `harbor_session.py`,
`harbor_verifier.py`, `stewardship_policy.py`, `rich_work_processes.py`,
`stewardship_events.py`, `stewardship_state_machine.py`,
`stewardship_views.py`, `time_presentation.py`, and
`stewardship_verifier.py`. PR 74 currently bypasses most of these paths.

### 6.4 Parallel paths to integrate and retire

| Current path | Preserve | Final disposition |
| --- | --- | --- |
| `coupled_run.py` | V4 manifest bindings, command meaning, replay assertions, and durability tests | Route v4 through the existing run and shared durable engine, then retire the second run and generation store. |
| `coupled_interface.py` | Operation validation and negative cases | Express calls through separate shared actor and control envelopes, then retire the combined request. |
| `coupled_rollout.py` | V2 lineage, ancestor binding, temporal inheritance, and isolation checks | Move generic branch mechanics to the continual runtime and task treatment rules to the pump adapter, then retire the duplicate control. |
| `coupled_rollout_interface.py` | Strict v2 request and result validation | Add versioned records to the existing rollout interface, then retire this file. |
| `coupled_agent.py` | Pump tool descriptions and session behaviour | Supply them through the registered pump definition and shared session, then retire the second session. |
| `coupled_harbor.py` | RS1 controller, model tool loop, semantic evidence, and negative transport tests | Integrate task controller and verifier ports into the existing Harbor path, then retire the second bridge. |
| `coupled_evaluation.py` | Conservation derivation and semantic result checks | Integrate them into the task verifier and stewardship evaluation route, then retire the parallel evaluator. |
| `coupled_execution.py` | Deterministic RS1 reference journey | Keep as a task-owned reference controller under a behaviour-based name and invoke it through the registered world. |
| `coupled_runtime.py` | V4 task transitions, event ordering, and state projections | Split task rules across the existing pump policy, event, state-machine, and view modules, then retire the parallel runtime. |
| `coupled_temporal.py` | RS1 temporal setup, child inheritance, and action routing | Reuse the existing session, temporal repository, and gateway, then retire the duplicate temporal route. |
| `coupled_work.py` | Resource, backlog, work-generation, and priority rules | Move records and task rules to their stable pump and stewardship owners, then retire the parallel work module. |
| `coupled_world.py` | Planned-outage admission rule | Move the rule to the stable pump policy module, retain coverage through the real field-work action, then retire this file. |

No parallel file is removed before its behaviour is proven on the target path.

### 6.5 Profile artifacts

| Current path | Owner | Disposition |
| --- | --- | --- |
| `reference_packages/au-nsw-lh-syn-sps-v2/*.json` | Certified pump-station profile | Keep as immutable production package data. |
| `reference_system.py` | Pump-station profile registry | Keep task-local. Register the resulting world definition through the continual-world catalogue. |
| `reference_system/asw-8-rs1/*.json` | RS1 profile | Keep as immutable descriptor, opening-state, schedule, and temporal-template data. |

### 6.6 Tests

| Current path group | Owner | Disposition |
| --- | --- | --- |
| `test_asw_8_agent_session.py` | Actor-session contract | Rename by behaviour and run against the shared session. |
| `test_asw_8_coupled_physics.py` | Pump physics | Rename by behaviour and keep task-local. |
| `test_asw_8_harbor.py` | Harbor parity | Rename by behaviour and run through catalogue dispatch. |
| `test_asw_8_installed_interface.py` | Actor/control transport | Rename by behaviour and require separate envelopes. |
| `test_asw_8_operational_boundaries.py` | Pump policy and authority | Split only where ownership differs; keep real outage-path coverage. |
| `test_asw_8_persistence_and_evaluation.py` | Runtime durability and pump verification | Split into shared runtime contract tests and task verifier tests after both target paths exist. |
| `test_asw_8_reference_journey.py` | RS1 end-to-end journey | Rename by behaviour and retain as the final task E2E gate. |
| `test_asw_8_reference_package.py` | Package boundary | Rename by behaviour and keep task-local. |
| `test_asw_8_reference_system.py` | Profile binding | Rename by behaviour and keep task-local. |
| `test_asw_8_rollout.py` | Branch lineage and task inheritance | Split into shared branch tests and pump temporal-treatment tests. |
| `test_asw_8_rollout_interface.py` | Rollout transport | Rename by behaviour and run through the existing versioned rollout interface. |
| `test_asw_8_temporal_evidence.py` | Pump temporal evidence | Rename by behaviour and keep task-local. |
| `test_asw_8_work_system.py` | Work generation and outage admission | Rename by behaviour and keep task-local. |

Useful coverage is moved before any old test is removed. Permanent test names
describe behaviour, contracts, boundaries, or failure modes, not delivery
sequence.

### 6.7 Research and offline tooling

| Current path group | Owner | Disposition |
| --- | --- | --- |
| `research/asset-stewardship/asset-stewardship-worlds-prd.md` | Temporary programme record | Keep only until accepted decisions are represented in normative docs. It becomes ignored under the approved research cleanup. |
| `research/asset-stewardship/asw-8-reference-system-design.md` | Temporary design record | Add this correction amendment, then treat it as research after normative contracts and tests carry the accepted boundary. |
| `research/asset-stewardship/asw-8-reference-system/ara/**` | Research evidence | Preserve outside tracked production history under the approved research policy. |
| `research/asset-stewardship/asw-8-reference-system/results/**` | Generated run evidence | Remove from the final tracked diff. It is not a runtime dependency. |
| `research/asset-stewardship/asw-8-reference-system/build_reference_system_artifacts.py` | Research evidence builder | Keep outside production or retire after its required evidence is captured. Production must not import it. |
| `research/asset-stewardship/asw-8-reference-system/station-data-v2/generator.py` | Maintained offline profile tooling | Move to `scripts/asset_stewardship/station_data_v2/` with focused tests if regeneration remains required. |
| `research/asset-stewardship/asw-8-reference-system/station-data-v2/certifier.py` | Maintained independent certification tooling | Move beside the generator without importing its claim-critical decision path. Keep an independent rejection test. |
| `research/asset-stewardship/asw-8-reference-system/station-data-v2/promote.py` | Maintained offline promotion tooling | Move beside the generator and certifier. It may publish only independently certified exact bytes. |

In the current PR 74 branch, production, tests, agents, documentation, and CI do
not import or invoke the generator, certifier, promotion tool, or RS1 artifact
builder. The runtime uses only their promoted JSON outputs. If repeatable
generation or certification remains an accepted maintenance requirement, the
retained offline tools receive focused maintenance tests without becoming
runtime or agent dependencies. Otherwise, the promoted immutable package is
the required production input.

### 6.8 Step 2 definition and catalogue ownership

The Step 2 correction adds only the registration boundary. It does not add or
replace execution machinery.

| Path | Owner | Compatibility and migration rule |
| --- | --- | --- |
| `src/aec_bench/contracts/continual_world.py` | Shared boundary contracts | Keep content-pinned world, implementation, and profile references task-neutral. Do not add task state, action names, controls, clocks, paths, or verifier fields. |
| `src/aec_bench/task_world_templates/continual/definition.py` | Shared definition boundary | Load only an exact declared profile, pin each registered Python port, and leave its value task-owned and opaque. |
| `src/aec_bench/task_world_templates/continual/catalogue.py` | Shared catalogue | Resolve new work by exact world ID and recovery work by exact definition content. Import no concrete task world. |
| `src/aec_bench/task_world_templates/continual_catalogue.py` | Composition root | Register the pump and SSC-03 definitions. Concrete imports are allowed only at this boundary. |
| `wastewater_pump_station/continual_definition.py` | Pump-station task world | Validate the exact RS1 descriptor, certified station package, opening state, and loader source. Do not start a coupled or stable run here. |
| `lifecycles/ssc03_hydraulic_continual_definition.py` | SSC-03 task world | Register all four real variants and the existing lifecycle adapter. Pin the complete template, variant, baseline source, revised source, and adapter identity. Do not add another lifecycle run or repository. |

This change is additive. It does not change a run manifest, snapshot, command,
receipt, replay result, accepted artifact byte, CLI route, Harbor route, agent
route, or evaluation route. Existing pump and SSC-03 execution remains on its
current path. Later steps will store and resolve these references when the
durable engine and dispatch paths move behind the catalogue.

The pump registration includes RS1 and its v2 station package because Step 2
validates profile content only. It does not claim that the current stable pump
session can execute v4. That cutover belongs to Step 4. The SSC-03 registration
proves the same definition and profile boundary through its real materializer,
resolver, smoke environment, and verifier. It does not claim autonomous time,
named snapshot creation, arbitrary rewind, or rollout groups.

The loaded SSC-03 port exposes no mutable template, variant, or adapter object.
Each operation rechecks the exact definition implementation, profile content,
and supplied package variant before it delegates to the existing lifecycle
adapter.

Stable profile identity and compiled runtime-package identity are separate.
For SSC-03, the profile reference hashes the complete runtime-independent task
inputs. A compiled hydraulic package also records its Python runtime identity,
so its package hash must stay with the compiled run and must not become the
portable profile ID. The definition reference separately hashes the registered
adapter and loader sources. Recovery must later check all three identities:
profile, definition implementation, and compiled run package.

## 7. Implementation sequence

The correction uses small pull requests against the unmerged ASW-8 branch.
Each item starts from the updated ASW-8 branch after the prior correction is
merged.

1. Boundary amendment and complete ownership map.
2. Continual-world contracts and catalogue, proved by pump and SSC-03 consumers.
3. Mature durable engine extraction with legacy pump byte preservation.
4. V4 pump integration through the existing run, session, state machine, and verifier.
5. Separate actor and host-control interface integration.
6. Existing rollout path extension and generic branch orchestration.
7. Catalogue-driven CLI, Harbor, and agent execution.
8. Verification and evaluation integration, duplicate retirement, and research and test cleanup.
9. Requirement-by-requirement final merge audit.

The ASW-8 pull request remains draft until item 9 passes.

## 8. Final gates

ASW-8 can merge only when all these statements are true:

- one continual-world runtime owns durable publication, replay, recovery,
  sessions, branches, and rollout groups;
- the shared runtime imports no pump-station or hydraulic task type;
- the pump-station and SSC-03 worlds pass the same runtime contract tests;
- one pump run and repository path supports v1-v4;
- v1-v3 artifacts retain their exact accepted bytes and hashes;
- actor and host-control requests remain separate through direct, JSON, and
  Harbor execution;
- no task-stage branch remains in the main agent;
- ASW-8 resume and replay resolve the profile from immutable run metadata;
- parent, child, and sibling isolation pass;
- crash recovery cannot duplicate an actor or control effect;
- direct, installed JSON, Harbor, rollout-child, and imported evaluation agree
  on the normalized semantic outcome;
- the complete RS1 journey and all four conservation reports pass;
- the real outage-admission action path remains covered;
- no parallel run, interface, rollout, agent, Harbor, replay, or evaluation
  path remains; and
- generated research outputs and delivery-labelled tests are absent from the
  final tracked diff.

Targeted tests must prove each changed boundary during its correction pull
request. The final audit then runs the complete named integration gates for the
continual runtime and both registered worlds. A narrow unit result cannot prove
a broader merge gate.
