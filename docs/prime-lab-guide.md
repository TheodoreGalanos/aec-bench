# Prime Lab Integration Guide

AEC-Bench can export tasks as Prime Lab environments for baseline evaluation,
rollout generation, and hosted RL training. This guide maps the Prime recipe
taxonomy to the task and harness concepts already used in this repository.

## Mapping

| Prime recipe | Prime environment | AEC-Bench lane | Export status |
|---|---|---|---|
| Math reasoning | `SingleTurnEnv` with exact or symbolic rubric | Formula and deterministic engineering tasks | Supported |
| Code generation with sandboxes | `PythonEnv` or `SandboxEnv` | Workspace tasks that execute files, scripts, or verifiers | Partial: exported as workspace tools |
| Multi-turn games and puzzles | Custom `MultiTurnEnv` | Interactive sequential tasks | Not a primary lane yet |
| Tool use and agentic tasks | `ToolEnv`, `MCPEnv`, or `StatefulToolEnv` | RLM, lambda-RLM, source lookup, document workflows | Supported as stateful workspace export; first-class policy export is next |
| Persistent evidence lifecycles | `StatefulToolEnv` with host-owned lifecycle tools | Staged evidence review across checkpoints | Supported as a local-only export |
| Multi-environment training | Multiple `[[env]]` entries with ratios | Cross-domain AEC benchmark suites | Planned config layer |

## Export Lanes

### Deterministic Single-Turn Tasks

Use this for tasks where the model can answer directly and a verifier can score
the final response without intermediate state.

Examples:

- Electrical voltage drop
- Heat-load calculations
- Bearing-capacity calculations
- Slope-stability calculations

Prime shape:

- `verifiers.SingleTurnEnv`
- Dataset row contains the task instruction
- Rubric writes the model completion to `output.md`
- Original `tests/verify.py` computes reward

This lane is closest to Prime's math-reasoning recipe. The main difference is
that AEC-Bench uses task-local engineering verifiers rather than `MathRubric`.

### Stateful Workspace Tasks

Use this for tasks that need file IO, command execution, or a persistent
workspace across turns.

Prime shape:

- `verifiers.StatefulToolEnv`
- Rollout-local copy of the task directory
- Tools for `read_file`, `write_file`, `list_files`, `run_command`, and
  `submit_answer`
- `submit_answer` writes `output.md` and ends the rollout
- Original `tests/verify.py` computes reward

This lane is closest to Prime's code-generation and sandbox recipes, but the
current export intentionally stays provider-neutral by exposing workspace tools
instead of depending on a Prime sandbox-specific environment class.

### RLM and Lambda-RLM Tasks

Use this for tasks where the important object is not only the final answer but
the interaction policy: search, inspect, extract, reflect, and submit.

Prime shape today:

- Classified from `rlm.toml` and `lambda-rlm.toml`
- Exported as `StatefulToolEnv`
- `[guardrails].max_iterations` becomes generated `max_turns`
- `[guardrails].token_budget` is carried into task metadata and prompt context
- Task verifier remains the scoring authority

This is enough for smoke evals and small hosted runs. The next deeper step is to
export RLM and lambda-RLM policies into explicit Verifiers state transitions and
tools, instead of treating them as generic workspace affordances.

### Local Evidence-Lifecycle Environments

Use this lane to expose existing materialized public evidence lifecycles through
the local Verifiers API. The export is a thin package: it references lifecycle
packages already on disk and delegates execution to the AEC-Bench lifecycle
host. It does not copy or rematerialize the lifecycle packages.

One Verifiers rollout spans the whole lifecycle in one persistent conversation.
The model receives later evidence only after it submits the active checkpoint.
The environment reuses the host-owned `list_workspace`, `read_workspace_file`,
`write_checkpoint_submission`, `submit_checkpoint`, and `revisit_checkpoint`
tools, so the same visibility, path-confinement, immutable-submission, and
checkpoint-order rules apply inside and outside Prime.

Export one or more materialized public variants with absolute paths:

```bash
uv run aec-bench prime export-lifecycle \
  --name ssc03-persistent-lifecycle \
  --package /absolute/path/to/staged-full-correction \
  --package /absolute/path/to/semantic-no-op-release \
  --output-dir /absolute/path/to/prime-rl/environments \
  --max-turns 60 \
  --aec-bench-root /absolute/path/to/aec-bench
```

