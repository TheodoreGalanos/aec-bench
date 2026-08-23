# L01 Deterministic Vertical-Slice Evidence

| Field | Value |
| --- | --- |
| Class | Research |
| Status | Research |
| Study | `l01-lifecycle-staged-evidence-transfer` |
| Scope | Deterministic infrastructure and isolation proof |

This record packages the evidence required to start the mandatory L01
architecture review. It is not a learning-effect result. The deterministic
adapter submits the task-owned gold response only to prove that the complete
execution, recording, feedback, memory, projection, and assessment path works.

## Fixed protocol

L01 uses these existing lifecycle tasks:

- acquisition:
  `lifecycle/drainage-model-evidence-lifecycle-review/staged_full_correction`;
- probe:
  `lifecycle/drainage-model-evidence-lifecycle-review/semantic_no_op_release`.

All arms use `fresh_context` with `artifact_memory`. The adapter identity is
`lifecycle-local:fresh_context:artifact_memory`.

The maintained protocol has three arms:

- `cold-reset`: probe only;
- `reset-after-acquisition`: acquisition, complete reset, then probe;
- `structured-memory`: acquisition, safe feedback, structured consolidation,
  then probe with read-only `learner_context/`.

Every measured probe has `commit_post_state=false`.

## Feedback boundary

The structured arm releases
`drainage-staged-review-public-feedback` after the acquisition. The exact
top-level fields are:

```text
feedback_view_id
trial_id
task_id
execution_status
terminal_outcome
review_gates
checkpoint_submissions
review_principles
```

`review_gates` contains only `passed` and `score` for the selected public gates.
`checkpoint_submissions` contains the learner's validated archived submissions
for `initial_review`, `response_review`, and `closeout_review`.

The projector deliberately excludes validity errors, raw gate failures, gold
files, verifier configuration, metrics, manifests, trajectories, package and
run paths, unreleased evidence, and probe details. The adapter rejects invalid
JSON, excess size, forbidden keys, absolute paths, hidden paths, and package or
run roots before it creates candidate state or publishes an artifact.

## Outcome projections

The study supplies these callbacks directly to the unchanged common assessor:

| Projection ID | Existing evidence source |
| --- | --- |
| `lifecycle.canonical-reward` | `TrialRecord.evaluation.reward` |
| `drainage.staged-disclosure` | `evaluation.breakdown.lifecycle_gates.staged_disclosure.score` |
| `drainage.finding-continuity` | `evaluation.breakdown.lifecycle_gates.finding_continuity.score` |
| `drainage.closure-evidence` | `evaluation.breakdown.lifecycle_gates.closure_evidence.score` |
| `drainage.claim-boundary` | `evaluation.breakdown.lifecycle_gates.claim_boundary.score` |

The existing lifecycle record and drainage gates were sufficient. B3 added no
new task evidence model, common phase contract, or `TrialRecord` field. Missing,
malformed, non-finite, or out-of-range values are ineligible and remain absent;
they are not changed to `0.0`.

## Deterministic result

The deterministic proof produced five complete lifecycle `TrialRecord` values:
one in the cold arm and two in each acquisition arm. Each lifecycle used three
fresh checkpoint sessions.

The fixture reached reward and selected gate score `1.0` in every probe. Each
structured-memory versus cold pair therefore had:

```text
focal_value      1.0
comparator_value 1.0
normalised_effect 0.0
```

The reset-after-acquisition versus cold canonical pair also had effect `0.0`.
These ceiling values are expected from a gold deterministic fixture and support
no behavioural claim.

With `relations_reviewed=false`, every measurement was `descriptive_only`.
With `relations_reviewed=true`, the five structured-memory versus cold
measurements were `controlled`; the reset-after-acquisition control comparison
remained `descriptive_only` because it is not an exposure-versus-cold contrast.

The recorded deterministic usage was 30 input tokens and 15 output tokens over
the five lifecycle trials. `estimated_cost_usd` remained `null`. No monetary
cost was inferred.

## Isolation evidence

For every arm, assessment evidence was derived from actual initial-state
references, step receipts, transition receipts, feedback records, terminal
recording, and lifecycle paths. The deterministic checks established:

- independently stored initial learner states with one equivalent content hash;
- separate arm, lifecycle package, lifecycle run, and candidate-state roots;
- complete state and transition lineage;
- no feedback release from a probe;
- memory-only `learner_context/` during the structured probe;
- discarded probe candidate state;
- no hidden file, verifier file, metrics file, probe result, or host path in
  learner state;
- exact equality between feedback state bytes and the published feedback
  artifact.

Changing `probe_state_discarded` to false or `hidden_evaluation_leaked` to true
makes the primary comparisons invalid, as required by the common assessor.

## Review boundary

The deterministic proof is complete. A paid or credentialed real-model pilot
was not run. The authored transfer relation still requires independent drainage
and benchmark review before a claim-bearing campaign.

The next action is the mandatory L01 architecture review. That review must give
one of the specified recommendations before L02 starts. B3 does not add raw
history, visibility-factor studies, scaffold withdrawal, a hydraulic study,
new phase evidence, or Gate B work.

The focused proof is executable with:

```bash
uv run pytest tests/experimentation/learning_studies/test_l01_drainage.py -q
```
