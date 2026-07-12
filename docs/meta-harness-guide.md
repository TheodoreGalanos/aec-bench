# Meta-Harness Guide

The meta-harness layer turns task prose, task-world profiles, run evidence, operation plans, and governance decisions into an explicit process. It lives inside the AEC-Bench library under `aec_bench.meta_harness`.

Runnable example artifacts live under `docs/examples/meta-harness/`. The CLI tests exercise those files so the examples stay aligned with the public command contracts.

## Boundaries

The layer follows existing AEC-Bench ownership boundaries:

- `contracts` still define task-world shapes such as `TaskWorldProfile`;
- `evaluation` still materialises run evidence and owns the LLM reviewer artifact contract;
- `harness` still owns Harbor execution and import;
- `meta_harness` coordinates world logic, operation profiles, governance, autonomy, and process ledgers;
- CLI commands only parse inputs and call library functions.

The important invariant is that agents propose and harness-owned code applies or records. Operation proposals are not hidden mutations.

## Main Modules

- `aec_bench.meta_harness.logic_profile` evaluates closure, construction, containment, review, and event candidates against evidence.
- `aec_bench.meta_harness.operation_profile` applies projection, difference, subset, and product operations when declared handles make them deterministic.
- `aec_bench.meta_harness.operation_orchestrator` builds the agentic operation-planning environment and executes validated plans.
- `aec_bench.meta_harness.world_process` builds problem-brief, world-generation, and governance packets.
- `aec_bench.meta_harness.world_runtime` runs the pauseable prose-to-world process.
- `aec_bench.meta_harness.autonomy` supervises bounded autonomous iterations with score, stagnation, cost, and governance gates.
- `aec_bench.meta_harness.harbor` binds generic Harbor-compatible subprocess commands to task-run evidence.
- `aec_bench.meta_harness.aecbench` binds runtime task-run resolvers to `SynchronousHarborWorkflow` and Harbor trial import.
- `aec_bench.meta_harness.model_runner` parses model endpoints and runs structured PydanticAI intake, world, review, and operation stages.
- `aec_bench.meta_harness.evidence_lifecycle` owns staged evidence release, immutable checkpoint submissions, revisits, branches, and durable attempt lineage.
- `aec_bench.meta_harness.evidence_lifecycle_episode` defines the verifier-independent request/result boundary between the lifecycle host and an episode environment.
- `aec_bench.meta_harness.evidence_lifecycle_local` runs one lifecycle through either a persistent model conversation or fresh checkpoint contexts.
- `aec_bench.meta_harness.evidence_lifecycle_metrics` compares task-extracted semantic atoms across checkpoints without changing verifier reward.
- `aec_bench.meta_harness.evidence_lifecycle_experiment` binds code, package, model configuration, prompts, tools, trajectories, metrics, and verification into an indexed experiment record.
- `aec_bench.meta_harness.lifecycle_operation_protocol` defines the generic source-bound operation call and observable-state identity.
- `aec_bench.meta_harness.lifecycle_operation_store` publishes immutable operation transactions and their smaller model-visible projections.

## Evidence Lifecycles

An evidence lifecycle is one evolving task run inside one task world. Evidence is released in declared checkpoint order; each structurally valid submission is archived before the host releases the next packet. A revisit reads an immutable earlier checkpoint without changing active state. Changing an earlier submission creates a derived branch from that checkpoint rather than mutating the parent run.

`lifecycle-run-local` supports two baseline execution conditions:

- `persistent` uses one model conversation across all checkpoints with `persistent_context` visibility;
- `fresh-context` creates one model context per checkpoint and defaults to `artifact_memory`, where earlier submissions remain model-visible.

Two additional fresh-context policies define later ablations without deleting audit artifacts:

- `raw_evidence_only` exposes cumulative released evidence but hides prior submissions;
- `current_release_only` exposes only the active release and active instruction.

The host workspace tool enforces visibility. All released evidence, archived submissions, trajectories, and conversations remain on disk for audit regardless of the model-visible policy.

