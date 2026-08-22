# LS-04A — Local Artifact-Task Learning Adapter

**Status:** Proposed
**Type:** Implementation PRD
**Release:** Learning Studies Release A
**Depends on:** LS-01A, LS-01B, LS-02A, LS-02B, and LS-03
**Blocks:** Artifact pilot execution and Gate A
**Primary owner:** `aec_bench.experimentation.learning_studies`
**Execution owner reused:** Existing local artifact-task harness
**Repository baseline:** `main`, reviewed 22 August 2026

## 1. Purpose

Bind the runtime-neutral learning-study substrate to ordinary local artifact-task execution.

The adapter must let a fixed model encounter several artifact trials while carrying only explicitly permitted external learner artifacts. It must preserve the existing artifact task’s instruction, environment, verifier, selection, and `TrialRecord` semantics.

This is the first real integration and should remain deliberately narrow.

## 2. Current artifact-task behaviour

The current local artifact path already provides:

- a fresh task workspace;
- optional `agent_files` copied into that workspace;
- one or more tracked attempts;
- selection of one attempt;
- one verifier execution against the selected workspace;
- an actor-visible snapshot taken separately from verifier evidence;
- publication of workspace artifacts into an ordinary `TrialRecord`;
- cleanup of attempt workspaces by default.

The learning adapter needs two additional capabilities:

1. inject an exact learner-state projection into each new task workspace;
2. recover the exact selected actor workspace before cleanup so a permitted post-task learner state can be constructed.

The adapter must not infer the selected attempt from internal workspace ordering.

## 3. Goals

1. Implement the LS-01B callback bundle for local artifact tasks.
2. Support reset, raw-history, structured-memory, and explicit harness-update treatments.
3. Keep model weights fixed.
4. Use ordinary `PlannedTrial`, local execution, verification, and `TrialRecord` output.
5. Carry only allowlisted learner channels between experiences.
6. Release only declared public feedback views.
7. Run explicit consolidation in a clean, bounded workspace.
8. Export the exact selected actor snapshot through a narrow execution-owner seam.
9. Reject unsupported attempt policies and backends rather than approximating them.
10. Prove probe and cross-arm isolation on the filesystem.

## 4. Non-goals

Release A does not support:

- Harbor or remote backend learner persistence;
- model-weight updates;
- arbitrary full-workspace continuation;
- automatic memory summarisation without a declared consolidation step;
- best-of or retry policies whose learner-state semantics are ambiguous;
- lifecycle or world execution;
- adaptive curricula;
- hidden verifier feedback;
- concurrent arm execution.

## 5. Adapter placement

Add:

```text
src/aec_bench/experimentation/learning_studies/artifact_tasks.py
```

This adapter may import the public artifact-task harness API.

The artifact harness must not import learning-study code.

## 6. Required narrow harness seam

### 6.1 Problem

`run_trial()` returns a `TrialRecord`, while its selected workspace is internal and ordinarily cleaned up. A learning adapter cannot safely reconstruct learner state from:

- the last attempt workspace;
- verifier logs;
- trial output artifacts alone;
- undocumented runtime internals.

Selection may differ from attempt order, and verifier execution must remain separate from the actor-visible workspace.

### 6.2 Decision

Add one optional caller-owned export parameter to the existing artifact runner, conceptually:

```python
run_trial(
    ...,
    selected_workspace_export: Path | None = None,
) -> TrialRecord
```

When supplied, the artifact execution owner:

1. selects the winning attempt through existing policy;
2. creates the same actor-visible snapshot used for artifact publication;
3. copies that exact snapshot atomically to the caller-owned empty destination;
4. runs verification according to existing semantics;
5. returns the ordinary `TrialRecord`;
6. cleans internal attempt workspaces normally.

Rules:

- the export destination must not already contain files;
- the exported snapshot is created before verifier-only files are introduced;
- export failure is an execution failure and cannot silently produce a learning transition;
- existing callers that omit the parameter behave identically;
- the harness remains unaware of learner treatments or study policy.

