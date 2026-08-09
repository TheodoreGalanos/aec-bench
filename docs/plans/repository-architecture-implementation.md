# Repository Architecture Alignment Implementation Plan

| Field | Value |
| --- | --- |
| Class | Plan |
| Status | Historical |

## Purpose

This plan implements the accepted findings in the
[repository architecture study](repository-architecture-study.md) and its
independent review.

The work restores one-way ownership around concepts which already exist. It
does not introduce a new universal hierarchy.

The implementation starts from branch
`feat/repository-architecture-alignment` at commit
`f771467b7ed7a964e6e249d23fae8700cae2f7a8`, with the existing uncommitted
Prime refinement, pump journey, RS2, and architecture-study work preserved.

## Final ownership correction

The completed cutover made one correction to the earlier stage descriptions
in this historical plan:

- stormwater hydraulic calculations and verification stay under
  `lifecycles/stormwater_design/hydraulics` because this lifecycle is their
  only current benchmark owner;
- the finite hydraulic-review lifecycle is not registered as a causal world;
- `worlds` contains the registered wastewater pump-station environment; and
- maintained code uses descriptive `stormwater_design`, `hydraulic_review`,
  and `hydraulic_review_prime` names.

`SSC-03` remains only where it identifies source evidence or explains the
historical design sequence below. It is not a current package, runtime, world,
or Prime integration name.

## Accepted design

Use these terms consistently:

| Term | Primary meaning |
| --- | --- |
| Task | Objective, actor-visible inputs, allowed work, completion, and verification |
| Artifact task | A task bound to a staged workspace |
| Interactive task | A task bound to a causal world |
| World | Causal state, observations, actions, time, external events, host controls, and replay |
| Lifecycle | A finite ordered workflow of releases, operations, submissions, and checkpoints |
| Domain capability | A calculation, simulator, lookup, or bounded engineering operation |
| Adapter | A model execution strategy which satisfies the adapter request and result boundary |
| Provider | A concrete external model, compute, or vendor implementation |
| Harness | Provider-neutral orchestration of an execution and its evidence |
| Integration | Code which joins two concrete systems |
| Experiment | A benchmark plan or treatment comparison |
| `TrialRecord` | The canonical record of an eligible, finalised benchmark trial |

The implementation uses composition:

```text
task objective and verification
    + workspace, lifecycle, or world binding
    + optional domain capabilities
    + provider-neutral harness
    + concrete adapter/provider integration
    -> native evidence
    -> family-specific benchmark finalisation when eligible
```

## Rejected designs

Do not add:

- a universal `Calculation` base class;
- `Calculation -> Task -> World` inheritance;
- one universal runner for artifact, lifecycle, world, Prime, and refinement
  flows;
- a rule that every exploratory execution creates a `TrialRecord`;
- a general Prime-world journey inferred from the pump alone;
- a global `core`, `common`, `utils`, or unqualified `runtime` package;
- a dependency-injection container;
- function-local imports which hide owner cycles;
- empty service or repository layers for symmetry; or
- compatibility aliases for private, pre-1.0 Python import paths.

## Protected behavior

The migration must preserve:

- documented CLI command names and options;
- `TaskDefinition`, `EvaluationResult`, `CostRecord`, and `TrialRecord`
  semantics;
- artifact task staging, verifier, evaluation, and ledger behavior;
- Prime JSON batch behavior on `run-local`;
- the installed continual actor request and result JSON;
- separate actor and host-control authority;
- pump repository bytes, replay, stale-decision, and exact-retry behavior;
- lifecycle checkpoint, publication, recovery, and verification behavior;
- Prime isolation and evidence redaction;
- Prime, world, and benchmark evidence as separate authorities; and
- optional dependency isolation under a minimal installation.

Internal package paths, private helpers, local test fixtures, and unreleased
schemas are not compatibility boundaries. Update all repository callers and
delete obsolete paths.

## Completed protected cutover

Theo approved the following one-time changes to persisted or executable
identities:

