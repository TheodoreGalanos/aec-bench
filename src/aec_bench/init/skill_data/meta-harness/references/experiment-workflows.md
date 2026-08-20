# Experiment Workflows

Choose the smallest workflow that can answer the research question. Planning and
validation are provider-free; model execution is not.

For direct Python composition, use
`aec_bench.experimentation.meta_harness`. Supply caller-owned candidate values,
an evaluator that returns `TrialRecord` values, and the assessment, selection,
refinement, and stop functions required by the study. Always set `max_rounds`
for an iterative run. Do not add a generic runtime or persisted workflow file.

## 1. Candidate-versus-baseline smoke comparison

Use this to verify an installation or learn the artifact shape:

```bash
aec-bench meta-harness example \
  --output artefacts/meta-harness/example
```

This is deterministic and makes no model, Harbor, Morph, Modal, or cloud call.

## 2. Evidence-lifecycle ablation

After `aec-bench init`, copy the example from the installed `meta-harness`
skill directory. Choose the command for your agent harness.

For Codex:

```bash
cp .agents/skills/meta-harness/examples/lifecycle-ablation.yaml experiment.yaml
```

For Claude Code:

```bash
cp .claude/skills/meta-harness/examples/lifecycle-ablation.yaml experiment.yaml
```

Replace `replace-with-your-model`, review the output and ledger roots, then
inspect the exact trial plan without writing runs or calling a model:

```bash
aec-bench meta-harness lifecycle-ablation \
  --config experiment.yaml \
  --dry-run
```

Remove `--dry-run` only after the manifest, budgets, provider configuration, and
output paths have been reviewed.

## 3. Fixed-K candidate search

Use a strict, preregistered `HarnessProgramStudySpec` when comparing fixed and
candidate harnesses under matched budgets:

```bash
uv run python -m aec_bench.experimentation.qualification.harness_program_study_cli \
  --spec harness-program-study.json \
  --project-root . \
  --repo-root . \
  --tasks-root tasks
```

This runner uses real Harbor execution and requires the providers and backends
declared by the spec. It has no implicit demo or mock execution mode.

## 4. Repair-only and adaptive-cycle runs

Run a preregistered paired repair:

```bash
uv run python -m aec_bench.experimentation.qualification.repair_cli \
  --spec repair.json
```

Run a complete adaptive cycle:

```bash
uv run python -m aec_bench.experimentation.qualification.adaptive_cycle_cli \
  --spec adaptive-cycle.json
```

Both commands use real Harbor execution unless an executor is injected by a
test. Do not treat provider-free contract tests as evidence of learned harnesses,
successful repair, transfer, or generalisation.

## Experiment checklist

Before execution, confirm:

- the task identities and snapshots are frozen;
- fixed and candidate harnesses use matched budgets;
- proposer inputs exclude verifier, reward, oracle, and held-out metadata;
- output and ledger roots are new or intentionally resumable;
- model and backend credentials are configured;
- the preregistered spec validates locally;
- the result will be imported as durable TrialRecord evidence.
