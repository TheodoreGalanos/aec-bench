# CLI Workflow

Use the CLI as a sequence of artifact-producing stages. The skill can guide the user, but the library stays scriptable.

## Verify the Installation

Run the complete provider-free example:

```bash
aec-bench meta-harness example \
  --output artefacts/meta-harness/example
```

Inspect:

- `comparison/comparison.json`
- `comparison/comparison.md`
- `recipe.json`
- `run_recipe.sh`

Run `run_recipe.sh` to reproduce the same comparison through the public CLI.

## Recipe Workspace

Create a workspace:

```bash
aec-bench meta-harness recipe \
  --task-file task.md \
  --baseline-world baseline-world.json \
  --baseline-run baseline-run.json \
  --candidate-world candidate-world.json \
  --candidate-run candidate-run.json \
  --output artefacts/meta-harness/<short-id>
```

The command writes:

- `task.md`
- `recipe.json`
- `run_recipe.sh`
- `compare_candidate.py`
- `README.md`

`run_recipe.sh` validates that the brief, baseline world/run, and candidate
world/run exist, then performs the deterministic comparison. It does not execute
placeholder experiment or provider commands.

## Stage Commands

Use intake commands to create or review the problem brief:

```bash
aec-bench meta-harness intake --task-file task.md
aec-bench meta-harness intake-models --task-file task.md --models-config models.json
```

Use the existing world-named CLI commands to create or revise the candidate
problem model. This public command vocabulary is retained for current scripts;
it does not refer to the interactive-world runtime.

```bash
aec-bench meta-harness world-request --brief brief.json
aec-bench meta-harness world-models --brief brief.json --models-config models.json
```

Use AEC-Bench execution for real runs:

```bash
aec-bench run --config candidate-experiment.yaml
aec-bench run --config baseline-experiment.yaml
```

Use reviewer and operation commands for post-run analysis:

```bash
aec-bench meta-harness review-models --world candidate-world.json --run candidate-run.json --models-config reviewer-models.json
aec-bench meta-harness operation-orchestrate --brief brief.json --world baseline-world.json --world candidate-world.json --emit-request
```

Compare after baseline and candidate evidence exist:

```bash
aec-bench meta-harness compare \
  --brief brief.json \
  --baseline-world baseline-world.json \
  --candidate-world candidate-world.json \
  --baseline-run baseline-run.json \
  --candidate-run candidate-run.json \
  --output comparison
```

For lifecycle ablations and fixed-K adaptive experiments, read
`experiment-workflows.md`.