1. Rename the static task-review fields in `RunBundle` and declared-stage
   artifacts. Existing local bundles must be regenerated. Do not add aliases or
   a converter.
2. Move the world and lifecycle source paths. Existing runs stay unchanged as
   historical evidence, but the new build cannot resume them under its new
   implementation identity.
3. Move fixed-kernel source paths and publish a new kernel identity. Existing
   bundles stay unchanged as historical evidence and cannot execute against
   the new kernel identity.
4. Do not rewrite old evidence or map an old identity to new source bytes.

The cutover also corrected the fixed-kernel closure from
`agents/entrypoint_agent.py`. The closure now includes the root `agents/`
package and declares dynamic executable module edges explicitly. Fixed K moved
once from `1.6.4` to `1.7.0`; old kernel identities fail closed.

## Implementation status

The alignment implementation is complete:

- the protected task-review persisted fields use their current names;
- adapter transcript contracts and the adapter/Prime dependency correction;
- minimal synthesis and hydraulic initialisers;
- pump-specific Prime composition under `harness/pump_station_prime`;
- neutral provider environment values and generic immutable ledger stores;
- non-kernel proposal coordination under `experimentation/proposals`;
- non-kernel governance under `experimentation/governance`;
- non-kernel qualification studies under `experimentation/qualification`;
- integrity interpretation under `evaluation`; and
- removal of unused evaluation-generation and governed-batch scaffolds, plus
  the unused `meta_harness/aecbench.py` binding;
- owner moves for engineering, worlds, lifecycles, harness, experimentation,
  evaluation, and ledger code;
- removal of the `meta_harness` and `task_world_templates` source umbrellas;
- fixed-kernel closure and the `1.7.0` identity cutover; and
- a concrete SSC-03 Prime lifecycle integration under `harness/hydraulic_review_prime`.

Deterministic SSC-03 process-boundary tests provide the delivery proof. A paid
live-model smoke test was not part of this architecture cutover and needs
separate authorisation.

## Target ownership

The target physical owners are:

```text
aec_bench/
    contracts/

    tasks/
    templates/
    generation/
    dataset/

    engineering/
        hydraulics/

    worlds/
        runtime/
        catalogue.py
        stewardship/
            wastewater_pump_station/

    lifecycles/
        runtime/
        catalogue.py
        compiled.py
        ssc03/

    adapters/
    providers/
    harness/
        pump_station_prime/

    prime_agent/
    prime_lab/

    evaluation/
    ledger/
    trajectory/
    feedback/
    communication/

    experimentation/
        proposals/
        lifecycle_studies/
        governance/
        qualification/

    evolution/
    remediation/
    synthesis/

    cli/
    tui/
    web/
```

This is an ownership map, not a demand for an empty package at every listed
level. Create only packages which receive current production code.

## Dependency rules

The final source graph must obey these rules:

| Owner | Can depend on | Cannot depend on |
| --- | --- | --- |
| `contracts` | standard library and validation libraries | AEC-Bench implementation packages |
| `engineering` | contracts and local domain values | harness, adapters, providers, CLI |
| `worlds.runtime` | contracts and neutral persistence values | concrete worlds, catalogue, providers |
| `lifecycles.runtime` | contracts and neutral persistence values | concrete lifecycle tasks, catalogue, providers |
| concrete tasks and worlds | contracts, their runtime, domain capabilities | adapters, Prime, Morph, CLI |
| adapters | execution contracts and provider-neutral clients | task semantics and ledger policy |
| providers | neutral provider contracts and vendor SDKs | concrete task and world semantics |
| harness | tasks, adapters, verification, evaluation, ledger, neutral provider values | concrete provider implementations |
| composition roots | both concrete sides which they wire | lower owners must not import the root back |
| evaluation | accepted evidence and contracts | providers and execution implementations |
| ledger | canonical records and storage values | scoring policy and providers |
| CLI, TUI, web | application services and read models | task semantics and metric authority |

## Stage 1: vocabulary and cheap dependency fixes

### 1.1 Rename the static review profile

Replace:

