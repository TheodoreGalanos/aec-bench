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