### Action-conditioned evidence

A checkpoint may optionally declare a public conditional-evidence catalogue: bounded request IDs, descriptions, prerequisites, and a finite budget. Every declared request must remain reachable: its transitive prerequisites plus the request itself must fit within that budget. The public contract contains no release path or expected outcome. A task-owned `hidden/evidence-request-resolutions.json` manifest maps those IDs to confined package directories, and the host exposes the catalogue at `workspace/checkpoints/<checkpoint-id>/evidence-requests.json`.

Action-capable packages add one model-visible tool:

```text
request_evidence(checkpoint_id, request_id, reason)
```

The host supplies session and attempt identity. A first valid unique request consumes one budget unit and publishes only its selected packet under `workspace/inbox/<checkpoint-id>/requests/<request-id>/`. A repeated successful request returns `already_released` without another charge. Typed rejections for inactive checkpoints, unknown IDs, unmet prerequisites, exhausted budgets, or unsupported checkpoints release nothing and consume zero; responses do not enumerate valid alternatives or hidden mappings.

Each boundary-valid request becomes a lock-serialized canonical transaction under `run/evidence_requests/<action-id>/` before its model-visible projection and state commit. The record binds outcome, reason, session/attempt ownership, pre/post observable-state hashes, budget arithmetic, and artifact hashes. Malformed or blank tool arguments return a bounded error without creating a lifecycle action; they remain visible in the ordinary tool trajectory. Recovery adopts an identically published transaction exactly once, repairs missing ledger entries, and fails closed on conflicting bytes. Acquired evidence and consumed budget survive retry and are inherited by a branch through its branch point.

Fresh episode requests bind the current public catalogue and hashes of previously acquired conditional evidence. Persistent local, fresh-context, and local Prime execution expose the same three public arguments. Packages without a conditional catalogue retain their previous tool set. Invocation manifests bind the versioned action protocol and exact tool schema; immutable snapshots include canonical transactions, catalogues, and workspace projections. See the [SSC-03 richer interaction roadmap](ssc03-richer-interaction-roadmap.md) for the hydraulic and holdout progression.

### Action-conditioned calculations

An operation-capable checkpoint declares a separate public catalogue of source activation and calculation operations. The model calls `execute_operation(checkpoint_id, operation_id, visible_source_state_sha256, reason)`. The host supplies session and attempt identity, resolves the selected ID against the task-owned package, and never accepts arbitrary source values or hidden paths from the model.

Operation inputs and prerequisites determine whether a prior result is still current. A matching result is returned as `already_current`, consumes zero budget, and points to its canonical originating action. A stale prerequisite is rejected without publishing a result. A new calculation consumes one budget unit and publishes only the artifacts declared for that operation; the complete PR18 hydraulic run remains host-only.

Every boundary-valid call becomes a canonical transaction before its workspace projection and lifecycle-state commit. The transaction binds the source fingerprints, input projection, prerequisite action IDs, artifact hashes, budget arithmetic, session and attempt, and observable state before and after the action. Recovery can adopt an identical durable transaction and repair missing derived state, but it fails closed on conflicting bytes.

The public SSC-03 interaction family uses these operations for two scenarios across a baseline, one declared revision, and closeout. Four revisions exercise an administrative no-op, a major-event rainfall change, an outlet-geometry change, and a tailwater change. The task verifier checks the resulting selective recomputation and document lineage independently of action efficiency. See [the interactive hydraulic lifecycle guide](ssc03-interactive-hydraulic-lifecycle.md).

### Sealed external lifecycles

A private holdout lifecycle is supplied by one explicit `SealedLifecycleProvider` instance rather than another registry. The host writes a generic `holdout` receipt, binds the provider to the exact package path and hash, and resolves its operation logic and task verifier only while the package-scoped mount is active. Copying the package or leaving the mount context removes that authority; a new process must explicitly bind the provider again.