If repository implementation makes a callback safer than a path argument, the agent may use a single narrow selected-snapshot consumer, but it must expose the exact selected actor snapshot and retain the same ownership boundary.

## 7. Learner-state layout

The artifact adapter owns a portable state directory with one reserved namespace:

```text
.aec-bench-learning/
  history/
  memory/
  harness/
    prompts/
    skills/
  feedback/
```

The namespace is staged into a task workspace as agent-visible files according to treatment policy.

It must never contain:

- hidden task files;
- verifier source or expected answers;
- provider credentials;
- absolute host paths;
- another arm’s data;
- arbitrary files copied from a prior task workspace.

The learner-state snapshot contains only this namespace. The full selected task workspace remains ordinary trial evidence, not persistent learner state.

## 8. Treatment definitions

Treatments are artifact-adapter-owned values addressed by `treatment_id`.

### 8.1 `reset`

```text
history: absent
memory: absent
harness: initial fixed artifacts only
feedback: absent
```

Each experience begins from the declared initial agent and no prior experience artifacts.

Used for cold controls.

### 8.2 `raw-history`

Carries an append-only, public episode history containing only:

- source experience ID;
- public task instruction or safe task summary;
- selected public output files or references;
- released terminal outcome or public evaluation;
- no verifier internals.

History entries are written by the adapter after an explicit feedback-release step. The agent does not receive unreleased host evidence.

The raw-history treatment does not automatically create a summary or reusable skill.

### 8.3 `structured-memory`

Carries:

```text
memory/
```

The memory channel is:

- readable during task execution;
- writable only during an explicit consolidation step in Release A;
- absent or empty initially unless the study declares a common initial memory;
- copied forward exactly after a committed consolidation.

This treatment tests whether deliberate compression is more useful than raw episode history.

### 8.4 `explicit-harness-update`

Carries allowlisted:

```text
harness/prompts/
harness/skills/
```

A consolidation step may update these artifacts.

Constraints:

- model identifier, client kind, and model weights remain fixed;
- the original study `AgentConfig` remains immutable;
- the adapter constructs an effective per-experience agent configuration from the initial config plus committed harness artifacts;
- every update receives a learner-transition receipt;
- no code, executable, package, or provider configuration may be added through this channel in Release A.

## 9. Channel permissions

Define treatment permissions centrally in the artifact adapter rather than scattering path checks.

| Step | History | Memory | Harness | Feedback |
|---|---|---|---|---|
| Task execution, reset | absent | absent | fixed initial only | absent |
| Task execution, raw history | read | absent | fixed initial only | read if released |
| Task execution, structured memory | optional read history | read | fixed initial only | read if released |
| Task execution, harness update | optional read history | read | read | read if released |
| Feedback release | adapter append | unchanged | unchanged | adapter append |
| Consolidation, structured memory | read | write | unchanged | read |
| Consolidation, harness update | read | optional write | write | read |

After every task or consolidation execution, compare the resulting reserved namespace against permissions. An undeclared write invalidates the candidate learner-state transition even when the task trial itself remains a valid ordinary `TrialRecord`.

## 10. Initial learner state

For each arm run, `initialise_learner`:

1. creates a unique arm-owned root;
2. creates the reserved namespace;
3. copies only declared initial prompt or skill artifacts needed by the treatment;
4. writes no task input, feedback, or prior trial record;
5. returns a unique `LearnerStateHandle`;
6. provides a snapshot directory suitable for LS-02A publication.

No two arm runs share writable directories or hard links.

## 11. Experience execution

For each compiled `RunExperienceStep`:

1. materialise the current learner-state snapshot into a new arm-and-step staging area;
2. prepare `agent_files` from the treatment’s readable channels;
3. construct the effective agent configuration without mutating the study spec;
4. invoke ordinary local artifact execution with the exact `PlannedTrial`;
5. request export of the exact selected actor workspace;
6. inspect only the reserved learner namespace in that exported workspace;
7. validate channel writes against treatment policy;
8. construct a new candidate learner-state directory from permitted changes;
9. return the ordinary `TrialRecord` and candidate state;
10. leave commit or discard to the common runtime and recorder.

