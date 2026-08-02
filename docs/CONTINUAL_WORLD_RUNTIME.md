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

### 6.9 Step 3A local lock ownership

The first durable-engine extraction moves only the host-local inter-process
lock. It is the smallest proven lifetime mechanic already used by both real
world implementations.

| Path | Owner | Compatibility and migration rule |
| --- | --- | --- |
| `src/aec_bench/ledger/local_lock.py` | Lower filesystem durability | Own trusted-root anchoring, confined relative-path traversal, a private regular lock file, and exclusive POSIX `flock`. Import no task or harness module. |
| `src/aec_bench/task_world_templates/continual/durability.py` | Shared continual-world durability | Re-export the lower lock primitive as part of the continual-world runtime boundary. Import no concrete task or harness module. |
| `wastewater_pump_station/world_run_repository.py` | Pump durability adapter | Keep `.world-run.lock`, translate shared lock failures to the existing pump error boundary, and keep every pump artifact, codec, commit, pointer, replay, and recovery rule task-local. |
| `meta_harness/evidence_lifecycle.py` | Shared evidence-lifecycle kernel | Use the lower primitive directly to keep the dependency direction downwards. Keep `.locks/lifecycle-state.lock`, translate lock failures to `EvidenceLifecycleError`, and keep lifecycle state, transaction, ledger, and recovery rules unchanged. SSC-03 remains one real consumer of this kernel. |

The shared lock is local to one POSIX host. It is not a distributed lock and
does not provide cross-host coordination. Each caller supplies a trusted run
root and a confined relative lock path. A relative root, including `.`, is
anchored once as an absolute path. The root's final component must be a real
directory, not a symbolic link. System path aliases above that root are valid.
Callers that used a symbolic link as the run root must supply its real target or
put the alias above the run root. Symbolic links and non-directory components
inside the root are not valid. The lock paths and mode `0600` stay unchanged.
Concurrent first callers must also serialize safely while the lock file is
created. One caller can create the file, and another must reopen and lock that
same regular file instead of failing startup.
Errors from work done while the lock is held keep their original type and
identity. No task artifact path or byte changes in this extraction.

Step 3 is not complete at this point. Immutable publication and confined reads
already have a generic implementation in `meta_harness/immutable_artifact_store.py`.
The next correction must resolve that implementation's lower-layer ownership
and reuse it rather than create a third byte store. Atomic current selection,
transaction publication, replay, and crash recovery remain on their existing
pump and SSC-03 paths until their shared raw-byte boundary is proved.

### 6.10 Step 3B immutable byte ownership

Step 3B extracts only exact immutable byte publication and reads. It proves
that this raw contract has two real consumers without moving task or lifecycle
policy into the lower layer.

| Path | Owner | Compatibility and migration rule |
| --- | --- | --- |
| `src/aec_bench/ledger/immutable_artifact_store.py` | Lower filesystem durability | Own trusted-root validation, descriptor-confined traversal, atomic first-writer publication, exact-byte reads, digests, private modes, and raw collision, confinement, and integrity errors. Import no meta-harness, task, or Pydantic module. |
| `src/aec_bench/task_world_templates/continual/durability.py` | Shared continual-world durability | Re-export the lower byte store and errors for task-world adapters. Keep the lower implementation as the single owner. |
| `src/aec_bench/meta_harness/immutable_artifact_store.py` | Meta-harness policy facade | Keep the public import path, Pydantic encoding, canonical model bytes, logical and content-addressed evidence rules, and `EvidenceRepository`. Delegate raw byte storage to the lower owner. |
| `wastewater_pump_station/world_run_repository.py` | Pump durability adapter | Use the continual-world byte interface and translate lower errors to the pump boundary. Keep pump codecs, state and content IDs, collection layout, `current.json` replacement, replay, and recovery in the pump adapter. |
| `src/aec_bench/meta_harness/evidence_lifecycle.py` | Shared evidence-lifecycle kernel and second consumer | Publish exact request and result bytes through the lower store and translate lower failures to the existing lifecycle conflict message. Keep lifecycle state, transactions, checkpoints, projections, replay, and recovery unchanged. SSC-03 uses this path through its real evidence lifecycle. |