Public template, lifecycle, and variant listings never consult the mount. Prime export and the normal full-fidelity experiment/`TrialRecord` paths reject sealed packages before copying prompts, paths, verifier identity, or package files. Provider exceptions become stable redacted codes. The private provider remains task authority only: the host still owns session identity, checkpoint transitions, verifier invocation, verifier-result validation, and reward. See [the sealed holdout boundary guide](ssc03-sealed-holdout-boundary.md).

### Typed episode boundary

Fresh-context execution crosses a strict `LifecycleEpisodeEnvironment` boundary. Before execution, the host validates the released checkpoint, gives the environment a chance to seal interrupted artifacts, allocates the session and attempt IDs, and constructs a content-bound `LifecycleEpisodeRequest`. The environment durably prepares its empty attempt artifacts; the host then publishes `episode_request.json`, records its SHA-256 in the active attempt, and only then calls `execute`. This ordering leaves recoverable identity even if the process stops in the narrow publication-to-execution window. The request carries lifecycle/package hashes, checkpoint ownership, the exact workspace and submission paths, execution mode, visibility policy, requested adapter/model identity, per-session turn limit, completed-checkpoint lineage, the public conditional-evidence catalogue when present, and hashes of conditional evidence acquired by earlier attempts. Version 3 also binds the current source, the active operation catalogue when one exists, and every operation artifact visible under the selected memory policy. Closeout can retain the current source and earlier visible artifacts without offering an operation catalogue. Recovery reconstructs the expected request from current state and declared environment configuration; finalization reconciles the request hash and stable identity against the immutable snapshot.

The environment returns a `LifecycleEpisodeResult` containing only execution identity, requested and resolved adapter/model identity, configuration, status, failure details, and token usage. Extra fields are rejected, so an adapter cannot return task-owned gates, pass/fail, or reward through the episode seam. The host requires request/result identity to match exactly and publishes a host-validated `episode_result.json` for every returned result or synthesized execution failure. Exceptions, returned failures, identity drift, and missing or invalid submissions close the active attempt as failed and cannot advance the lifecycle. A candidate submission left by a failed attempt is moved under that attempt's session directory and hash-bound as audit evidence; a retry must create its own candidate.

`run_evidence_lifecycle` deliberately accepts only `fresh_context` episode environments: one environment call owns one checkpoint. The persistent runner remains a distinct one-session orchestration because it releases later checkpoints inside the same model conversation. This distinction is part of the benchmark condition, not an implementation shortcut.

### Local Prime lifecycle boundary

The local Prime lifecycle export exposes the persistent condition through a Verifiers `StatefulToolEnv`. One rollout owns the complete lifecycle and one model conversation. The adapter references existing materialized public packages by absolute path, binds their lifecycle-spec and package hashes, binds the exact local AEC-Bench source provenance, and reuses the host lifecycle workspace and control tools. Conditional packages receive the matching session-bound `request_evidence` and `execute_operation` capabilities. Selected packages must agree separately on whether each capability exists, so one exported environment cannot hide a tool-schema mismatch. The adapter does not copy the packages or move checkpoint, visibility, operation, evidence-request, submission, or revisit authority into Prime.

The task-owned lifecycle verifier remains the only reward authority and runs only after terminal completion. Incomplete rollouts close their active attempt and receive zero reward. This export is a local execution boundary, not evidence of hosted publication or training, a fresh-context comparison, transfer, or continual learning. See the [Prime Lab integration guide](prime-lab-guide.md) for the export and loading commands.

### Controlled SSC-03 variants

SSC-03 exposes a small public calibration family through a task-specific event contract. Every variant starts from the same stale-manifest packet and keeps the same three checkpoint IDs. The host selects the event sequence at materialization; callers cannot patch arbitrary files or supply expected answers.