```text
contracts/task_world.py              -> contracts/task_review.py
evaluation/task_world.py             -> evaluation/task_review.py
TaskWorldProfile                     -> TaskReviewProfile
MaterializedTaskWorldRun             -> MaterializedTaskReview
world_id                              -> profile_id
world.json generation sidecar        -> task-review.json
```

Use `TaskReviewProfile`, not `ArtifactReviewProfile`, because the review
taxonomy is not yet proved to be artifact-only.

Update generation, evaluation, meta-harness review, tests, templates, and
current generated fixtures together. Do not retain old class or module aliases.

The approved persisted-format cutover uses these task-review names:

```text
WorldSnapshotRef                    -> TaskReviewSnapshotRef
TaskSnapshotRef.world               -> TaskSnapshotRef.task_review
world_id                            -> profile_id
world_envelope_sha256               -> review_profile_sha256
world_package_sha256                -> review_sidecar_sha256
topology_signature_sha256           -> declared_surface_sha256
DeclaredStageGraph.world_package_sha256
                                    -> review_sidecar_sha256
StageExecutionReceipt.world_package_sha256
                                    -> review_sidecar_sha256
```

Existing local bundles and declared-stage receipts must be regenerated. There
is no alias or converter. Old evidence remains unchanged as historical
evidence.

### 1.2 Make package initialisers minimal

- Remove eager implementation exports from `synthesis/__init__.py`.
- Remove eager implementation exports from the hydraulic package initialiser.
- Update callers to import public functions from their defining modules.
- Prove that importing neutral packages does not import optional model or
  provider SDKs.

### 1.3 Move adapter transcript values

Move adapter transcript enums and value models from
`adapters/transcript.py` to `contracts/adapter_execution.py`.

Both adapters and Prime event parsing depend on this contract. The concrete
Prime adapter can depend on `prime_agent`; `prime_agent` must not depend on
`adapters`.

### 1.4 Add architecture fitness tests

Extend the standard-library AST checks to:

- enforce the accepted owner import matrix;
- reject unexplained strongly connected owner packages;
- reject concrete-world imports from shared runtimes;
- reject imports of catalogues by their registered implementations;
- reject optional SDK imports from neutral packages; and
- import selected public modules under the minimal dependency set.

Composition-root modules are allowed to import both sides. Lower owners cannot
import those roots.

### Stage 1 proof

- focused contract, generation, evaluation, synthesis, hydraulic, adapter, and
  Prime event tests;
- package ownership and minimal-import tests;
- Ruff and mypy on changed paths; and
- an AST graph with the adapter/Prime cycle removed.

## Stage 2: world, engineering, and lifecycle ownership

### 2.1 Move deterministic hydraulics

Move `task_world_templates/hydraulics` to `lifecycles/stormwater_design/hydraulics`.

Keep source data, calculations, bounded operation requests, materialised
packages, verification, and current CLI behavior together. It remains usable
without a model or world runtime.

Two current files are lifecycle resolvers, not pure hydraulic capability code:

```text
task_world_templates/hydraulics/operations.py
    -> lifecycles/stormwater_design/operations.py

task_world_templates/hydraulics/intervention_operations.py
    -> lifecycles/stormwater_design/intervention_operations.py
```

They move with SSC-03 because they depend on lifecycle state, budgets, and
operation recovery. Hydraulic calculations, packages, and verification stay in
`lifecycles/stormwater_design/hydraulics`.

### 2.2 Move the neutral continual runtime

Move `task_world_templates/continual` to `worlds/runtime`.

Move the external catalogue to `worlds/catalogue.py`. The runtime must not
import the catalogue or a concrete world. Concrete world implementations must
not call the external catalogue back.

Merge the two current catalogue modules into that one composition root. Delete
`continual/durability.py`; its callers can use the existing ledger durability
and lock values directly.

### 2.3 Pump-world owner

The pump world lives at `worlds/stewardship/wastewater_pump_station`.

Preserve task-owned state, action meaning, host controls, persistence, replay,
verification, evaluation, RS1, and RS2.

### 2.4 Extract lifecycle ownership