The pump compatibility inventory records byte length and SHA-256 for the
artifacts produced before extraction. The v1 and v2 inventories keep the
`accepted-existing` status. The v3 inventory has the explicit
`pre-extraction-compatibility-baseline` status. It proves that Step 3B does not
change those bytes, but it does not give v3 a retroactive acceptance or
certification claim.

The raw store accepts only normalized relative paths. Each path component is
opened relative to a trusted directory descriptor, and each final artifact
must be a regular file. The current implementation requires a local POSIX
filesystem that supports directory-relative descriptor operations and
hard-link publication. This is a host-local filesystem contract. It is not an
object-store or cross-host durability claim.

The trusted root must not be changed by a malicious process that uses the same
operating-system account. The store supports cooperative local publishers. It
does not provide isolation from another process with the same account.

This extraction does not move mutable pointers, transaction publication,
replay, rewind, or crash recovery into the shared runtime. It also does not
change a task codec or define task-specific artifact collections. Those
boundaries stay with the pump and evidence-lifecycle owners until later Step 3
work proves a shared contract for each one.

### 6.11 Step 3C durable mutable byte replacement

Step 3C extracts only the atomic replacement of one mutable file with exact
bytes. It does not make a mutable file into a shared pointer or transaction
contract. The caller still owns what the file means and when it can change.

| Path | Owner | Compatibility and migration rule |
| --- | --- | --- |
| `src/aec_bench/ledger/durability.py` | Lower filesystem durability | Own unique sibling temporary creation, exact-byte writes, file flush, descriptor-relative replacement, final-byte verification, parent-directory flush, private mode, and raw confinement and integrity errors. Import no meta-harness or task module. |
| `src/aec_bench/task_world_templates/continual/durability.py` | Shared continual-world durability | Re-export the lower replacement function and errors for task-world adapters. Keep the lower implementation as the single owner. |
| `wastewater_pump_station/world_run_repository.py` | Pump durability adapter | Encode the existing canonical `current.json` bytes, request mode `0600`, and translate lower failures to pump errors. Keep the run lock, pointer schema, stale checks, commit selection, replay, and recovery in the pump adapter. |
| `src/aec_bench/meta_harness/evidence_request_store.py` | Evidence-lifecycle policy facade and second consumer | Keep sorted, indented JSON encoding with no final newline, then call the lower function directly and translate failures to `EvidenceLifecycleError`. Keep lifecycle transactions, commit-marker meaning, projections, ledger repair, replay, and recovery unchanged. SSC-03 uses this path through its real lifecycle run. |

The lower function accepts one existing trusted directory and one normalized
file name. It creates a unique sibling temporary file with exclusive creation,
keeps its descriptor and device and inode identity, writes and flushes all
bytes, rejects symbolic-link or non-regular destinations, replaces by directory
descriptor, verifies the final regular file and exact bytes, and then flushes
the parent directory. Cleanup removes a temporary name only when it still has
the identity created by that call. Host-private callers get mode `0600` even
under a restrictive process mask.

The final directory component must be a real directory. Trusted path aliases
above that component are allowed and select their physical directory. The
caller must therefore trust every supplied ancestor. When `host_private` is
false, the new file starts with mode `0666` filtered by the current process
mask. Replacement does not preserve the former destination's metadata.

The pump byte inventory remains unchanged. The lifecycle compatibility
inventory also fixes the pre-extraction length and SHA-256 of `state.json` and
the operation `committed.json` marker. JSON layout, whitespace, and final-newline
rules remain caller policy.

This is a local POSIX filesystem contract for cooperative processes that use
the same account and caller-owned lock. It is not a distributed transaction,
compare-and-swap pointer, rollback mechanism, or protection from a malicious
same-account process. The existing `ledger/durability.py` source was already in
the default kernel executor inventory, so this step adds no new executor source
path or operation-specific identity.

The raw function does not acquire a lock. The pump adapter owns its existing
run lock and the pump-specific selection policy described in Section 6.13.