| Variant | Response event | Closeout event | Intended pressure |
| --- | --- | --- | --- |
| `staged_full_correction` | corrected manifest, rerun, and report | propagated memo | canonical acquisition and closeout |
| `semantic_no_op_release` | unregistered administrative runtime notice | complete corrected chain | retention under irrelevant evidence |
| `response_assertion_only` | unregistered correction assertion without artifacts | complete corrected chain | assertion is not closure evidence |
| `memo_closeout_missing` | corrected manifest, rerun, and report | memo assertion without memo | unresolved evidence must remain not ready |

List or materialize the public variants through the existing task-world surface:

```bash
aec-bench --json task composite-template list-lifecycle-variants \
  drainage-model-evidence-lifecycle-review

aec-bench --json task composite-template materialize-lifecycle \
  drainage-model-evidence-lifecycle-review \
  --variant response_assertion_only \
  --output lifecycle-package
```

Omitting `--variant` selects `staged_full_correction` and preserves the canonical agent-visible instructions and release bytes. Materialization requires an empty output directory so evidence from an earlier package cannot survive into another variant. The validated variant identity and existing adaptation lineage are stored in `hidden/variant.json`; the package hash, lifecycle experiment manifest, and append-only experiment index bind that identity. Variant IDs are not written into model-visible instructions or releases.

Runtime notices are model-visible observations, but they are explicitly not registered project sources and are not added to cumulative `evidence_refs`. This keeps the no-op checkpoint semantically unchanged while still testing whether the reviewer invents an engineering update from irrelevant prose.

Packages materialized before variant identity was introduced do not contain `hidden/variant.json` and are intentionally rejected rather than assigned an inferred label. Rematerialize them from the registered template; the default variant preserves the earlier canonical model-visible bytes.

These committed variants are public calibration cases, not private holdouts. True holdout evidence must remain structurally separate and outside the public repository.

### Lifecycle ablation sweeps

The lifecycle ablation runner expands one strict manifest across:

```text
public variant × valid execution/visibility condition × agent × repetition
```

The four valid conditions are the persistent conversation with `persistent_context`, plus fresh checkpoint contexts with `artifact_memory`, `raw_evidence_only`, or `current_release_only`. Invalid mode/policy combinations are rejected instead of entering a larger meaningless Cartesian product.

This release is a **descriptive calibration sweep**, not a randomized causal ablation. Its required `study_design` contract records that the turn budget is per session, execution follows deterministic sequential plan order, trials are neither randomized nor counterbalanced, and causal effects are unsupported. Persistent trials normally use one session. Every fresh-context session owns exactly one checkpoint; a retry opens another attempt-specific session rather than reusing context across checkpoints. Total configured turn capacity is therefore not held constant. Group means locate hypotheses; they do not identify effects of context or memory policy.

Preview an exact plan without materializing persistent packages, writing ledgers, or calling a provider:

```bash
aec-bench --json meta-harness lifecycle-ablation \
  --config docs/examples/meta-harness/lifecycle-ablation.example.yaml \
  --dry-run
```

The preview classifies every trial as `pending`, `resumable`, `finalizable`, `complete`, or `conflict` using the same persisted-manifest, package, deterministic gold/verifier smoke, runtime-lineage, snapshot, and record checks as execution. Planning and smoke validation materialize each missing variant only in temporary directories so task package/spec hashes can enter the trial identity without changing the requested output tree.

Run or resume the same manifest by omitting `--dry-run`. Trial IDs are full SHA-256 identities over every experimental dimension, materialized task revision, registered scorer, and declared aec-bench source inventory. The runner persists the normalized manifest and expanded plan, rejects code, task, configuration, or storage-contract drift on resume, materializes each public variant once, and runs a deterministic package/gold/verifier smoke gate before any model call. Execution is deliberately sequential in this version.

Each lifecycle invocation retains its task-owned manifest, metrics, verification, sessions, and checkpoint state. Finalization then:

1. resolves the canonical invocation through its per-invocation sealed index entry, ignores abandoned dot-prefixed staging directories, validates every declared run artifact, package file, session, attempt owner, execution mode, visibility policy, per-session turn limit, requested and actual adapter identity, token total, verifier result, and plan field, and repairs a missing or truncated shared discovery index from canonical seals under an inter-process lock;
2. snapshots only the hash-declared package/run files, canonical invocation and seal, normalized index entry, sweep manifest, and expanded plan under `ledger/<experiment>/_artifacts/<trial-id>/`;
3. rebuilds and validates the record from staged immutable bytes rather than mutable working paths;
4. fsyncs every staged file, directory, and newly created ancestor before atomically publishing the snapshot and one typed core `TrialRecord`; and
5. recovers a validated snapshot left before record publication without calling the model again.

The lifecycle invocation UUID is audit evidence, not a competing sweep identity. Cross-run discovery and resume use the current content-bound plan; historical aggregate evaluation uses the plan referenced by the immutable records themselves. Lifecycle summaries are persisted as `EvaluationArtifact`s and read only the ledger records and their hash-bound snapshots. Changing or deleting a mutable source run—or later changing planner code or Python versions—cannot redefine a finalized result.

Provider failures are first-class zero-reward records with preserved sessions, costs, failure details, and artifacts. A returned adapter implementation that differs from the requested condition is recorded as an actual-adapter identity mismatch and remains an unscored failed execution; it cannot be credited to the planned adapter. Every submitted checkpoint must have one final submitted attempt and durable session ownership in the planned execution mode. Session results are atomically replaced and fsync-durable. A persistent session that crashes after submitting the final checkpoint but before returning an agent result is sealed from its durable attempts and validated trajectory with unresolved model/adapter identity, recorded as `interrupted_after_completion`, and finalized at zero reward without rebuilding an adapter. A torn terminal `agent_result.json` is retained as `agent_result.corrupt.json` before the conservative failure record is published; a malformed trajectory remains a conflict because the runner will not infer or truncate event history. A rerun never overwrites a finalized success or failure under the same trial ID. Fresh-context retries use attempt-specific directories; abandoned fresh or persistent sessions are sealed as interrupted without pretending that a requested model alias was a provider-resolved identity. A completed invocation—or immutable snapshot—that crashed before core record publication is imported without calling the model again, and a valid immutable snapshot cannot be vetoed by later mutable package or run corruption.

Artifact finalization and execution success do not by themselves justify `completeness=complete`. A lifecycle record is complete only when it also carries typed, hash-bound sessions with observed resolved-model and adapter identity and comes from a clean Git repository snapshot whose commit and source inventory can reproduce the adapter, dispatcher, and registered task scorer. Git provenance is accepted only when the loaded `aec_bench` package is actually tracked by that repository; an ignored installation under another project's `.venv` cannot inherit the caller's commit, and tracked nonstandard package layouts are hashed from the package path that ownership validation actually resolved. Installed source uses a freshly recomputed `source-sha256:` identity over the package and installed distribution metadata so in-process source drift changes the plan. Such records remain `partial` because no retrievable repository revision was observed. Dirty-worktree or unresolved-session invocations likewise remain honest `partial` records while preserving the same immutable evidence.

Every trial also binds a separate runtime-dependency provenance object: requested adapter, locally resolved provider family, sorted distribution identities, and a SHA-256 inventory of the current bytes in the `pydantic-ai-slim` base closure plus the selected provider extra and verifier dependencies. Explicit `provider:model` names use a declared provider-to-extra map and unknown provider prefixes fail closed; unprefixed replay/test identities retain the non-provider base closure. When multiple active distribution roots contain the same package, the first import-search path is authoritative. `RECORD` may enumerate files, but its recorded hashes are never trusted; the planner rereads realized bytes, resolves editable `direct_url.json` sources, and invalidates its per-file cache on filesystem identity, size, mtime, or ctime changes. The invocation recaptures this object after execution, finalization requires exact equality with the planned trial, and the typed `TrialRecord` preserves it. Dependency code drift therefore changes plan/trial identity before execution or becomes an explicit conflict if it occurs after planning.