Create `lifecycles/runtime` for:

- checkpoint host and progression;
- request and result boundaries;
- lifecycle state and persistence;
- conditional evidence publication;
- operation protocols and stores;
- exact operation recovery; and
- task-neutral JSONL persistence used by the runtime.

Move `build_evidence_lifecycle_task_run_resolver` to
`harness/lifecycle_task_run.py`. It adapts task execution to the lifecycle; it
is not lifecycle progression.

Keep provider execution, calibration, ablation, transfer studies, session-record
analysis, and `TrialRecord` finalisation outside the runtime. They coordinate or
interpret lifecycle evidence; they are not lifecycle progression.

Move the concrete SSC-03 definitions to `lifecycles/stormwater_design`. Add
`lifecycles/catalogue.py` as the composition root.

Move the SSC-03 hydraulic operation resolvers with the lifecycle. The pure
hydraulic calculations and package verifier remain in
`lifecycles/stormwater_design/hydraulics`. Inject the concrete operation resolver into the
runtime. The runtime must not import the lifecycle catalogue.

Move lifecycle ablation, calibration, transfer, and treatment comparison to
`experimentation/lifecycle_studies` when they are not runtime behavior.

Move lifecycle metrics and verification-result values to
`evaluation/lifecycle.py`. The lifecycle runtime must not import an experiment
package. Move `evidence_lifecycle_local.py` to `harness/lifecycle_local.py`
because it creates adapters and model sessions.

Move `task_world_templates/compiled_world.py` to `lifecycles/compiled.py` and
use lifecycle-specific Python names. Preserve the existing serialized Harbor
filenames and fields, including `compiled-world-envelope.json`,
`compiled-world-export.json`, and `world_id`. These are retained execution
evidence even though the Python owner changes.

Do not move `meta_harness/world_process.py` or
`meta_harness/world_runtime.py` into `worlds`. Their current use of “world” is
an older task-operation process, not a causal world.

### 2.5 Delete `task_world_templates`

Delete the old package only after all source, tests, CLI, docs, build hashing,
and import paths use their new owners. Do not keep forwarding modules.

### Stage 2 proof

- world-runtime and both real world conformance tests;
- lifecycle checkpoint, operation, recovery, calibration, and trial-finaliser
  tests;
- pump repository byte and replay comparison before and after the move;
- hydraulic package and verifier tests;
- CLI task-world and lifecycle tests; and
- package ownership graph with no lifecycle/meta-harness or catalogue/world
  cycle.

Moving a concrete world changes its Python entry point and source-tree build
digest. Before the move, choose and document one explicit cutover for existing
persisted runs. Do not report the new build as byte-identical to the old build.
The causal repository and replay formats must remain unchanged.

## Stage 3: Prime, provider, and harness integration ownership

### 3.1 Move pump-specific Prime composition

Keep these generic Prime concerns in `prime_agent`:

- process launch;
- JSON batch mode;
- ACP protocol;
- event parsing;
- process isolation;
- session evidence and accounting; and
- refinement change capture.

Move pump-specific session, journey, trajectory treatment, and journey evidence
to `harness/pump_station_prime`.

Do not create a generic world journey in this stage.

### 3.2 Separate provider-neutral harness from Morph

Move provider-neutral runtime dependency values and environment request values
to a contract owner which imports neither harness nor Morph.

Make Morph implement the neutral boundary. Move concrete Harbor-plus-Morph
wiring to one outer composition module. `harness` must not import Morph
implementation modules, and Morph implementation modules must not own harness
policy.

Use small values, callables, or protocols. Do not add a dependency-injection
framework.

### 3.3 Keep the Harbor entry point bounded

Keep `agents/entrypoint_agent.py` as an external composition root. Move
substantial family-specific behavior to its owner and leave only validated
dispatch at the root.

### Stage 3 proof

- Prime batch and ACP tests;
- pump Prime session, journey, evidence, replay, and refinement tests;
- Harbor artifact and pump-world tests;
- Morph provider boundary tests; and
- import graph with no harness/provider or adapter/Prime reciprocal owner
  relationship.

