---
name: create-dataset
description: Create a versioned benchmark dataset interactively. Discovers templates and tasks, guides selection and configuration, generates instances if needed, freezes into an immutable manifest, and verifies integrity. Use when the user wants to create, build, or publish a dataset.
---

# Create Dataset

Create a versioned, immutable benchmark dataset through guided discovery and configuration. Datasets are the formal "this IS the benchmark" artifact that sits between template generation and experiment execution.

## When to Use

- User runs `/create-dataset`
- User asks to "create a dataset", "build a benchmark", "freeze tasks into a dataset"
- User wants to publish a benchmark or create a reproducible evaluation set

## Process

### Step 1 — Detect Context

Read `aec-bench.toml` to resolve project paths. If it doesn't exist, tell the user to run `aec-bench init` first and stop.

Scan the project:
- Run `aec-bench generate list-templates` to see available templates
- Run `aec-bench dataset list` to see existing datasets
- Count tasks on disk by discipline (scan `tasks/` directory)

Show the user what's available:

```
Templates available: 96 across 3 domains (ground: 10, electrical: 14, civil: 72)
Tasks on disk: 6 instances
Existing datasets: 0
```

### Step 2 — Strategy Selection

Ask the user which approach they want:

> **How do you want to build this dataset?**
>
> A. **From templates** — Generate fresh task instances from templates (recommended for new benchmarks)
> B. **From existing tasks** — Freeze the tasks already on disk into a dataset
> C. **Mixed** — Generate some new instances and include existing ones

### Step 3 — Template Selection (if A or C)

If generating from templates, show available templates grouped by domain:

```
Ground (10 templates):
  terzaghi-bearing-capacity, spt-corrections, infinite-slope, ...
Electrical (14 templates):
  voltage-drop, cable-sizing, fault-current, ...
Civil (72 templates):
  rational-method, design-wind-pressure, retaining-wall-stability, ...
```

Ask which templates to include. Accept:
- "all" — every template
- Domain names — "electrical, ground"
- Specific template names — "voltage-drop, cable-sizing"

For each selected template, ask how many instances:

> **How many instances per template?**
>
> A. 3 (quick test)
> B. 5 (standard)
> C. 10 (comprehensive)
> D. Custom number

Ask about difficulty distribution:

> **Difficulty mix?**
>
> A. Balanced (equal easy/medium/hard)
> B. Weighted toward hard (20% easy, 30% medium, 50% hard)
> C. Only medium and hard
> D. Custom

### Step 4 — Dataset Identity

Ask for dataset metadata:

> **Dataset name?** (e.g., `aec-bench-electrical-v1`, `full-benchmark`)

> **Version?** (e.g., `1.0.0`)

> **One-line summary?** (e.g., "200 tasks across 5 AEC domains for AI agent evaluation")

> **Purpose?** (optional — why does this dataset exist?)

### Step 5 — Generate and Freeze

Build a `suite.toml` from the user's selections:

```toml
[[dataset]]
template = "voltage-drop"
count = 5

[[dataset]]
template = "cable-sizing"
count = 5

[settings]
seed = 42
output = "tasks"
```

Execute the pipeline:

1. **Generate instances** (if using templates):
   ```bash
   aec-bench generate dataset --config suite.toml --seed 42
   ```

2. **Create the dataset manifest**:
   ```bash
   aec-bench dataset create --config suite.toml --name "<name>" --version "<version>" --summary "<summary>"
   ```

3. **Verify integrity**:
   ```bash
   aec-bench dataset validate <name>
   ```

4. **Show the result**:
   ```bash
   aec-bench dataset info <name>
   ```

### Step 6 — Next Steps

After successful creation, suggest:

> Dataset created! Next steps:
>
> - **Run an experiment:** `aec-bench run --config experiment.yaml` (reference this dataset in the tasks section)
> - **Export for sharing:** `aec-bench dataset export <name> --output <name>.tar.gz`
> - **Configure an experiment:** `/configure-experiment` (will discover this dataset)

Show how to reference the dataset in an experiment config:

```yaml
experiment_id: eval-sonnet-on-<name>
tasks:
  dataset: "<name>@<version>"
agents:
  - name: sonnet-tool-loop
    adapter: tool_loop
    model: claude-sonnet-4-20250514
compute:
  backend: modal
```

## Key Rules

- Always verify integrity after creation with `aec-bench dataset validate`
- Suggest meaningful names — avoid generic names like "test" or "dataset1"
- Default seed to 42 for reproducibility unless the user specifies otherwise
- If the user has no templates, suggest running `/create-template` first
- If the user has no tasks and no templates, suggest `/add-task` first
