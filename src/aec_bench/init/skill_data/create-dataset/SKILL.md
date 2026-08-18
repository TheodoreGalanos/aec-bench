---
name: create-dataset
description: Create and publish a benchmark dataset interactively. Discovers templates and tasks, guides selection and configuration, generates instances if needed, creates a semantic manifest, publishes an immutable reference, and verifies integrity. Use when the user wants to create, build, or publish a dataset.
---

# Create Dataset

Create a semantic dataset manifest and publish one immutable Git or detached-bundle reference through guided discovery and configuration.

## When to Use

- User explicitly invokes Create Dataset
- User asks to "create a dataset", "build a benchmark", "freeze tasks into a dataset"
- User wants to publish a benchmark or create a reproducible evaluation set

## Process

### Step 1 — Detect Context

Read `aec-bench.toml` to resolve project paths. If it doesn't exist, tell the user to run `aec-bench init` first and stop.

Scan the project:
- Run `aec-bench generate list-templates` to see available templates
- Run `aec-bench dataset list` to see existing datasets
- Count tasks on disk by discipline (scan `tasks/` directory)

Show the user what's available using the live command output. Do not copy fixed
catalogue counts into the response:

```
Templates available: <live total grouped by discipline>
Tasks on disk: <live instance count>
Existing datasets: <live dataset count>
```

### Step 2 — Strategy Selection

Ask the user which approach they want:

> **How do you want to build this dataset?**
>
> A. **From templates** — Generate fresh task instances from templates (recommended for new benchmarks)
> B. **From existing tasks** — Freeze the tasks already on disk into a dataset
> C. **Mixed** — Generate some new instances and include existing ones

### Step 3 — Template Selection (if A or C)

If generating from templates, show available templates grouped by discipline:

```text
Ground:
  terzaghi-bearing-capacity, spt-corrections, infinite-slope, ...
Electrical:
  voltage-drop, cable-sizing, fault-current, ...
Civil:
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

> **Dataset ID?** (e.g., `aec-bench-electrical`, `full-benchmark`)

> **Publication label?** (e.g., `public-2026`, `qualification-set`)

> **One-line summary?** (e.g., "200 tasks across 5 AEC domains for AI agent evaluation")

### Step 5 — Generate, Create, and Publish

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
   aec-bench generate suite --config suite.toml --seed 42
   ```

2. **Create the dataset manifest**:
   ```bash
   aec-bench dataset create "<dataset_id>" --from-suite-output <manifest_path> --description "<summary>"
   ```
   Use the `manifest_path` returned by `generate suite` for `<manifest_path>`.

3. **Publish an immutable bundle reference**:
   ```bash
   aec-bench dataset publish <dataset_id> --label <label>
   ```

4. **Verify integrity**:
   ```bash
   aec-bench dataset validate <dataset_id>@<label>
   ```

5. **Show the result**:
   ```bash
   aec-bench dataset info <dataset_id>@<label>
   ```

### Step 6 — Next Steps

After successful creation, suggest:

> Dataset created! Next steps:
>
> - **Run an experiment:** `aec-bench run --config experiment.yaml` (reference this dataset in the tasks section)
> - **Export for sharing:** `aec-bench dataset export <dataset_id>@<label> --output <dataset_id>.tar.gz`
> - **Configure an experiment:** invoke Configure Experiment, which will discover this dataset

Show how to reference the dataset in an experiment config:

```yaml
experiment_id: eval-sonnet-on-<name>
tasks:
  dataset: "<dataset_id>@<label>"
agents:
  - name: sonnet-tool-loop
    adapter: tool_loop
    model: claude-sonnet-4-20250514
compute:
  backend: modal
```

## Key Rules

- Always publish first, then verify the exact reference with `aec-bench dataset validate`
- Never use `latest` as a publication label or persisted selector
- Suggest meaningful names — avoid generic names like "test" or "dataset1"
- Default seed to 42 for reproducibility unless the user specifies otherwise
- If the user has no templates, suggest Create Template first
- If the user has no tasks and no templates, suggest Add Task first
