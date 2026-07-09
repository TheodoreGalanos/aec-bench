# CLI Workflow

Use the CLI as a sequence of artifact-producing stages. The skill can guide the user, but the library stays scriptable.

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

## Stage Commands

Use intake commands to create or review the problem brief:

```bash
aec-bench meta-harness intake --task-file task.md
aec-bench meta-harness intake-models --task-file task.md --models-config models.json
```

Use world commands to create or revise the candidate world:

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
python compare_candidate.py \
  --brief brief.json \
  --baseline-world baseline-world.json \
  --candidate-world candidate-world.json \
  --baseline-run baseline-run.json \
  --candidate-run candidate-run.json \
  --output comparison
```
