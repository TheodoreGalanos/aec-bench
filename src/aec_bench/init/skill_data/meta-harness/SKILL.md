---
name: meta-harness
description: Guide an agent through creating or revising a task-world harness, running it against a baseline, reviewing evidence, and preparing a comparison. Use when the user wants to create a harness from prose, compare a candidate harness to an existing one, or investigate verifier/schema gaps.
---

# Meta-Harness

Guide a user through the meta-harness workflow without turning the library into a chat system. The skill operates the CLI/API, preserves artifacts, and stops for governance when the evidence calls for a world or schema change.

## Provider-Free Quick Start

Verify the installed meta-harness before configuring Harbor or a model:

```bash
aec-bench meta-harness example \
  --output artefacts/meta-harness/example
```

The command writes a complete baseline, candidate, evidence pair, recipe, and
comparison. Reproduce the deterministic comparison with:

```bash
artefacts/meta-harness/example/run_recipe.sh
```

This proves artifact production and comparison only. It does not claim that a
harness was learned or that an agent generalised.

## When to Use

- User explicitly invokes Meta-Harness or asks to create a harness from task prose.
- User wants to compare a candidate harness against an existing task, world, or experiment.
- User suspects the verifier, schema, artifacts, or review language is missing a real edge case.

## Process

### Step 1 - Detect Context

Read `aec-bench.toml`. If it is missing, tell the user to run `aec-bench init` first and stop.

Inspect the repo enough to identify:
- existing `tasks/` and candidate task files;
- existing experiment YAML files;
- existing task-world files such as `world.yaml`, `world.json`, or task-local evidence artifacts;
- recent `jobs/` or `artefacts/ledger/` outputs that could serve as baseline evidence.

### Step 2 - Capture the Task Request

If the user supplied prose or files, preserve them. If not, ask for a short task description and what existing harness or experiment should be treated as the baseline.

Do not require a structured brief up front. The first structured artifact is the `problem_space_brief` produced or reviewed through the meta-harness intake step.

### Step 3 - Materialize a Recipe Workspace

Read `references/cli-workflow.md`.

Create a recipe workspace with:

```bash
aec-bench meta-harness recipe \
  --task-file task.md \
  --baseline-world baseline-world.json \
  --baseline-run baseline-run.json \
  --candidate-world candidate-world.json \
  --candidate-run candidate-run.json \
  --output artefacts/meta-harness/<short-id>
```

If some paths are not available yet, still create the recipe and leave placeholders. Tell the user exactly which artifacts must be filled before comparison.

The generated `run_recipe.sh` deliberately runs only the provider-free comparison.
Use the staged commands in `recipe.json` to create any missing inputs first.

### Step 4 - Build or Revise the Candidate World

Use the recipe commands or direct CLI calls to create the intake packet and candidate world. If model endpoints are available, use the model-backed commands. If not, emit requests and ask the user or their agent to supply the structured artifacts.

Never invent verifier outputs or task-run evidence. Missing run evidence means the process is paused, not complete.

### Step 5 - Execute Baseline and Candidate Runs

Run candidate and baseline through native AEC-Bench execution where possible. Prefer `aec-bench run` and Harbor-backed imports over bespoke scripts.

Read `references/evidence-contract.md` before comparing outputs.
Read `references/experiment-workflows.md` before starting a new controlled
experiment or fixed-K adaptive cycle.

### Step 6 - Review, Evaluate, and Compare

Run the reviewer when configured. Then use `aec-bench meta-harness compare` or
the generated `run_recipe.sh` to write:

- `comparison/comparison.json`
- `comparison/comparison.md`

Report the reward delta, score delta, event-candidate delta, artifact-count delta, and recommendation.

### Step 7 - Governance Stop

Read `references/governance-rules.md`.

If the comparison produces event candidates, verifier-language gaps, schema gaps, missing handles, or world-generator changes, stop and ask for a governance decision. Do not mutate the world or verifier silently.

## Output

The expected output is a recipe directory with durable artifacts and a short final summary:

- recipe path;
- baseline and candidate inputs used;
- comparison outputs;
- any governance proposal or unresolved evidence gap.

## Reference Files

Read these during execution:

- `references/cli-workflow.md` - command flow and recipe workspace shape
- `references/evidence-contract.md` - required comparison evidence
- `references/experiment-workflows.md` - provider-free planning and real experiment runners
- `references/governance-rules.md` - when to stop for review or regeneration