An error after the descriptor-relative replacement has an unknown commit
result: the new bytes can already be visible even when later verification,
directory flush, or descriptor close fails. A caller must reload and reconcile
before retry. Process death before replacement can leave a unique hidden
temporary file. It is not authoritative, later writes ignore it, and Step 3C
has no scavenger. Process-death tests prove old-or-new atomic visibility. A real
power-loss guarantee also depends on the filesystem and storage honoring
`fsync`.

Step 3 remains incomplete after Step 3C. Shared pointer policy, transaction
publication, replay, recovery, sessions, branches, rollouts, CLI, and Harbor
behavior remain deferred until two real consumers prove the same task-neutral
contract.

### 6.12 Step 3D durable directory-tree creation

Step 3D extracts the last proven duplicate raw filesystem mechanic. It creates
each missing directory component, can apply an exact mode to each component
created by that call, and flushes every parent whose child entry changed. It
does not decide what a directory stores or how any stored record becomes
authoritative.

| Path | Owner | Compatibility and migration rule |
| --- | --- | --- |
| `src/aec_bench/ledger/durability.py` | Lower filesystem durability | Own missing-component discovery, optional mode application to newly created components, and parent-directory flushes. Preserve the default mode behavior for existing callers. |
| `src/aec_bench/task_world_templates/continual/durability.py` | Shared continual-world durability | Re-export the lower directory function for task-world adapters. Keep the lower implementation as the single owner. |
| `wastewater_pump_station/world_run_repository.py` | Pump durability adapter | Request mode `0700` for every newly created run-root component. Keep final-root validation, the existing-root mode policy, repository layout, and artifact meaning task-local. |
| SSC-03 lifecycle stores | Existing real lower-layer consumers | Continue to call the lower function with its default mode behavior. Keep lifecycle transaction paths, state, markers, adoption, and recovery unchanged. |

The optional created-directory mode does not change an existing ancestor. The
pump repository still applies its existing `0700` policy to the selected final
root, including when that root already exists. The extraction changes no pump
artifact path or byte and no SSC-03 transaction record.

This completes the controlled Step 3 extraction. No shared pointer,
transaction, replay, or recovery policy is promoted. The pump run selects a
commit through `current.json`; an unselected immutable commit has no live
effect. SSC-03 can adopt a valid lifecycle transaction into state and then
repair its commit marker. Pump replay follows parent commit identities from the
selected pointer, while SSC-03 replay follows state-owned actions through its
resolver. These are different task and lifecycle policies. Combining them now
would create a new abstraction without two proven consumers.

### 6.13 Pump staged publication lock ownership

Before V4 uses the existing pump repository, every path that selects a staged
transition must own the pump run lock. This is pump pointer policy. It is not a
shared pointer or transaction contract.

| Path | Owner | Compatibility and migration rule |
| --- | --- | --- |
| `wastewater_pump_station/world_run_repository.py` | Pump durability adapter | Make public `publish_staged_transition()` acquire `.world-run.lock` before it reads `current.json`, checks idempotence or staleness, validates immutable evidence, and replaces the pointer. Keep one private lock-required selection helper for callers that already own that lock. |
| `wastewater_pump_station/world_run.py` | Pump run coordinator | Keep one continuous lock across current-state read, request retry checks, transition evaluation, immutable staging, and pointer selection. Call the private lock-required helper to avoid a nested non-reentrant lock. |
| `src/aec_bench/ledger/` and `task_world_templates/continual/` | Lower durability | Make no change. Raw immutable publication and mutable byte replacement remain lock-free caller-owned mechanics. |

Two direct publishers prepared from one prior snapshot are serialized. The
first selected transition wins; the second receives `stale-publication`. An
exact retry is accepted only when the durable parent commit, staged commit, and
next snapshot form one consistent chain and both commit files are present with
their declared content identities. The receipt's pre-state and the actor or
control input's parent binding must pass the same rule used by full chain
replay. The returned transition is reloaded from that durable commit, not
trusted from the caller's staged object. A valid retry creates no new commit or
task effect. Process death before or after the pointer replacement releases the
operating-system lock. Reload and exact retry then select or recover the same
transition once.

