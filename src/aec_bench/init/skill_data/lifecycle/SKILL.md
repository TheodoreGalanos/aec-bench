---
name: lifecycle
description: Run, inspect, branch, verify, or study a finite AEC-Bench evidence lifecycle. Use for lifecycle packages, checkpoints, local lifecycle execution, ablation, and calibration freeze work.
---

# Lifecycle

Use `aec-bench task lifecycle` for all lifecycle host controls and studies.
The commands are adapters over the same lifecycle application functions used by Python callers.

## Provider-Free Checks

List definitions and inspect a study plan without model execution:

```bash
aec-bench task lifecycle list
aec-bench task lifecycle study ablation --config experiment.yaml --dry-run
```

Do not remove `--dry-run` until the model, provider configuration, budgets, and output paths are approved.

## Checkpoint Rules

- Start releases the next checkpoint before actor work.
- Submit records the active checkpoint evidence.
- Status reads the canonical lifecycle state.
- Revisit reads accepted checkpoint evidence and does not change progression.
- Branch starts a new lifecycle from a submitted checkpoint and inherits the accepted prefix.
- Run continues from the current canonical state. It does not reconstruct history or bypass the coordinator.

## Studies

Read `references/studies.md` before an ablation or calibration-freeze command.

## Output

Normal trial execution returns a `TrialRecord`. Persistence is optional and explicit.
Study-specific snapshot and selection rules stay with the lifecycle study.