The adapter does not run the verifier itself and does not alter its result.

## 12. Attempt policy

Release A supports the simplest existing single-attempt policy only.

Reject plans using:

- best-of selection;
- retry with model feedback;
- multi-attempt learner-state aggregation;
- policies where more than one attempt could modify persistent learner artifacts.

The selected-workspace export seam is designed to permit later extension, but Release A should first prove one experience equals one unambiguous agent attempt and one trial.

## 13. Feedback views

Support these view IDs initially.

### 13.1 `terminal-outcome`

May include:

- trial status;
- canonical public reward;
- whether required output was produced;
- public failure category where already exposed.

### 13.2 `public-evaluation`

Uses a task- or study-owned projector to create a safe feedback artifact from public evaluation evidence.

The projector must explicitly select fields. Do not serialise the entire evaluation payload by default.

### 13.3 `task-explanation`

Available only when the task owner publishes a dedicated learner-safe explanation or failure-analysis artifact.

Absence is a supported condition. Do not generate an explanation by exposing verifier source or expected output.

### 13.4 Release operation

A feedback release:

1. reads host-held evidence for the source trial;
2. invokes the selected projector;
3. writes a public artifact under `feedback/<feedback_id>/`;
4. optionally appends a raw-history entry when the treatment permits it;
5. returns a new learner state and a `FeedbackHandle`;
6. records public artifact references through LS-02A.

## 14. Consolidation execution

Consolidation is a separate bounded agent operation, not a benchmark trial.

### 14.1 Consolidation workspace

Create a clean workspace containing only:

- the current permitted learner-state channels;
- the feedback handles referenced by the step;
- a study-owned consolidation instruction;
- declared output directories.

Do not include:

- original hidden task files;
- verifier implementation;
- expected answer;
- unrelated prior feedback;
- probe-only task content.

### 14.2 Consolidation instruction

The operation ID selects one adapter-owned instruction, for example:

```text
update-structured-memory
update-harness-artifacts
```

Instructions must require the model to write bounded files rather than returning an untracked prose answer.

### 14.3 Output validation

- only permitted channels may change;
- paths must remain within the reserved namespace;
- symlinks and executables are rejected;
- output file and total-byte limits are enforced;
- prompt and skill updates remain plain text or another explicitly allowed static format;
- no model or client configuration changes are accepted.

### 14.4 Usage evidence

Record model calls, tokens, cost, and elapsed time when the existing adapter exposes them. Attach this to the learner-transition evidence rather than synthesising a `TrialRecord`.

## 15. Probe handling

For a probe experience:

- execute the task normally from the current committed learner state;
- withhold evaluation until the trial record is complete;
- construct a candidate state as usual for audit;
- discard that candidate when `commit_post_state` is false;
- do not write probe output, notes, or evaluation into the committed learner state;
- remove the candidate workspace after its discard receipt is persisted.

This must be proven with filesystem assertions, not only state IDs.

## 16. Local backend only

Release A supports the current local artifact runtime because it can:

- create isolated workspaces;
- stage exact agent files;
- export selected actor state;
- preserve staging directories for atomic commit and resume.

Reject other compute backends with `LearningStudyFeatureUnsupported` until they provide equivalent explicit state semantics.

Do not simulate persistence by scraping remote logs.

## 17. Adapter API

Provide a builder such as:

```python
def build_artifact_learning_operations(
    *,
    tasks_root: Path,
    run_root: Path,
    treatment_specs: Mapping[str, ArtifactLearningTreatment],
    feedback_projectors: Mapping[str, ArtifactFeedbackProjector],
    consolidation_operations: Mapping[str, ConsolidationOperation],
) -> LearningStudyOperations[ArtifactLearnerState, ArtifactFeedback]:
    ...
```