This correction does not promote `current.json`, commit-chain meaning, replay,
or recovery into the shared continual-world layer. It only closes the pump
adapter path that Step 4 will reuse.

### 6.14 V4 registered opening state on the existing pump run

The first Step 4 slice moves only root creation and exact resume. It does not
move a V4 actor or host-control transition. The registered pump profile now
supplies the V2 station package, coupled model, and complete V4 stewardship
opening state. The profile still starts no run by itself.

| Path | Owner | Compatibility and migration rule |
| --- | --- | --- |
| `wastewater_pump_station/continual_definition.py` | Registered pump definition | Load the full specification-checked V4 opening state and coupled model. Pin both factories in the definition identity. |
| `wastewater_pump_station/world_run_models.py` | Pump durable records | Keep the manifest-v1 record exact. Add a separate required manifest-v2 record and the closed root-or-rollout initial-state source. Permit the coherent V4 record set only with manifest v2. |
| `wastewater_pump_station/world_run_serialization.py` | Pump task codec | Select manifest v1 and v2 through manifest-only codec profiles. Do not reuse a state or actor-projection profile. |
| `wastewater_pump_station/world_run.py` | Pump run coordinator | Create RS1 only through its content-pinned definition and profile. Resume it from those immutable references without a caller package, model, opening state, schedule, or feature override. Keep V4 mutations closed until the next slice routes the task-owned transitions. |
| `wastewater_pump_station/world_run_repository.py` | Pump durability adapter | Publish the normal immutable manifest, state, and initial commit. While the same pump run lock is held, complete required temporal setup before selecting `current.json`. Keep the commit and pointer formats unchanged. |

Manifest v2 binds the exact continual-world definition and profile, RS1
descriptor, opening-state specification, event schedule, temporal template,
V2 package, coupled model, realised temporal bundle, corpus, capability, and
initial-state source. Start resolves the current definition by task-world ID
through the composition catalogue. Resume resolves the content-pinned
definition and profile through the same catalogue and compares the complete
reconstructed manifest. A task-local definition factory alone is not a runtime
registration. Resume also reloads and independently verifies the stored
temporal repository. It never rebuilds a replacement corpus under an existing
selected run.

Manifest version, stewardship-state version, and actor-projection version are
independent axes. The codec must select each from its own record type. It must
not use one generic V4 profile to identify all three.

The run container keeps the physical model and complete state profile related
in its type. Bare legacy callers retain the V1-V3 model and state types. The
repository can decode either stored state profile, but a legacy consumer must
use its checked legacy-state accessor. That accessor rejects V4 before a state
can enter a legacy view, verifier, session, control, or rollout path.

Startup publishes the immutable pump records first, then publishes and
verifies the required temporal repository, and only then replaces
`current.json`. All three actions occur under one pump run lock. A process
failure before selection can leave exact immutable staged records, but it
cannot expose an actor-ready current snapshot. An exact retry reuses those
bytes, completes temporal verification, and selects one initial commit.

The free-form legacy `create()` path does not accept V4 inputs, and the legacy
caller-supplied `resume()` path rejects manifest v2. V1-V3 inventory lengths
and hashes remain unchanged. The parallel coupled run remains only as a
behaviour oracle until V4 transitions, replay, sessions, and verification have
parity on the existing path.

### 6.15 V4 transitions and replay on the existing pump run

Step 5 moves the V4 actor actions and the three root host controls onto the
existing pump commit chain. It does not add a second live pointer, a `HEAD`
file, or a generation store. The selected state remains the commit named by
`current.json`.