The generated `lifecycle_manifest.json` binds each absolute package path to its
lifecycle-spec and package hashes. It also records the exact local AEC-Bench
source provenance, including the commit, dirty-state digest, and source
inventory hash. The generated `pyproject.toml` binds that checkout as an
editable local `[tool.uv.sources]` dependency, so the executing runtime and the
recorded source are the same tree. Loading and rollout setup reject source
drift; rollout setup rejects package drift.

Reward remains task-owned. `submit_checkpoint` ends the rollout only after the
final checkpoint is accepted; the registered lifecycle verifier then scores the
complete run. An incomplete rollout is closed as failed and receives zero
reward instead of being scored from partial state.

Load the generated package from outside the AEC-Bench repository root. The
repository has a top-level `agents/` directory that can otherwise shadow the
installed `openai-agents` package required by Verifiers:

```bash
uv sync --python 3.13 --project /absolute/path/to/prime-rl/environments/ssc03-persistent-lifecycle
cd /tmp
/absolute/path/to/prime-rl/environments/ssc03-persistent-lifecycle/.venv/bin/python \
  -c "from ssc03_persistent_lifecycle import load_environment; print(type(load_environment()).__name__)"
```

This lane is local-only. It does not support hosted publication, hosted
execution, training, fresh-context lifecycle conditions, transfer evaluation,
or continual learning. Those require separate contracts and evidence.

## Defaults and Limits

AEC-Bench exports conservative defaults:

- Generated Prime packages write to `prime-rl/environments/`
- `prime-rl/` is ignored by git because generated packages and eval outputs are
  local artifacts
- Smoke evals use `--max-tokens 2048` by default
- RLM tasks inherit `max_turns` from `max_iterations`
- Hosted-compatible packages require `verifiers>=0.1.10`

For longer RLM runs, prefer explicit eval settings:

```bash
prime eval run <owner>/<env> \
  --model anthropic/claude-haiku-4.5 \
  --num-examples 1 \
  --rollouts-per-example 1 \
  --max-tokens 4096 \
  --max-concurrent 1
```

Hosted eval currently controls some runtime package versions. Keep generated
environments compatible with `verifiers==0.1.10` unless Prime exposes a hosted
runtime override.

## Hosted Eval and Adapter Eval

Prime uses the same evaluation boundary for base models and Hosted Training
adapters. In AEC-Bench, keep that model simple: export or reference one Prime
environment, choose the same task slice, then change only the model identifier.

### Baseline Eval

Run the base model first and pin the environment selection arguments. This makes
the adapter result comparable instead of accidentally sampling a different task
slice.

```bash
uv run aec-bench prime eval \
  --remote-env <prime-namespace>/<environment-name> \
  --hosted \
  --model "<base-model-id>" \
  --split eval \
  --difficulty medium \
  --harness stateful \
  --env-num-examples 10 \
  --seed 20260509 \
  --num-examples 5 \
  --rollouts-per-example 3 \
  --max-tokens 4096 \
  --eval-name aec-prime-50-base-medium-stateful
```

The AEC-Bench wrapper forwards `--split`, `--difficulty`, `--harness`,
`--env-num-examples`, and `--seed` through Prime's `--env-args`, which are
passed to the generated package's `load_environment(...)` function.

### Adapter Eval

After Hosted Training finishes, list deployable adapters:

```bash
prime deployments list --plain
```

Deploy the ready adapter:

```bash
prime deployments create <adapter-id> --yes --plain
```

Then evaluate it through the same AEC-Bench eval command. Pass the trainable base
model as `--model` and the adapter id as `--adapter-id`; AEC-Bench composes the
Prime inference model string as `<base-model>:<adapter-id>`.

```bash
uv run aec-bench prime eval \
  --remote-env <prime-namespace>/<environment-name> \
  --hosted \
  --model "<base-model-id>" \
  --adapter-id <adapter-id> \
  --split eval \
  --difficulty medium \
  --harness stateful \
  --env-num-examples 10 \
  --seed 20260509 \
  --num-examples 5 \
  --rollouts-per-example 3 \
  --max-tokens 4096 \
  --eval-name aec-prime-50-adapter-medium-stateful
```

