---
name: configure-experiment
description: Build an experiment.yaml config interactively. Discovers available tasks, guides agent and model selection, validates the manifest, and previews the trial plan with a dry run. Use when the user wants to set up, configure, or plan a benchmark run.
---

# Configure Experiment

Build a valid `experiment.yaml` by discovering what's in your project, guiding you through task selection and agent configuration, and previewing the trial plan.

## When to Use

- User runs `/configure-experiment`
- User asks to "set up an experiment", "configure a run", "plan a benchmark"
- User wants to create or modify an experiment.yaml

## Process

### Step 1 — Detect Context

Read `aec-bench.toml` to resolve project paths. If it doesn't exist, tell the user to run `aec-bench init` first and stop.

Scan the tasks directory by reading `task.toml` files:
- Count tasks by discipline (use the first path segment under tasks/)
- Count tasks by difficulty (read `[metadata].difficulty` from each task.toml)
- Note which tasks have `[[environment.tools]]` declarations
- Note which tasks have tools with `returns_image = true`

Check for datasets:
- Run `aec-bench dataset list` to discover existing datasets
- Note dataset names, versions, task counts, and domains

Check for project maturity:
- Look for existing `experiment*.yaml` files in the project root
- Check if the ledger directory (`artefacts/ledger/` or configured path) has experiment subdirectories

**If returning user** (existing experiment YAMLs or ledger data found):

List existing experiment configs and offer to modify one:
> "Found existing experiment configs. Want to modify one, or start fresh?"
>
> 1. `experiment.yaml` — electrical-sonnet-2026-03-19
> 2. `experiment-ground.yaml` — ground-gpt4o-2026-03-18
> 3. Configure from scratch

If they choose to modify: load the YAML, show it, ask what to change, then jump to Step 5.

**If fresh project:** Proceed to Step 2.

### Step 2 — Task Selection

**If datasets exist**, offer them first:

> **How do you want to select tasks?**
>
> A. **Use a dataset** (recommended for reproducible benchmarks)
>    - `electrical-only@1.0.0` — 6 tasks, electrical
>    - `full-benchmark@1.0.0` — 200 tasks, all domains
> B. **Select from tasks on disk** (exploratory, ad-hoc)

If the user chooses a dataset, set `tasks.dataset: "name@version"` in the config and offer optional filters (difficulty, patterns) on top. Skip to Step 3.

If the user chooses to generate a config from a dataset, suggest:
```bash
aec-bench dataset config <name>@<version> --model <model> -o experiment.yaml
```

**If no datasets exist**, or user chooses option B, show what's on disk:

```
Your tasks:
  electrical  45 tasks (12 easy, 20 medium, 13 hard)
  ground      23 tasks (8 easy, 10 medium, 5 hard)
  civil       67 tasks (25 easy, 28 medium, 14 hard)
  mechanical   0 tasks
  structural   0 tasks
```

Only show disciplines that have tasks. Use the actual counts from scanning.

Ask: **Which disciplines do you want to benchmark?** (multiple choice from available)

Then ask: **Which difficulty levels?** (default: all available)
- Fresh user: explain that easy tests basic knowledge, medium adds hidden parameters, hard requires deep domain expertise.

For advanced users who want finer control, offer include/exclude patterns:
> "Want to filter further with glob patterns? (e.g., `electrical/voltage-*` to only run voltage tasks)"
> Most users can skip this.

After selection, show the count:
> "That selects 34 tasks across 2 disciplines."

If zero tasks match, warn and let them re-select.

> **Tip:** Consider creating a dataset with `/create-dataset` to make this selection reproducible.

### Step 3 — Agent Configuration

Read `references/agent-provider-matrix.md` for the full compatibility table.

Show available agent types:

```
Available agents:
  1. tool_loop   — Multi-turn tool use (Anthropic, Azure OpenAI)
  2. pydantic_ai — PydanticAI framework (all providers, multimodal support)
                   Note: requires harbor_import_path override
  3. direct      — Single-turn, no tools (Anthropic, Azure OpenAI)
```

Add contextual notes based on the selected tasks:
- If tasks have tools: "X of your Y tasks declare tools — tool_loop or pydantic_ai will use them, direct won't."
- If tasks have `returns_image: true`: "Z tasks have image-returning tools — pydantic_ai handles those natively."

Ask: **Which agent type?**

If they choose `pydantic_ai`, explain:
> "PydanticAI isn't in the default Harbor dispatch table yet. You'll need to provide the import path to your PydanticAI agent class. For example: `agents.pydantic_ai_anthropic:PydanticAIAnthropicAgent`"

Ask: **Which model?**

Suggest models based on the agent-provider matrix:
- tool_loop + Anthropic: `claude-sonnet-4-20250514`, `claude-haiku-4-5-20251001`
- tool_loop + Azure OpenAI: `gpt-4o`, `o3`, `o4-mini`
- pydantic_ai: any of the above plus `gemini-2.5-pro`
- direct: same as tool_loop

Ask: **Custom system prompt file?** (default: none)
- If none: the agent uses the task's built-in `system_prompt.md` if it exists in the container, otherwise its own default.
- If specified: validate the file exists relative to the project root.

Ask: **Max turns?** (default: 10, only for tool_loop/pydantic_ai)
- Fresh user: "10 is good for most tasks. Increase to 20 for complex multi-step tasks."

Auto-generate agent name: `{adapter}-{model_short}` (e.g., `tool_loop-sonnet`).

After completing the first agent:
> "Want to add another agent for comparison? (e.g., pit Sonnet against GPT-4o)"

If yes, loop back through the agent questions. If no, proceed.

### Step 4 — Execution Settings

Ask: **How many repetitions per task-agent pair?** (default: 1)
- Fresh user: "1 is fine for a quick test. Use 3+ for statistically meaningful results."

Ask: **Compute backend?** (default from `aec-bench.toml`)
- Valid values: `modal` (serverless via Modal), `docker` (local Docker)
- Fresh user: "modal is the default — runs trials in cloud containers."

Ask: **Concurrent trials?** (default: 4)
- Fresh user: "How many trials to run in parallel. 4 is safe for Modal free tier."

Auto-generate experiment ID: `{primary_discipline}-{model_short}-{date}`
- Example: `electrical-sonnet-2026-03-21`
- If this ID already exists (ledger directory or YAML file), append `-02`, `-03`, etc.

Ask: **Experiment name?** Suggest one based on the config, let user override.
- Example: "Electrical benchmark — Sonnet 4.6"

### Step 5 — Write YAML

Assemble the complete YAML from collected answers. The structure must exactly match the `ExperimentManifest` Pydantic contract (strict mode — no extra fields allowed).

Read `references/manifest-schema.md` for field reference.

Write to `experiment.yaml` in the project root (or a user-chosen filename).

Show the file contents with YAML syntax highlighting.

Important: do NOT include `lifecycle_filter` in the YAML — it's in the contract but not consumed by the scheduler.

### Step 6 — Dry Run

Execute the dry run:

```bash
uv run aec-bench run --config experiment.yaml --dry-run
```

Show the output to the user (trial plan table showing task count, agents, total trials).

Tell the user:
> "Config written to `experiment.yaml`. When you're ready:"
> ```
> aec-bench run --config experiment.yaml
> ```

## Reference Files

Read these during execution:

- `references/manifest-schema.md` — Field-by-field reference for ExperimentManifest
- `references/agent-provider-matrix.md` — Which agents work with which providers and models
- `references/example-configs.md` — 4 concrete experiment.yaml examples to reference