| Path | Owner | Compatibility and migration rule |
| --- | --- | --- |
| `wastewater_pump_station/world_run.py` | Pump run coordinator | Accept the shared actor request or the pump-bound root-control request. Bind each change to the selected run, episode, branch, sequence, state, and commit. Evaluate it with the model pinned in the run manifest. |
| `wastewater_pump_station/world_run_repository.py` | Pump durability adapter | Stage and select the V4 command, actor evidence when present, receipt, state, and commit under the existing run lock. Use the existing immutable stores, commit chain, and `current.json` pointer. |
| `wastewater_pump_station/world_run_models.py` | Pump durable records | Add separate V4 command and commit-v2 records. Do not change the V1-V3 command, commit, state, receipt, or inventory bytes. |
| `wastewater_pump_station/world_run_commands.py` | Pump command codec | Rebuild the shared actor request or typed root control from one strict command. Verify its content identity before selection and replay. |
| `wastewater_pump_station/stewardship_state_machine.py` | Pump task semantics | Convert a validated actor action to a typed proposal before mutation. Apply the operations review, process outcome, and common boundary as typed root controls. |
| `wastewater_pump_station/stewardship_verifier.py` | Pump replay verifier | Reload every selected V4 step and replay it from the registered opening state with the exact manifest-bound model. Compare the complete transition and final state. |

An actor action uses `WorldActorActionRequest`. Its binding names the exact
public view and information set for the selected commit. The run validates the
task, run, episode, branch, sequence, state, commit, actor, and view identities
before it applies the typed proposal. A root control uses
`PumpStationBoundControlRequest`. This separate envelope binds the control to
the same selected world identities without giving the actor access to the
host-control surface. The repository reloads the stored manifest and rejects a
caller manifest or command scope that differs from it. It also rebuilds the
command input and checks its content identity before it can select a state.

The V4 actor view identity covers every public view field. Staging and replay
rebuild the complete view and information set from the parent state, manifest
scope, actor tenure, and manifest-bound source artifacts. A command and a view
cannot define their own matching but foreign episode, branch, or evidence
scope.

Request identity is global across the legacy and V4 pump transition records.
An exact retry is found before the run checks whether the old base snapshot is
still current. The retry is accepted only when its complete command and parent
binding match the selected committed evidence. Reuse of the same request ID
with changed action, control, arguments, authority, or parent identity is a
conflict. Two real processes use the same run lock, so only one task effect can
be selected. If a complete immutable commit exists after a process stops
before pointer selection, an exact retry selects that stored transition. It
does not evaluate a new outcome for the same command.

Replay does not trust the live Python objects used during the first
transition. It reloads the durable command, proposal and information set when
present, receipt, state, and commit. It then rebuilds the transition from the
registered opening state. The replay uses the coupled model named by the
manifest. It does not load a default model that can drift from the run.
Replay captures the selected steps and final pointer under one run lock, then
performs the deterministic calculation after it releases the lock.

The V4 backlog bindings on inspection, obstruction clearance, and verification
do not enter V1-V3 storage. A legacy run rejects these fields before retry
lookup or transition evaluation. Accepted legacy proposals keep their exact
bytes and exact-retry meaning.

This slice keeps the existing coupled run only as a behaviour oracle. It is
not the live source of V4 state or selection. Session ownership and handover
remain for Step 6. Child physical treatment and rollout branches remain for
Step 7. Temporal search and fetch remain read-only evidence operations; they
do not create world-transition commits.

### 6.16 V4 session ownership on the existing separate interfaces

Step 6 reuses `PumpStationWorldSession`, `PumpStationWorldControl`, and
`PumpStationLocalInterfaceRequest`. It does not add another V4 session, a
combined actor/control request, or another live run pointer.

