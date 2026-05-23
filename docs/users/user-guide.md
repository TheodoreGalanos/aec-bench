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
aec-bench generate dataset --config suite.toml

# Preview what would be generated (without writing files)
aec-bench generate dataset --config suite.toml --dry-run
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
  --model claude-sonnet-4-20250514

# Run with the PydanticAI agent (required for multimodal tasks)
aec-bench run tasks/electrical/pf-droop \
  --model claude-sonnet-4-20250514 \
  --adapter pydantic_ai

# Dry run to preview the trial plan
aec-bench run tasks/ground/shallow-foundations/terzaghi-bearing-capacity \
  --model claude-sonnet-4-20250514 --dry-run

# Evaluate results
aec-bench evaluate
```

### Adapter types

| Adapter | When to use |
|---------|------------|
| `tool_loop` | Default. Text-only tasks with bash + custom tools. |
| `pydantic_ai` | Multimodal tasks (charts, images). Requires `pydantic-ai` in container. |
| `script` | Single-turn tasks (no tool use). |

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
  --model claude-sonnet-4-20250514

# Step 5: Harden (via agent skill)
/hardening-pass
```

---

## Journey 4: Create a Multimodal Task

Build a task where the agent generates charts or diagrams as part of its workflow.

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
tags = ["electrical", "multimodal"]

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
| `environment/tools/create_chart.py` | Chart generator (prints `IMAGE:/path` for multimodal) |
| `tests/verify.py` | Scores agent output against ground truth |

### Run it

```bash
aec-bench run tasks/electrical/my-task \
  --model claude-sonnet-4-20250514 \
  --adapter pydantic_ai
```

See `tasks/electrical/pf-droop/` and `tasks/electrical/qv-droop/` for complete examples.

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
| `multimodal` | pydantic-ai, matplotlib | Tasks with chart/image generation |
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

Tools can return images to the agent for multimodal self-review. Declare `returns_image = true` in task.toml:

```toml
[[environment.tools]]
name = "create_chart"
source = "tools/create_chart.py"
description = "Generate a chart from computed data."
returns_image = true
```

The tool script prints `IMAGE:/path/to/file.png` to stdout. The PydanticAI agent detects this, reads the image, and injects it into the conversation so the model can visually review its own output.

### How it works

```
Agent computes values → calls create_chart tool → tool generates PNG
→ tool prints IMAGE:/workspace/chart.png → agent sees the chart
→ agent reviews visually → submits final answer
```

This requires the `pydantic_ai` adapter (`--adapter pydantic_ai`).

---

## Quick Reference

| Command | Purpose |
|---------|---------|
| `aec-bench init` | Set up a new project |
| `aec-bench search <query>` | Find templates and seeds |
| `aec-bench generate list-templates` | List available templates |
| `aec-bench generate task <name>` | Generate instances from a template |
| `aec-bench generate dataset --config suite.toml` | Generate a full dataset |
| `aec-bench generate dockerfiles tasks/` | Regenerate Dockerfiles from extensions |
| `aec-bench generate validate-template <dir>` | Validate a template |
| `aec-bench run <path> --model <model>` | Run an experiment |
| `aec-bench evaluate` | Score and summarise results |
| `aec-bench report` | Generate analysis reports |
| `aec-bench tui` | Interactive terminal UI |
| `aec-bench config` | View/manage configuration |