## Stage 4: higher-order ownership

### 4.1 Consolidate proposal execution

Move proposal contracts, compilation, session execution, evidence,
qualification, Harbor integration, and Morph integration into one bounded
context under `experimentation/proposals`.

The package can use ordinary harness and provider ports. Ordinary harness and
provider packages must not import proposal policy back.

### 4.2 Classify the remaining meta-harness code

Move each current family to one real owner:

- proposal execution;
- lifecycle studies;
- treatment comparison and qualification;
- monitors;
- governance;
- adaptive program compilation; or
- maintained research experiments.

Use these current owners:

- proposal creation, freeze, compilation, dispatch, execution, import, and
  proposal-specific Morph code → `experimentation/proposals`;
- lifecycle ablation, calibration, transfer, evaluation, session analysis,
  and finalisation → `experimentation/lifecycle_studies`;
- authority, promotion, monitors, critic lifecycle, kernel change authority,
  and assured motif storage → `experimentation/governance`;
- adaptive, factorial, repair, transfer, motif-learning, RunBundle, and Prime
  refinement studies → `experimentation/qualification`;
- phase-neutral compilation, governed execution, declared-stage execution,
  Harbor lowering, and model execution → bounded subpackages under `harness`;
- pure logic-profile and integrity interpretation → `evaluation`; and
- generic process logs and immutable stores → `ledger`.

Apply these concrete corrections during the protected fixed-kernel cutover:

- move `logic_profile.py` to `evaluation`;
- keep `llm_reviewer.py` with harness model execution because it invokes an
  adapter and PydanticAI;
- keep `task_snapshot.py` with harness compilation and lowering, not proposal
  studies;
- move `applicability.py`, `authority_ledger.py`, `authority_validation/`,
  `motifs/`, and `standing_monitors/` to governance;
- move `decomposition_problem_view.py`, `program_proposal_compilation/`,
  `proposal_freezing/`, and `structural_generalization_corpus.py` to proposals;
- move compilation, declared-stage, program-execution, governed-attempt,
  kernel, budget, contract, and Harbor-lowering code to bounded harness
  packages;
- move the remaining RunBundle and adaptive-corpus studies to qualification;
- extract `TaskGenerationIdentity` from `adaptive_cycle_corpus.py` to a neutral
  contract before proposal code imports it; and
- delete `meta_harness/aecbench.py` and its isolated test because no current
  product caller, command, document, or protected artifact uses it.

Do these moves as one fixed-kernel identity cutover after the final target paths
are stable. Do not publish a series of intermediate kernel identities.

Move proposal-specific modules out of both `harness` and `providers` with the
proposal bounded context. Split proposal-only dispatch and import behavior from
generic Harbor functions. Use one injected evidence finaliser at the generic
Harbor import boundary instead of task or proposal branches.

Moving fixed-kernel source paths changes executable kernel identity. Preserve
old proposal and study artifacts unchanged as historical evidence, but fail
closed if the new implementation is asked to execute an old kernel identity.
Do not rewrite old manifests or map old identities to new source paths.

Delete production code with no current product capability, caller, supported
interface, or protected artifact need.

### 4.3 Remove `meta_harness`

Delete the old package after every current caller moves. Keep the public
`aec-bench meta-harness` command name unless a separate public behavior change
is approved. The command can compose the new higher-order owners.

### Stage 4 proof

- proposal compilation, dispatch, execution, import, qualification, monitor,
  governance, repair, and lifecycle-study tests;
- CLI meta-harness tests;
- no `aec_bench.meta_harness` import or source path; and
- import graph with higher-order code depending on ordinary execution in one
  direction only.

## Stage 5: second Prime task and proven extraction

Use SSC-03 as the second Prime integration if its existing lifecycle actor
surface can be exposed without host paths, verifier data, hidden evidence, or
a new world protocol.

The selected seam is the existing fresh-context `LifecycleEpisodeEnvironment`.
`run_evidence_lifecycle` remains the only checkpoint coordinator. Each active
checkpoint gets one fresh Prime ACP session and one lifecycle-specific scoped
endpoint under `harness/hydraulic_review_prime`. Do not add an SSC-03 journey.

