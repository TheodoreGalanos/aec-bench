# aec-bench User Guide

Common workflows for creating, running, and evaluating AEC benchmark tasks.

## Getting Started

```bash
# Install from source
git clone <repo> && cd aec-bench
uv sync --dev

# Add optional surfaces when needed
uv sync --extra webui --dev
uv sync --extra pydantic-ai

# Or install a packaged release
pip install aec-bench
pip install "aec-bench[webui]"  # browser UI runtime

# Initialise a project
aec-bench init my-benchmark
cd my-benchmark
```

This creates:
- `aec-bench.toml` — project config
- `suite.toml` — dataset generation config (example templates)
- `.claude/skills/` — bundled skills for Claude Code

---

## Journey 1: Generate a Dataset from Existing Templates

You have 80+ built-in templates across ground, electrical, and civil engineering. Generate a dataset of task instances from them.

```bash
# Browse available templates
aec-bench generate list-templates
aec-bench search "bearing capacity"

# Edit suite.toml to select templates and instance counts
# (created by `aec-bench init`)

# Generate instances
aec-bench generate suite --config suite.toml

# Preview what would be generated (without writing files)
aec-bench generate suite --config suite.toml --dry-run
```

### suite.toml format

```toml
[[dataset]]
template = "terzaghi-bearing-capacity"
count = 5

[[dataset]]
template = "voltage-drop"
count = 10
difficulty = "easy,medium"    # Optional: filter by difficulty

[settings]
seed = 42
output = "tasks"
```

---

## Journey 2: Generate and Run with an Agent

Generate instances from a single template and run them through an agent.

```bash
# Generate 3 instances of a specific template
aec-bench generate task terzaghi-bearing-capacity --instances 3 --seed 42

# Run with a tool-loop agent (default)
aec-bench run tasks/ground/shallow-foundations/terzaghi-bearing-capacity \
  --model "<model-id>"

# Run with the PydanticAI-backed tool-loop alias
aec-bench run tasks/electrical/pf-droop \
  --model "<model-id>" \
  --adapter pydantic_ai

# Dry run to preview the trial plan
aec-bench run tasks/ground/shallow-foundations/terzaghi-bearing-capacity \
  --model "<model-id>" --dry-run

# Preview a post-verifier LLM reviewer stage
aec-bench run tasks/ground/shallow-foundations/terzaghi-bearing-capacity \
  --model "<model-id>" \
  --reviewer-models-config reviewer-models.json \
  --dry-run

# Run through Morph Cloud via Harbor
aec-bench run tasks/electrical/pf-droop \
  --model "<model-id>" \
  --adapter pydantic_ai \
  --backend morph

# Evaluate results
aec-bench evaluate
```

### Backend Selection

`aec-bench run` executes through Harbor. The default backend is `modal`; supported run backends are `modal`, `morph`, `e2b`, `daytona`, and `docker`.

Use `--backend morph` when you want Harbor's normal task/agent/verifier flow to run on Morph Cloud. Morph runs require the `morphcloud` package and `MORPH_API_KEY` in `.env`.

### Post-Verifier LLM Reviewer

Add `--reviewer-models-config reviewer-models.json` to run an LLM reviewer after
the verifier. The reviewer can use multiple PydanticAI model endpoints:

```json
{
  "enabled": true,
  "models": [
    {"name": "openai-main", "model": "openai:gpt-5.2"},
    {"name": "claude-reviewer", "model": "anthropic:claude-opus-4-8"}
  ]
}
```

For local runs, reviewer artifacts are copied under `logs/reviewer/`. For
Harbor-backed runs, reviewer summaries are written into each trial directory
before ledger import and appear under `evaluation.breakdown.llm_reviewer`.

Tasks can optionally include a `world.yaml` sidecar to define the reviewer-facing
task-world profile: `logic_profile` gates, operation handles, and review modes.
When no sidecar exists, a conservative default profile is derived from the task
and final verifier evidence. The resolved profile is saved as
`world_profile.json` beside the reviewer request.

### Adapter types

| Adapter | When to use |
|---------|------------|
| `tool_loop` | Default. Text-only tasks with bash + custom tools. |
| `pydantic_ai` | Compatibility alias for the PydanticAI-backed tool loop. |
| `rlm` | RLM reasoning adapter for scaffolded/report-style tasks. |
| `lambda-rlm` | Template-driven RLM report adapter. |
| `direct` | Single-turn tasks with no tool use. |

### Azure AI Foundry Models

Foundry deployments that expose the v1 OpenAI-compatible API can run through
the PydanticAI-backed adapters. Put the endpoint and key in `.env`, then pass
the deployment name exactly as Foundry shows it:

```bash
AZURE_OPENAI_ENDPOINT=https://example.services.ai.azure.com/openai/v1/
AZURE_OPENAI_API_KEY=

aec-bench run tasks/electrical/pf-droop \
  --model "DeepSeek-V4-Flash" \
  --adapter pydantic_ai
```

For classic Azure OpenAI deployments, use the same environment variables with
the normal Azure OpenAI endpoint and `AZURE_OPENAI_API_VERSION`.

### Together AI Models

Together models use the OpenAI-compatible chat-completions endpoint. Put the
key in `.env`, then prefix the model with `together:` so provider routing stays
explicit:

```bash
TOGETHER_API_KEY=

aec-bench run tasks/electrical/pf-droop \
  --model "together:Qwen/Qwen3.7-Max" \
  --adapter pydantic_ai
```

The prefix is stripped before the request is sent to Together.

---

## Journey 3: Create a New Template and Run It