| Path | Owner | Compatibility and migration rule |
| --- | --- | --- |
| `wastewater_pump_station/world_session_activation.py` | Pump session adapter | Define immutable activation, claim, and active-pointer records for one exact run, branch, session, tenure, snapshot, view, information set, retrieval head, and host authority. |
| `wastewater_pump_station/world_run_repository.py` | Pump durability adapter | Publish session records and select one active binding under the existing run lock. An exact repeat returns the same binding. A changed or stale repeat fails closed. |
| `wastewater_pump_station/world_run.py` | Pump run coordinator and V4 verification orchestrator | Admit a V4 actor change only when its request, active session binding, and current session information set agree. Keep exact committed command validation idempotent after the originating session closes, while the actor session still requires active authority for a continuation view. Traverse the selected session chain, reconstruct each dynamic information set, and combine session, temporal, and task replay findings. |
| `wastewater_pump_station/world_session.py` | Existing pump actor session | Resume a registered V4 run from its stored manifest. Route V2 actor changes through the existing run and route temporal search and fetch through the existing temporal repository. |
| `wastewater_pump_station/temporal_evidence/` | Pump temporal evidence | Keep V1 records unchanged. Add an immutable V2 session information-set chain that binds each visible context to its activation, world snapshot, retrieval head, tools, sources, and prior binding. |
| `wastewater_pump_station/world_control.py` | Existing pump host control | Validate the configured host principal before session or root-control execution. Route the three typed V4 root controls through the existing run. |
| `wastewater_pump_station/local_interface.py` | Task-local request boundary | Accept `PumpStationBoundControlRequest` only in the existing control union. Do not add any root control to the actor catalogue or actor request surface. |
| `wastewater_pump_station/stewardship_views.py` | Pump projection and evidence models | Define the session-bound information set, dynamic visible context, actor-history entry, and structured handover content. Keep pump projection fields and handover meaning task-local. |
| `wastewater_pump_station/stewardship_verifier.py` | Pure pump transition replay verifier | Replay the V4 steps supplied by the run coordinator and compare each deterministic transition and final state. Do not load or reconstruct session evidence, select an active session, or perform evaluation import. |

One run branch has one active actor session binding. A session identifier and
tenure bind to one activation. Opening the same active binding is an exact
reattachment. A fresh session or tenure requires a host-authorised activation.
The host can install one durable structured handover before the recipient acts.
Selecting the new binding closes the old actor authority at the same world
snapshot. Activation and handover do not change world state, commit, sequence,
or time.

Each actor observation is published as an immutable session information-set
binding before it is returned. The binding names the exact world snapshot,
view, information set, temporal retrieval state, tools, sources, and prior
binding. Search, fetch, and handover can change this visible context without a
world transition. They therefore advance the session information-set chain but
do not create a world-transition commit.

Session publication can stop after the temporal binding is durable but before
the world session selector changes. Resume completes this exact staged binding
only when it is not present in the selected session history and its complete
context matches the recovered world, retrieval state, session, tenure, and host
authority. A binding already present in selected history belongs to a closed
session and cannot be selected again.

An actor world change is accepted only when its public binding matches the
selected session activation and current information-set binding. Actor action
and handover admission use the same run lock, with the temporal lock taken
inside it when required. An exact retry through the active session returns the
stored effect with the current continuation view. After replacement, the
closed actor session cannot make another interface call. The host run can
still validate the exact committed command without selecting another task
effect.

The actor and control authorities stay separate. The actor catalogue contains
only the V2 actor actions. The host-control surface contains session controls
and the operations review, process outcome, and common boundary controls. The
configured host principal must match the task authority carried by a root
control until a separate durable delegation contract exists. An exact root
control retry returns its original immutable transition result. A caller uses
the snapshot or progress operation when it needs the current world position.

Step 6 session-evidence verification is an admission and deterministic replay
integrity check. It proves that each selected actor transition used the durable
session evidence bound to that transition. It does not score task outcomes or
prove transport parity. Step 9 integrates the completed task verifier with
evaluation import, checks direct and transported outcomes, retires duplicate
paths, and runs the final merge audit.

This step does not change or certify CLI, Harbor, rollout, semantic evaluation,
duplicate retirement, or coupled-path deletion. Those changes remain in their
later sequence items.

## 7. Implementation sequence

The correction uses small pull requests against the unmerged ASW-8 branch.
Each item starts from the updated ASW-8 branch after the prior correction is
merged.

1. Boundary amendment and complete ownership map.
2. Continual-world contracts and catalogue, proved by pump and SSC-03 consumers.
3. Mature durable engine extraction with legacy pump byte preservation.
4. Registered V4 pump opening and exact resume through the existing run.
5. V4 pump transitions and replay through the existing run, state machine, and verifier.
6. V4 session ownership through the existing session and separate actor and host-control interfaces.
7. Existing rollout path extension and generic branch orchestration.
8. Catalogue-driven CLI, Harbor, and agent execution.
9. Verification and evaluation integration, duplicate retirement, research and test cleanup, and the requirement-by-requirement final merge audit.

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