The endpoint can list and read actor-visible lifecycle files, execute one
declared operation, and accept one proposed checkpoint submission. It privately
owns the package, run, checkpoint, session, resolver, socket, and capability.
It accepts no package, run, profile, build, branch, checkpoint, verifier,
evaluation, or host-control selector. Prime cannot submit or advance the
lifecycle. After a clean Prime end turn, the existing lifecycle host validates
and archives the proposed submission, then releases the next checkpoint.

Use a dedicated `ssc03_lifecycle` client and skill. Do not reuse
`ContinualWorldActorRequest` or `aec-world`: SSC-03 is a finite lifecycle, not a
causal world. Prime end state, checkpoint state, lifecycle state, verification,
and benchmark validity remain separate. Limits and usage cover the complete
lifecycle and do not reset at each checkpoint.

Implement one concrete `SSC-03 + Prime` composition first. Preserve:

- Prime process and ACP evidence;
- lifecycle native evidence;
- task-owned hydraulic operation evidence;
- task-owned verification; and
- benchmark finalisation as a separate optional step.

Compare the pump and SSC-03 integrations for:

- process and ACP lifecycle;
- actor transport and isolation;
- limits and usage accounting;
- cancellation and failure handling;
- recovery and exact resume;
- session completion versus task completion; and
- safe evidence aggregation.

The only shared correction required before the SSC-03 implementation is an
explicit scoped-socket argument on the generic ACP runner. Generic Prime code
must not inspect a pump-specific environment variable. Compare both concrete
endpoints before extracting any shared socket framing, capability, cleanup,
redaction, or logging mechanics.

Extract shared code only where both integrations have the same owner and
semantics. Keep task actions, host controls, completion, verification, and
evaluation outside the shared Prime-world code.

Reject an extraction which needs `if world_type == ...` branches.

### Stage 5 proof

- focused SSC-03 Prime unit and process-boundary tests;
- one authorised live smoke test after deterministic proof passes;
- retained Prime and lifecycle evidence with no hidden-state leakage;
- comparison with the pump path; and
- no task-specific branch in any extracted shared runtime.

## Stage 6: final deletion and audit

- Remove obsolete private packages, modules, tests, exports, comments, and
  documentation.
- Update `ARCHITECTURE.md`, `CONTRACTS.md`, `PROJECT_STRUCTURE.md`, world and
  lifecycle authoring guides, runtime protocols, and the root README.
- Keep the repository study as dated evidence. Record accepted architecture in
  current authorities.
- Add a lightweight architecture-audit procedure for major execution,
  provider, world, or evidence changes and for periodic review.
- Recompute the import graph from the final source tree.
- Require zero unexplained reciprocal owner relationships.

## Completion audit

The work is complete only when current evidence proves all of these:

1. `world` has one primary causal meaning in current contracts and docs.
2. No `TaskWorldProfile`, `MaterializedTaskWorldRun`, or static artifact
   `world.json` sidecar remains.
3. `task_world_templates` and `meta_harness` no longer exist.
4. Hydraulics, world runtime, pump stewardship, and lifecycle runtime have
   separate owners.
5. Shared runtimes import no concrete definitions or catalogues.
6. `prime_agent` imports no adapter implementation and contains no pump
   semantics.
7. Neutral harness code imports no Morph implementation.
8. Proposal execution has one owner and does not create a harness cycle.
9. Optional runtimes do not load during neutral package imports.
10. All documented protected commands and evidence formats still work.
11. Pump replay and lifecycle recovery retain their exact semantics.
12. SSC-03 supplies the second real Prime integration before any shared journey
    extraction.
13. Every new dependency rule has a focused failing-then-passing architecture
    test.
14. Targeted boundary tests, Ruff, formatting, mypy, build checks, and the final
    import graph pass.

The default verification remains targeted during implementation. Run broader
checks only at the changed boundary and at the final package/build audit.