Treatment, projector, and consolidation maps are supplied explicitly. Avoid a global plugin registry.

## 18. Failure taxonomy

At minimum:

```text
artifact-backend-unsupported
artifact-attempt-policy-unsupported
selected-workspace-export-failed
learner-namespace-missing
learner-channel-write-forbidden
learner-path-unsafe
feedback-view-unsupported
feedback-projection-failed
feedback-leak-detected
consolidation-operation-unsupported
consolidation-output-invalid
harness-update-forbidden
probe-state-contaminated
cross-arm-path-detected
```

A learner-state transition failure does not rewrite the task’s `TrialRecord` status. It fails the study step separately.

## 19. File changes

Expected additions:

```text
src/aec_bench/experimentation/learning_studies/artifact_tasks.py
tests/experimentation/learning_studies/test_artifact_tasks.py
tests/experimentation/learning_studies/test_artifact_isolation.py
tests/experimentation/learning_studies/test_artifact_feedback.py
tests/experimentation/learning_studies/test_artifact_consolidation.py
```

Expected narrow modification:

```text
src/aec_bench/harness/artifact_tasks.py
```

Only to export the exact selected actor snapshot through a general caller-owned seam. It must not import experimentation or treatment concepts.

## 20. Test matrix

### Harness seam tests

- omitted export argument preserves existing behaviour;
- exported directory exactly matches the selected actor snapshot;
- non-selected attempt files are absent;
- verifier-only files are absent;
- non-empty destination rejected;
- internal cleanup still occurs.

### Treatment tests

- reset carries nothing;
- raw history includes only released public content;
- structured memory survives acquisition-to-probe;
- harness update changes only allowed prompt/skill files;
- model/client remain fixed;
- forbidden channel write rejects transition.

### Arm isolation tests

- separate roots and inodes for every arm run;
- no shared writable hard links;
- control cannot read exposure memory;
- repetition state resets;
- one arm cleanup cannot delete another state.

### Feedback tests

- unreleased evaluation absent;
- terminal outcome view contains only allowlisted fields;
- public evaluation uses projector output;
- task explanation unavailable when no safe artifact exists;
- probe evaluation withheld until scoring.

### Consolidation tests

- clean workspace contains only declared inputs;
- unrelated feedback absent;
- output limits enforced;
- symlink and executable rejected;
- transition usage recorded where available;
- reflective prose alone does not count as a learning result.

### Probe tests

- candidate state records task-created changes;
- candidate is discarded;
- committed parent state remains byte-identical;
- later step cannot read probe files;
- discard survives resume.

### Regression tests

- ordinary artifact trials remain unchanged;
- existing `run_trial()` callers require no changes;
- task verifiers and rewards remain authoritative;
- no new `TrialRecord` fields.

## 21. Acceptance criteria

LS-04A is complete when:

1. A compiled artifact study executes through the common runtime and returns ordinary `TrialRecord` values.
2. Reset, raw-history, structured-memory, and explicit-harness-update treatments are implemented with distinct declared channels.
3. The exact selected actor snapshot is available through a narrow harness-owned export seam.
4. Learner state contains only the reserved allowlisted namespace.
5. Feedback is released explicitly and excludes verifier secrets.
6. Consolidation runs in a clean bounded workspace and produces a recorded learner transition.
7. Probe-created state is discarded and proven inaccessible to later steps.
8. Cross-arm and cross-repetition filesystem isolation is proven.
9. Unsupported backends and attempt policies fail explicitly.
10. Existing artifact execution remains unchanged when the learning adapter is unused.

## 22. Agent handoff

The implementation agent should return:

- final selected-workspace export API;
- treatment definitions and path permissions;
- learner-state directory example before and after each step kind;
- feedback projector inventory;
- consolidation input/output contract;
- isolation and probe-contamination test evidence;
- confirmation that the model, verifier, task semantics, and `TrialRecord` schema remain unchanged.
