# ABOUTME: Explains the SSC-03 successor lifecycle where a model-selected intervention changes the hydraulic source.
# ABOUTME: Separates deterministic task evidence from model performance, post-training, and continual learning claims.

# SSC-03 Model-Selected Hydraulic Intervention

## The short version

The PR19 task lets a model run declared calculations after the host issues a source revision. The source changes, but
the model does not choose that change.

This successor task adds one missing step: the model must choose one of two bounded design responses before seeing its
calculated outcome. That archived choice controls which exact hydraulic source becomes active. Later calculations,
decisions, and the closeout memo must all follow the chosen source.

This is a richer fixed-model environment. It is not post-training or continual learning.

## The four checkpoints

| Checkpoint | Plain-language job |
| --- | --- |
| `problem_analysis` | Run both scenarios and diagnose the issued major-rainfall problem. |
| `intervention_selection` | Read two public intervention descriptions and commit to exactly one. |
| `intervention_analysis` | Activate only that archived choice, reuse unchanged hydrology, and recompute the affected calculations. |
| `closeout_review` | Carry the selected option, current source, runs, reports, decisions, and readiness into one final record. |

The selection checkpoint deliberately exposes the declared physical changes but not their calculated outcomes. The
host archives the submission before it releases the intervention-analysis checkpoint. Changing the archived choice
later is rejected.

## The issued problem

The task starts from the public major-rainfall revision. The design event passes. The major event has two coupled
problems:

- minimum freeboard is `0.289305 m`, below the declared `0.30 m` minimum; and
- peak structured outflow is `1.620433 m³/s`, slightly above the first pipe's capacity.

The reviewer therefore needs to consider both the basin and the downstream network. Fixing only the most visible local
symptom may move the problem elsewhere.

## The bounded choices

| Intervention | Declared physical change | Deterministic consequence after selection |
| --- | --- | --- |
| `controlled_orifice_resize` | Increase the controlled-orifice diameter from `0.42 m` to `0.48 m`. | Both scenarios satisfy every declared screening criterion. |
| `emergency_weir_enlargement` | Increase the emergency-weir length from `4.2 m` to `5.5 m`. | Major-event freeboard passes, but the greater downstream flow still exceeds pipe capacity. |

The second option is intentionally plausible. It improves the basin result, but the coupled network calculation exposes
the remaining consequence. The task is not asking the model to avoid an obviously silly answer.

## What the host records

The model still uses the existing bounded operation call:

```text
execute_operation(
  checkpoint_id,
  operation_id,
  visible_source_state_sha256,
  reason
)
```

At intervention analysis, `source-intervention.selected` is the only source-changing operation. The resolver reads the
immutable selection submission, rejects undeclared option IDs, and binds all of the following into the activation:

- the selected intervention ID;
- the selection-submission hash;
- the problem-source fingerprints;
- the selected option-source fingerprints; and
- the resulting model-visible source identity.

Neither the model nor the CLI can supply arbitrary outlet geometry, source paths, or expected answers.

Because both options change only the outlet section, the dependency behavior is exact:

```text
hydrology                    -> already current, zero budget
detention and outlet         -> recomputed
downstream HGL and capacity  -> recomputed
```

## Honest failure and task completion are separate

The verifier has a distinct `intervention_effectiveness` gate.

If the reviewer selects the larger emergency weir and accurately reports the remaining pipe-capacity failure, its
source grounding, calculations, decisions, readiness, and closeout can all be correct. Those gates pass. The task still
does not pass overall because the selected intervention did not solve every declared criterion. Its scalar reward is
capped at `0.5`, so correct paperwork around an ineffective intervention cannot look nearly equivalent to task success.

This prevents two bad incentives:

- pretending that a physically inadequate option succeeded; and
- treating an honest diagnosis as though it completed the design-response objective.

## Run the complete credential-free task proof

From the repository root:

```bash
uv run aec-bench --json task composite-template materialize-lifecycle \
  hydraulic-design-response-lifecycle-review \
  --output /tmp/ssc03-intervention-package

uv run aec-bench --json task composite-template run-lifecycle-smoke \
  /tmp/ssc03-intervention-package \
  --run-dir /tmp/ssc03-intervention-run
```

The second command runs the default feasible policy through the real lifecycle host, operation store, deterministic
hydraulic engine, immutable submissions, and task-owned verifier. It makes no provider call and is not model-performance
evidence.

A real fixed-model run can use the same package through `lifecycle-run-local` or the local Prime lifecycle export. That
later run requires the separately approved provider configuration and must be reported as a pilot or campaign result,
not inferred from the deterministic smoke.

## What this establishes

- A model-controlled bounded choice can select a different physical source state.
- Two runs from the same problem can produce divergent, attributable hydraulic consequences.
- The prior selection cannot be changed after submission.
- Dependency-aware reuse and recomputation continue to work after the model-selected transition.
- The task verifier can distinguish correct reporting from successful intervention choice.

## What it does not establish

- that a real language model chooses the feasible option reliably;
- project design quality or authority approval;
- SWMM equivalence;
- transfer to a distinct target;
- an effect of post-training; or
- continual learning across encounters.

The next richer mechanic should add a scarce diagnostic choice before intervention selection, or introduce explicit
time-evolving world state for stepwise control. The latter needs a separate world-state protocol rather than pretending
that runtime storage and flow are static source files.