Build a reusable template from a seed, then generate and run instances.

```bash
# Step 1: Add a task seed (via agent skill)
/add-task
# Follow the prompts to describe the engineering calculation

# Step 2: Create the template (via agent skill)
/create-template seeds/<discipline>/<task-id>/source_task.json
# Researches formulas, writes engine.py + params.toml + instruction.md
# Validates with: aec-bench generate validate-template <template_dir>

# Step 3: Generate instances
aec-bench generate task <template-name> --instances 5

# Step 4: Run
aec-bench run tasks/<discipline>/<category>/<template-name> \
  --model "<model-id>"

# Step 5: Harden (via agent skill)
/hardening-pass
```

For task-world harness design or candidate-vs-baseline harness comparison, use the
meta-harness skill:

```bash
/meta-harness
```

For scripts, start with:

```bash
aec-bench meta-harness recipe --task-file task.md --output artefacts/meta-harness/demo
```

---

## Journey 4: Create a Chart-Generating Task

Build a task where the agent generates charts or diagrams as part of its workflow. The current unified entrypoint treats generated image paths as text output; binary image self-review is only available on legacy script routes.

```bash
# Step 1: Create the task directory
mkdir -p tasks/electrical/my-task/environment/tools
mkdir -p tasks/electrical/my-task/tests
```

### task.toml

```toml
version = "1.0"

[metadata]
difficulty = "medium"
category = "power-systems"
tags = ["electrical", "chart-generation"]

[agent]
timeout_sec = 600.0

[verifier]
timeout_sec = 120.0

[environment]
extensions = ["multimodal"]

[[environment.tools]]
name = "create_chart"
source = "tools/create_chart.py"
description = "Generate a chart from computed data."
returns_image = true
```

### Container setup

```bash
# Generate the Dockerfile from extensions
aec-bench generate dockerfiles tasks/

# This creates environment/Dockerfile with pydantic-ai + matplotlib
```

### Required files

| File | Purpose |
|------|---------|
| `task.toml` | Metadata, extensions, tool declarations |
| `instruction.md` | What the agent must do |
| `ground_truth.json` | Expected numeric outputs |
| `environment/tools/create_chart.py` | Optional chart generator script used by the task |
| `tests/verify.py` | Scores agent output against ground truth |

### Run it

```bash
aec-bench run tasks/electrical/my-task \
  --model "<model-id>" \
  --adapter pydantic_ai
```

See `tasks/electrical/pf-droop/` and `tasks/electrical/qv-droop/` for manually authored chart-generation examples.

---

## Journey 5: Review and Analyse Results

After running experiments, review results interactively or programmatically.

```bash
# Launch the TUI (browse, triage, review)
aec-bench tui

# Evaluate experiment results
aec-bench evaluate

# Generate reports
aec-bench report

# Export ledger data
aec-bench ledger --experiment <id> --output json

# Search for specific tasks
aec-bench search "voltage drop"
```

---

## Container Extensions

Tasks declare container capabilities via `extensions` in task.toml instead of writing Dockerfiles manually.

```toml
[environment]
extensions = ["claude-cli", "multimodal"]
```

### Available extensions

| Extension | What it adds | When to use |
|-----------|-------------|-------------|
| `claude-cli` | curl, procps, Claude Code CLI | Tasks using Claude Code as the agent |
| `multimodal` | pydantic-ai, matplotlib | Tasks with chart/image generation dependencies |
| `ocr` | tesseract, poppler-utils | Tasks requiring OCR or PDF processing |

### Generating Dockerfiles

```bash
# Generate Dockerfiles for all tasks with extensions
aec-bench generate dockerfiles tasks/

# Preview without writing
aec-bench generate dockerfiles tasks/ --dry-run
```

Tasks that declare `extensions` get auto-generated Dockerfiles. Tasks without `extensions` (or with custom needs) keep their hand-written Dockerfiles.

**Important:** Run `aec-bench generate dockerfiles` after creating new tasks with extensions, or after changing the extension definitions. A warning will appear during task loading if a Dockerfile is missing or out of sync.

---

## Image-Returning Tools

Tasks can declare image-producing tools with `returns_image = true` in task.toml:

```toml
[[environment.tools]]
name = "create_chart"
source = "tools/create_chart.py"
description = "Generate a chart from computed data."
returns_image = true
```

The legacy script agent path can consume `IMAGE:/path/to/file.png` markers. The current unified entrypoint records tool output as text and does not expose binary image returns to the model, so do not rely on multimodal self-review unless you are intentionally using that legacy route.

### How it works

```
Agent computes values → calls create_chart tool → tool generates PNG
→ tool prints IMAGE:/workspace/chart.png → output is available as text
→ verifier scores the submitted answer
```

Treat `returns_image = true` as partial support in the unified entrypoint.

---

## Quick Reference

| Command | Purpose |
|---------|---------|
| `aec-bench init` | Set up a new project |
| `aec-bench search <query>` | Find templates and seeds |
| `aec-bench generate list-templates` | List available templates |
| `aec-bench generate task <name>` | Generate instances from a template |
| `aec-bench generate suite --config suite.toml` | Generate a full suite |
| `aec-bench generate dockerfiles tasks/` | Regenerate Dockerfiles from extensions |
| `aec-bench generate validate-template <dir>` | Validate a template |
| `aec-bench run <path> --model <model>` | Run an experiment |
| `aec-bench evaluate` | Score and summarise results |
| `aec-bench report` | Generate analysis reports |
| `aec-bench tui` | Interactive terminal UI |
| `aec-bench config` | View/manage configuration |