This is equivalent to calling Prime with:

```bash
prime eval run <prime-namespace>/<environment-name> \
  --model "<base-model-id>:<adapter-id>" \
  --env-args '{"split":"eval","difficulty":"medium","harness":"stateful","num_examples":10,"seed":20260509}' \
  --num-examples 5 \
  --rollouts-per-example 3 \
  --max-tokens 4096 \
  --hosted
```

Use repeated `--difficulty` flags for mixed slices:

```bash
uv run aec-bench prime eval \
  --remote-env <prime-namespace>/<environment-name> \
  --hosted \
  --model "<base-model-id>" \
  --adapter-id <adapter-id> \
  --difficulty easy \
  --difficulty medium
```

Use `--env-arg KEY=VALUE` for extra generated-environment arguments that are not
first-class CLI options yet. Values are parsed as JSON when possible, so
`--env-arg max_turns=20` becomes an integer and `--env-arg source=adapter-smoke`
stays a string.

### Interpreting the Comparison

For a meaningful base-vs-adapter check, keep these fixed:

- Remote environment slug and published version
- `split`, `difficulty`, `harness`, `env-num-examples`, and `seed`
- `num-examples`, `rollouts-per-example`, `max-tokens`, and concurrency
- The base model paired with the adapter

Inspect more than reward. For stateful AEC-Bench exports, check:

- `submit_answer_calls`: whether the rollout reaches the verifier path
- `run_command_calls`, `read_file_calls`, and `write_file_calls`: whether tools
  are actually being used
- `has_error` and `EmptyModelResponseError`: whether failures are model/runtime
  behavior rather than verifier disagreement
- Per-example reward rows: whether one task dominates the aggregate result

Small evals are smoke tests, not benchmark claims. Scale the same fixed config
only after the stateful tool loop is visibly healthy.

## Training Readiness

Before launching hosted training:

1. Push the environment privately.
2. Run a one-example hosted eval.
3. Confirm reward is nonzero and the stop condition is expected.
4. Check tool-call metrics: `run_command_calls`, `write_file_calls`,
   `submit_answer_calls`, and `total_tool_calls`.
5. Choose trainable open-weight base models from `prime train models`.

Closed hosted inference models are useful for baseline evaluation and teacher
rollouts, but they are not hosted fine-tuning targets. Training configs should
use trainable models exposed by the Prime account.

### Training Configs with Difficulty Filtering

Use `aec-bench prime train-config` to generate Hosted Training TOML rather than
hand-editing Prime configs. For broad suites, keep the train environment fixed
and create difficulty-filtered environment views with repeated
`--difficulty-ratio` flags:

```bash
uv run aec-bench prime train-config \
  --environment <prime-namespace>/<environment-name> \
  --output configs/rl/aec-filtered-ratios.toml \
  --model "Qwen/Qwen3.5-9B" \
  --split all \
  --harness stateful \
  --difficulty-ratio easy=0.45 \
  --difficulty-ratio medium=0.40 \
  --difficulty-ratio hard=0.15 \
  --max-steps 50 \
  --batch-size 64 \
  --rollouts-per-example 8 \
  --max-tokens 4096 \
  --online-difficulty-filtering \
  --easy-threshold 0.8 \
  --hard-threshold 0.2 \
  --easy-fraction 0.25 \
  --hard-fraction 0.25
```

This emits one `[[env]]` block per difficulty and a Prime `[buffer]` section
with matching `env_ratios`. The ratio flags are mutually exclusive with
repeated `--difficulty`, which still represents a single environment view with a
list of allowed difficulties.

For noisy AEC reward surfaces, start with some easy and hard examples retained
instead of dropping them completely. That keeps the run from collapsing into
only already-solved examples or only zero-signal failures while still letting
Prime focus training on examples near the model's current capability.

## Design Direction

The integration should remain explicit rather than magical:

- Classify each task into an export lane.
- Preserve the task verifier as the source of reward truth.
- Preserve RLM and lambda-RLM guardrails during export.
- Prefer deterministic rubrics over LLM judges where engineering correctness can
  be checked mechanically.
- Use LLM judges only for genuinely open-ended proposal/document quality.
- Keep generated Prime artifacts outside version control.
