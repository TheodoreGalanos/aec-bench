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
- `aec_bench.meta_harness.evidence_lifecycle_local` runs one lifecycle through either a persistent model conversation or fresh checkpoint contexts.
- `aec_bench.meta_harness.evidence_lifecycle_metrics` compares task-extracted semantic atoms across checkpoints without changing verifier reward.
- `aec_bench.meta_harness.evidence_lifecycle_experiment` binds code, package, model configuration, prompts, tools, trajectories, metrics, and verification into an indexed experiment record.

## Evidence Lifecycles

An evidence lifecycle is one evolving task run inside one task world. Evidence is released in declared checkpoint order; each structurally valid submission is archived before the host releases the next packet. A revisit reads an immutable earlier checkpoint without changing active state. Changing an earlier submission creates a derived branch from that checkpoint rather than mutating the parent run.

`lifecycle-run-local` supports two baseline execution conditions:

- `persistent` uses one model conversation across all checkpoints with `persistent_context` visibility;
- `fresh-context` creates one model context per checkpoint and defaults to `artifact_memory`, where earlier submissions remain model-visible.

Two additional fresh-context policies define later ablations without deleting audit artifacts:

- `raw_evidence_only` exposes cumulative released evidence but hides prior submissions;
- `current_release_only` exposes only the active release and active instruction.

The host workspace tool enforces visibility. All released evidence, archived submissions, trajectories, and conversations remain on disk for audit regardless of the model-visible policy.

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

```bash
aec-bench meta-harness lifecycle-run-local \
  --package lifecycle-package \
  --run-dir lifecycle-run \
  --model "$MODEL_ID" \
  --mode fresh-context \
  --visibility-policy artifact_memory
```

Every local invocation writes root-level latest views plus an immutable experiment record:

- `experiment-manifest.json` binds the repository commit and dirty digest, package and verifier hashes, exact model/configuration records, prompts, tool schema, visibility, and output hashes;
- `metrics.json` normalizes checkpoint and whole-run timing, requests, tool calls, reads, revisits, retries, failures, tokens, and estimated cost, and carries semantic-transition diagnostics when the task verifier provides them;
- `verification.json` preserves the typed lifecycle verifier result;
- `experiments/<experiment-id>/` preserves the canonical record for each failed, interrupted, resumed, or completed invocation;
- `experiment-index.jsonl` is append-only and points to each canonical manifest by hash.

This apparatus is an adaptation microscope for fixed-model behavior under staged evidence. Checkpoint progression is ordered and submission-gated; semantic verification occurs over the accumulated lifecycle. It does **not** yet provide action-conditioned evidence transitions, cross-run learner updates, demonstrated transfer, or continual learning.

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