The manifest accepts only lifecycle controls that the current runner applies: `tool_loop` or `pydantic_ai`, plus a required positive `max_turns_per_session`. The explicit name prevents a per-session cap from being mistaken for a total-trial budget. Provider seeds, temperatures, custom clients, prompt overrides, parallel execution, private holdouts, transfer interventions, total-trial budget allocation, randomized or counterbalanced ordering, and automatic causal interpretation are intentionally deferred rather than silently ignored.

The ledger-derived `EvaluationArtifact` repeats the hash-bound study design and reports each group's session count, configured turn capacity, requests, tool calls, tokens, reward, retention, and cost. It deliberately emits no pairwise effect, winner, or causal estimate. A future causal phase must define retry-aware total-trial budget allocation and randomized or counterbalanced execution before such comparisons are valid.

PR21 extends this runner to action-driven public tasks. A registered hydraulic smoke environment executes the real bounded operation graph for each public variant and constructs submissions from runtime action IDs, so dry-run inspection no longer assumes every task has static gold submissions. The dry-run expands all declared conditions but does not execute a model in each one. For a fresh selectable campaign, provider-configuration preflight errors fail before campaign files or immutable failure records are created; recovery can still finalize a previously completed immutable snapshot. Preflight confirms a configured credential source, not remote authentication.

A selectable manifest preregisters its deterministic selection rule, public and holdout repetitions, and positive finite estimated spend envelope. After all planned public records exist, freeze one exact condition with:

```bash
SSC03_CALIBRATION_MODEL_ID="$MODEL_ID" \
aec-bench --json meta-harness lifecycle-calibration-freeze \
  --config docs/examples/meta-harness/hydraulic-lifecycle-calibration.example.yaml
```

The selector validates every record against its immutable snapshot, retains incorrect completed outcomes in mean reward, and requires stable resolved identity, runtime dependency bytes, lifecycle-operation protocol, and tool schema across every public variant/repetition cell. It cannot run under a sealed holdout mount and publishes one write-once artifact. See [the public calibration and freeze guide](ssc03-public-calibration-freeze.md).

### Evidence-only holdout evaluation

The transfer-evaluation contract is a pure post-verifier read over content-addressed `TrialRecord` references and their immutable snapshot artifacts. It performs no model, adapter, provider, or verifier execution. Record visibility is reconciled with the snapshotted task-owned variant metadata; package and runtime provenance, execution condition, verifier reward, and verifier validity are reconciled with the immutable invocation and verification artifacts. A selected condition is frozen across model, adapter, runtime dependency fingerprint, execution mode, memory visibility policy, and per-session turn limit.

Calibration support must be explicitly `public`; targets must be explicitly `holdout`. Missing visibility is not inferred. Both sides must be complete and verifier-finished, every referenced artifact must still match its recorded hash, and a target package must differ from every integrity-valid calibration input regardless of visibility or condition. Calibration failures remain typed `not_supporting` results, while target failures remain typed `not_evaluable` results, each with explicit reasons. If no target is eligible, mean target reward is `null`, not zero or perfect performance.

The fixed study design calls this `descriptive_holdout_generalization` selected from `public_calibration`. It reports canonical holdout verifier reward and validity plus optional semantic diagnostics without computing an effect, uplift, winner, or learner-transfer claim. It does not mutate the underlying verifier result.

This first surface is deliberately a library build function only. There is no CLI, campaign runner, or generic `EvaluationArtifact` write path. PR20 adds an explicitly mounted private materializer but deliberately blocks its full-fidelity artifacts from the normal public record path. The generic `_evaluations/` directory still does not enforce an internal/holdout publication boundary, so persisting holdout-derived summaries there would create an avoidable leakage surface.

```bash
aec-bench meta-harness lifecycle-run-local \
  --package lifecycle-package \
  --run-dir lifecycle-run \
  --model "$MODEL_ID" \
  --mode fresh-context \
  --visibility-policy artifact_memory
```

