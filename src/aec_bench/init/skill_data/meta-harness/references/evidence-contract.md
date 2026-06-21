# Evidence Contract

Compare candidate and baseline only after both sides have explicit world and task-run artifacts.

## Required Inputs

- `brief.json`: problem-space brief with `brief_id`, `objective`, `task_request`, and `evidence_requirements`.
- `baseline-world.json`: existing task-world profile.
- `candidate-world.json`: candidate task-world profile.
- `baseline-run.json`: task-run evidence from the baseline.
- `candidate-run.json`: task-run evidence from the candidate.

## Task-Run Evidence

Each task-run should contain:

- `run_id`
- `evidence.score.passed` or `evidence.score.reward`
- `evidence.artifacts` for verifier outputs, reports, traces, or preserved files
- `evidence.agentic_review` when the reviewer has run

If reviewer evidence is missing, say that comparison is provisional. Do not fabricate reviewer findings.

## Comparison Outputs

The comparison reports:

- deterministic logic status for each side;
- meta-harness score for each side;
- reward delta;
- event-candidate delta;
- artifact-count delta;
- recommendation.

Treat additional event candidates as governance pressure, not automatic failure.
