# Lifecycle Studies

Copy the installed example for the selected agent harness:

```bash
cp .agents/skills/lifecycle/examples/lifecycle-ablation.yaml experiment.yaml
```

For Claude Code, use `.claude/skills/lifecycle/examples/lifecycle-ablation.yaml`.
Replace `replace-with-your-model`, then review the roots, finite trial limit, and per-session turn budget.

Inspect the exact plan without writing runs or calling a model:

```bash
aec-bench task lifecycle study ablation \
  --config experiment.yaml \
  --dry-run
```

Remove `--dry-run` only after the execution condition and provider configuration are approved.
Freeze a completed public calibration with:

```bash
aec-bench task lifecycle study calibration-freeze --config experiment.yaml
```

The ablation uses normal lifecycle trial execution. The study keeps its own immutable snapshot, recovery, and selection policy.
