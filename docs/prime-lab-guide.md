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
  --remote-env gabriel-syme/aec_prime_50_suite \
  --hosted \
  --model "Qwen/Qwen3.5-4B" \
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
  --remote-env gabriel-syme/aec_prime_50_suite \
  --hosted \
  --model "Qwen/Qwen3.5-4B" \
  --adapter-id uv124zgh7ttg3in94f7jzmv2 \
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
prime eval run gabriel-syme/aec_prime_50_suite \
  --model "Qwen/Qwen3.5-4B:uv124zgh7ttg3in94f7jzmv2" \
  --env-args '{"split":"eval","difficulty":"medium","harness":"stateful","num_examples":10,"seed":20260509}' \
  --num-examples 5 \
  --rollouts-per-example 3 \
  --max-tokens 4096 \
  --hosted
```

Use repeated `--difficulty` flags for mixed slices:

```bash
uv run aec-bench prime eval \
  --remote-env gabriel-syme/aec_prime_50_suite \
  --hosted \
  --model "Qwen/Qwen3.5-4B" \
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

Closed hosted inference models such as Claude Sonnet or Haiku are useful for
baseline evaluation and teacher rollouts, but they are not hosted fine-tuning
targets. Training configs should use Prime trainable models such as Qwen,
Llama, Nemotron, or GPT-OSS models exposed by the account.

## Design Direction

The integration should remain explicit rather than magical:

- Classify each task into an export lane.
- Preserve the task verifier as the source of reward truth.
- Preserve RLM and lambda-RLM guardrails during export.
- Prefer deterministic rubrics over LLM judges where engineering correctness can
  be checked mechanically.
- Use LLM judges only for genuinely open-ended proposal/document quality.
- Keep generated Prime artifacts outside version control.