Every local invocation writes root-level latest views plus an immutable experiment record:

- `experiment-manifest.json` is a mutable latest-view alias; its canonical indexed copy binds repository commit, source inventory and dirty digest, package hashes, the scorer/dispatcher chain, execution environment, exact model/configuration records, prompts, tool schema, visibility, and every authoritative run-artifact hash;
- `metrics.json` normalizes checkpoint and whole-run timing, requests, tool calls, reads, revisits, retries, failures, tokens, and estimated cost, and carries semantic-transition diagnostics when the task verifier provides them;
- `verification.json` preserves the typed lifecycle verifier result;
- `experiments/<experiment-id>/` preserves the canonical record and its `index-entry.json` seal for each failed, interrupted, resumed, or completed invocation;
- `experiment-index.jsonl` is the shared discovery view, points to each canonical manifest by hash, and is rebuilt under a file lock from valid per-invocation seals after an interrupted append so concurrent repairs cannot lose entries.

This apparatus is an adaptation microscope for fixed-model behavior under staged evidence. Checkpoint progression is ordered and submission-gated; semantic verification occurs over the accumulated lifecycle. It now supports bounded evidence requests and bounded hydraulic calculations whose results depend on the current source. It does **not** yet provide model-performance evidence, cross-run learner updates, demonstrated transfer, or continual learning.

### Semantic transition diagnostics

Semantic diagnostics are deliberately separate from verifier gates and reward. The task-specific verifier projects each cumulative submission into stable semantic atom IDs; the shared metric function compares those atoms across the declared checkpoint order. Equivalent reference lists are canonicalized as sets before comparison.

The output reports explicit support counts and rates:

- `initial.accuracy` is the fraction of initial semantic atoms that match the expected initial state;
- `acquisition` is expected changes that move from the correct prior value to the correct new value, divided by all expected changes;
- `update_precision` is actual changes that end in the expected current value, divided by all actual changes;
- `update_recall` is expected changes whose current value is correct, divided by all expected changes;
- `retention` is previously correct, expected-stable atoms that remain correct, divided by all previously correct, expected-stable atoms;
- `interference` is the complementary count and rate of those prior-correct stable atoms that become incorrect.

An atom that anticipates a future value can receive current-state correctness later, but it does not receive acquisition credit because its prior value was already wrong. A correction to an earlier model mistake can count as a precise update, but it is not evidence-driven acquisition. Rates are `null` when their denominator is zero; zero opportunity is never reported as perfect performance.

SSC-03 currently extracts matrix states, run/report/claim transitions, readiness, stable finding and request identity/state, and accepted-decision status/supersession lineage. Free-form prose and evidence-reference fields with multiple verifier-approved formulations are excluded from exact atom comparison; their existing verifier gates remain authoritative.

These diagnostics are persisted in `verification.json` and copied to `metrics.json` as `semantic_transition`. They are hash-bound by the existing experiment manifest. They do not alter checkpoint progression, model-visible feedback, gate scores, pass/fail, or reward.

## CLI

The `meta-harness` command group exposes the same contracts as the library. The commands are deliberately thin: they parse JSON, call `aec_bench.meta_harness`, and emit the usual AEC-Bench CLI envelope.

There are two intended user surfaces:

- use the CLI/API recipe for scripts and automation;
- use the packaged `/meta-harness` agent skill when an agent should guide the process.

Use the small commands when working on one process boundary:

```bash
aec-bench meta-harness intake --task-text "Create a diagnostic task."
aec-bench meta-harness world-request --brief brief.json --source-world world.json
aec-bench meta-harness logic-evaluate --world world.json --run task-run.json
aec-bench meta-harness review --world world.json --run task-run.json
aec-bench meta-harness operation-apply --world world.json --operation operation.json
aec-bench meta-harness govern \
  --brief brief.json \
  --source-world world.json \
  --proposal proposal.json \
  --decision decision.json
```

Use the model commands when you want a PydanticAI-backed stage. `--emit-run-plan` validates the endpoint shape without calling a provider:

```bash
aec-bench meta-harness intake-models \
  --task-text "Create a diagnostic task." \
  --model openai:gpt-4.1-mini \
  --emit-run-plan

aec-bench meta-harness world-models --brief brief.json --model openai:gpt-4.1-mini
aec-bench meta-harness review-models --world world.json --run task-run.json --model openai:gpt-4.1-mini
aec-bench meta-harness operation-models --brief brief.json --world world.json --model openai:gpt-4.1-mini
```

Endpoint configs may declare `input_cost_per_million`, `output_cost_per_million`, cache token rates, and `request_cost`. When present, model runners emit `cost.estimated_cost_usd`, and autonomous processes include those model-stage costs in `--max-cost-usd` accounting.

Use the operation-orchestrator command to generate an agent request or execute a supplied plan:

```bash
aec-bench meta-harness operation-orchestrate \
  --brief brief.json \
  --world world.json \
  --emit-request

aec-bench meta-harness operation-orchestrate \
  --brief brief.json \
  --world world.json \
  --plan operation-plan.json
```

Use `harbor-task` when you need a Harbor-shaped operation-orchestrator package:

```bash
aec-bench meta-harness harbor-task \
  --brief brief.json \
  --world world.json \
  --plan operation-plan.json \
  --output operation-task
```

Use `recipe` to create a scriptable candidate-vs-baseline workspace:

```bash
aec-bench meta-harness recipe \
  --task-file task.md \
  --baseline-world baseline-world.json \
  --baseline-run baseline-run.json \
  --candidate-world candidate-world.json \
  --candidate-run candidate-run.json \
  --output artefacts/meta-harness/demo
```

The recipe writes `recipe.json`, `run_recipe.sh`, `compare_candidate.py`, and a README. Once baseline and candidate evidence exist, run the comparison script to produce `comparison/comparison.json` and `comparison/comparison.md`.

Run the pauseable process with supplied artifacts:

```bash
aec-bench meta-harness process "Create a diagnostic task." \
  --process-id process.demo \
  --brief brief.json \
  --world world.json \
  --task-run task-run.json \
  --operation-plan operation-plan.json \
  --governance-proposal proposal.json \
  --governance-decision decision.json \
  --output-dir process-output \
  --ledger process-ledger.jsonl
```

When a stage input is omitted, the process pauses at the corresponding awaiting state unless model endpoints are supplied for that stage.

Use `autonomous` for bounded supervision over the same pauseable process. Queued artifacts resolve waiting states; missing artifacts leave the process paused rather than inventing data.

```bash
aec-bench meta-harness autonomous \
  --task-text "Create a diagnostic task." \
  --brief brief.json \
  --world world.json \
  --task-run task-run.json \
  --operation-plan operation-plan.json \
  --max-iterations 3 \
  --output autonomous-output
```

## Harbor Bindings

Use `build_harbor_task_run_resolver` for a generic Harbor-compatible command that writes `result.json` and related artifacts:

```python
from aec_bench.meta_harness.harbor import build_harbor_task_run_resolver

resolver = build_harbor_task_run_resolver(
    command=["python", "-m", "some_runner", "--output", "artifacts"],
    artifact_dir=Path("artifacts"),
)

task_run = resolver(runtime_result)
```

Use `build_aecbench_harbor_task_run_resolver` when an autonomous process needs a task-run resolver backed by AEC-Bench Harbor execution:

```python
from aec_bench.meta_harness.aecbench import (
    AecBenchWorkflowConfig,
    build_aecbench_harbor_task_run_resolver,
)

resolver = build_aecbench_harbor_task_run_resolver(
    manifest=manifest,
    workflow_config=AecBenchWorkflowConfig(project_root=repo_root),
)

task_run = resolver(runtime_result)
```

The resolver returns `{"run_id": ..., "evidence": ...}` with score, artifacts, imported trial records, and AEC-Bench workflow metadata.
