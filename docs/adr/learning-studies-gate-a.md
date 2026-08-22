# Learning Studies Gate A

| Field | Value |
| --- | --- |
| Class | Decision |
| Status | Current |
| Date | 2026-08-22 |
| Scope | Artifact-derived Learning Studies substrate |

## Decision

Gate A passes after the simplification in this change. The substrate is ready
for detailed lifecycle design. This decision does not promote any Release A
model result to a causal scientific claim. The maintained artifact relations
still need independent domain review before such a claim.

The common layer stays an optional experimentation composition over
`PlannedTrial` and `TrialRecord`. It owns finite study order, explicit learner
state transitions, feedback timing, isolation, resume, comparison validity,
and pair-level assessment. Task meaning, execution, verification, outcome
projection, workspace policy, treatment behavior, and consolidation content
stay with their current owners.

## Evidence used

Four maintained protocols use normal artifact tasks and the local artifact
harness.

| Protocol | Evidence | Result used at Gate A |
| --- | --- | --- |
| A01 structural transfer | Cold and structured-memory arms use the same Sydney probe after one Brisbane acquisition in the exposed arm. | The deterministic run gives cold `0.0`, exposed `1.0`, and paired effect `+1.0`. It is descriptive while relation review is false. The same full run qualifies as controlled when the explicit review input is true. |
| A02 applicability boundary | Cold, reset-after-acquisition, raw-history, and structured-memory arms use the same downstream probe. | The task-owned boundary projection is `0` for raw history and `1` for cold and structured memory. Raw history is `-1.0` against cold. Treatment-to-treatment comparisons are descriptive. |
| A03 retention and interference | One real Azure `gpt-4.1-mini` pilot completed six isolated arms and 15 normal trials. | All results are descriptive because relation review is false. Immediate transfer is `0.00`, retained gain is `+0.25`, within-order decay is `-0.08`, interference is `-0.08`, and reset-control spread is `+0.17`. The control spread is larger than the observed interference effect. |
| A04 composition | Cold, component-only, and two acquisition-order arms use one stormwater composition probe. | Cold is `0.54`, each component-only arm is `0.69`, and each two-component arm is `1.0`. Cold comparisons can be controlled after relation review. Exposure-to-exposure and order comparisons remain descriptive. |

The successful A03 bundle used 34 model calls, 50,277 input tokens, 29,668
output tokens, and 15,488 cache-read tokens. The complete bundle was about
2.7 MiB; learner-arm state was about 1.2 MiB. `TrialRecord.estimated_cost_usd`
was null, so exact monetary cost is unavailable. This is evidence against a
new delta-snapshot system and against guessed cost reporting.

One first A03 attempt failed before provider use because a synchronous
artifact operation entered an active event loop. Running synchronous study
operations in a worker thread fixed the actual failure and remains common
runtime behavior.

## Authored contract review

The following table records every retained authored type and field.

| Type | Retained fields | Decision and evidence |
| --- | --- | --- |
| `LearningStudySpec` | `study_id`, `title`, `research_question`, `agent`, `compute`, `repetitions`, `experiences`, `relations`, `measurements`, `arms` | Keep common. Identity and design cross the persisted plan boundary. One agent and compute value protect matched conditions. All protocols use repetitions, experiences, measurements, and arms. Relations stay optional for directly authored studies. |
| `LearningStudyProtocolSpec` | `study_id`, `title`, `research_question`, `experiences`, `relation_ids`, `measurements`, `arms` | Keep common. This is the strict persisted protocol file before run configuration is bound. |
| `LearningExperienceSpec` | `experience_id`, `task_id`, `role` | Keep common. Compilation needs exact identity, existing task identity, and sequence role. |
| `LearningProtocolExperienceSpec` | `experience_id`, `role`, exactly one of `family_member_id` or `task_id` | Keep common. It prevents a second task catalogue while supporting one direct non-family practice task in A03. |
| `LearningMeasurementSpec` | `measurement_id`, `projection_id`, `direction`, `target_experience_id`, `focal_arm_id`, exactly one of `comparator_arm_id` or `reference_experience_id` | Keep common. All measurements are one named paired difference. The comparator fields distinguish between-arm controls from within-arm sequence comparisons. |
| `LearningArmSpec` | `arm_id`, `role`, `treatment_id`, `steps` | Keep common. Arm role is required to distinguish cold control from exposure. Treatment identity stays opaque. |
| `RunExperienceStep` | `kind`, `step_id`, `experience_id`, `commit_post_state` | Keep common. All protocols use it. The explicit override protects probe-state handling. |
| `ReleaseFeedbackStep` | `kind`, `step_id`, `source_experience_id`, `feedback_view_id` | Keep common. All exposure studies use a separate release point. It is necessary to prove that probe feedback was not released. |
| `ConsolidateStep` | `kind`, `step_id`, `feedback_step_ids`, `operation_id` | Keep common. All exposure studies use bounded consolidation with explicit inputs. Operation meaning stays adapter-owned. |
| `ExperienceRelationSpec` | `relation_id`, `purpose`, `source_experience_ids`, `target_experience_id`, `invariant_claims`, `changed_dimensions`, `rationale` | Keep common. These fields state the authored comparison assertion and prevent task-ID similarity from becoming evidence. |

Enum review:

| Enum | Retained values | Decision |
| --- | --- | --- |
| `ExperienceRole` | `acquisition`, `practice`, `interference`, `probe` | Keep. Acquisition and probe occur throughout; A03 uses practice and interference as sequence roles. |
| `StudyArmRole` | `control`, `exposure` | Keep for cold-control validity. |
| `ExperienceRelationPurpose` | `transfer`, `boundary`, `composition` | Keep. A01/A03 use transfer, A02/A03 use boundary, and A04 needs composition validation. Retention and interference are sequence and measurement questions, not separate task-relation semantics. |
| `ImprovementDirection` | `higher`, `lower` | Keep. A02 and A03 use lower-is-better projections. |

## Learning-family review

| Type | Retained fields | Decision and evidence |
| --- | --- | --- |
| `LearningFamilySpec` | `family_id`, `title`, `description`, `dimensions`, `members`, `relations` | Keep as the caller-selected persisted overlay. Four families use it. |
| `LearningDimensionSpec` | `dimension_id`, `kind`, `description` | Keep. Relations need exact author-declared dimensions and readable meaning. |
| `LearningFamilyMember` | `member_id`, `task_id`, `description`, `probe_only`, `dimension_values` | Keep. `task_id` is the existing authority. `probe_only` prevents acquisition leakage. Descriptions and values document the expert assertion. |
| `LearningFamilyRelation` | `relation_id`, `purpose`, `source_member_ids`, `target_member_id`, `invariant_dimensions`, `invariant_claims`, `changed_dimensions`, `rationale` | Keep. Composition cardinality, probe protection, boundary applicability, and changed/invariant dimensions are validated before execution. |
| `LearningDimensionKind` | `surface`, `parameter`, `causal`, `applicability`, `component` | Keep. Surface, causal, and applicability occur across families; parameter occurs in A01/A03. Component is required to validate A04 composition. |

## Runtime, recording, and assessment review

| Surface | Retained fields or callbacks | Decision and evidence |
| --- | --- | --- |
| Compiled plan | `CompiledLearningStudy`, `PlannedArmRun`, and the three compiled step values with their existing fields | Keep runtime-local. They freeze exact `PlannedTrial` values and paired arm runs before execution. |
| Learner and feedback handles | `LearnerStateHandle(state_id, value)` and `FeedbackHandle(feedback_id, source_experience_id, view_id, value)` | Keep runtime-local. Opaque values remain adapter-owned; identities support isolation and resume. |
| Operation requests | `ExecuteExperienceRequest(arm_run, step, state)`, `ReleaseFeedbackRequest(arm_run, step, state, source_trial_record)`, `ConsolidationRequest(arm_run, step, state, feedback)` | Keep runtime-local. Each contains only the input required by the current operation. Initialisation receives `PlannedArmRun` directly. |
| Operation results | `ExperienceExecutionResult(trial_record, candidate_state)`, `FeedbackReleaseResult(candidate_state, feedback)`, `LearnerTransitionResult(candidate_state)` | Keep runtime-local. Copy-on-write candidate state is the only common transition output. |
| Operations | `initialise_learner`, `execute_experience`, `release_feedback`, `consolidate`, `discard_state` | Keep common runtime callbacks. Each maps to a distinct validity or execution boundary. |
| Observer | `arm_started`, `learner_initialised`, `step_started`, `step_committed`, `step_failed`, `arm_finished`, `study_finished`, `study_cancelled` | Keep. Atomic recording and interruption recovery use the commitment callbacks. |
| Execution and resume values | All identity, status, step, trial, feedback, failure, and known-identity fields on `StepExecutionResult`, `ArmRunExecutionResult`, `LearningStudyExecution`, `ArmRunResumeState`, and `LearningStudyResume` | Keep runtime-local. Failure injection and resume use them to avoid rerunning a completed step and to reject reused identities. |
| `LearnerStateRef` | `state_id`, `arm_run_id`, `treatment_id`, `parent_state_id`, `created_after_step_id`, `artifact` | Keep persisted. Exact artifact identity and parent lineage are resume and isolation evidence. |
| `FeedbackReleaseRecord` | `feedback_id`, `arm_run_id`, `release_step_id`, `source_experience_id`, `source_trial_id`, `view_id`, `public_artifact_refs`, `state_before_id`, `state_after_id` | Keep persisted. These fields bind learner-visible feedback to a scored source trial and committed state transition. |
| `LearnerTransitionReceipt` | `transition_id`, `arm_run_id`, `step_id`, `operation_kind`, `state_before_id`, `candidate_state_id`, `committed_state_id`, `committed`, `feedback_ids` | Keep persisted. These are the explicit copy-on-write and probe-discard facts. |
| Step and event evidence | All current fields on `StudyStepFailureRecord`, `StudyStepReceipt`, and `StudyEvent`; all current event and status enum values | Keep persisted. The final step receipt is resume authority. Event sequence is navigation evidence. Cancellation remains an interruption event, not a fabricated final result. |
| Recorded result | All current fields on `RecordedArmRunResult` and `RecordedStudyExecution` | Keep persisted as the terminal study summary and trial reference list. |
| Assessment input | `AssessmentArmEvidence(adapter_id, initial_state_equivalence_id, arm_isolated, lineage_complete, probe_feedback_hidden, probe_state_discarded, hidden_evaluation_leaked)` and required `relations_reviewed` | Keep runtime-local. Every hard validity fact is now explicit; none defaults to success. Mapping keys own arm identity. |
| Projection | `ProjectionResult(eligible, value, reason, lower_bound, upper_bound)` and named projection callbacks | Keep. Task owners supply meaning. Bounds support observed ceiling and floor diagnostics. |
| Pair-level assessment | All current fields on `PairedMeasurementValue`, `ExcludedPair`, `LearningMeasurementResult`, and `LearningStudyAssessment`; validity values `controlled`, `descriptive_only`, `invalid` | Keep persisted. Pair records are authority. Means are compact summaries. Controlled status now requires exposure versus a matched cold control. |

## Deleted or moved concepts

The following provisional concepts did not meet the promotion rule and are
deleted directly. No aliases remain.

- Authored claim policy: `StudyClaimMode` and both `claim_mode` fields. Actual
  validity derives from measurement shape and supplied evidence. Compilation
  permits descriptive exposure-to-exposure comparisons; only assessment can
  grant controlled status.
- Measurement taxonomy: `LearningMeasurementKind`, `kind`,
  `acquisition_experience_ids`, and `efficiency_denominator_id`. All real
  calculations were the same paired difference. Efficiency stays study-owned
  secondary analysis when real cost or usage data exists.
- Unused or redundant relation meanings: `retention` and `interference`.
  Sequence roles and named comparisons already own these questions.
- Undemonstrated dimension kinds: `observability`, `authority_or_resource`,
  and `regime`. A04 `hydraulic_domain` is an applicability dimension.
- Duplicate descriptions and authority paths: executable and protocol
  experience `description`, plus family `source_task_paths`. Exact `task_id`
  resolution is the authority.
- Test-only wrappers: `ResolvedLearningFamilyMember`,
  `ResolvedLearningFamily`, `ResolvedLearningRelation`,
  `resolve_learning_family()`, `resolve_learning_relation()`, and
  `relation_to_experience_specs()`. The protocol loader composes the persisted
  family directly.
- Implicit runtime history: `ExecuteExperienceRequest.completed_trial_records`
  and `released_feedback`. State and explicit feedback steps are the only
  continuity paths.
- Redundant runtime configuration: `InitialiseLearnerRequest`,
  `run_learning_study(working_root=...)`, and `close_state`. The arm plan is the
  initialisation input; the real adapter had no close operation.
- Common channel and callback diagnostics: every `changed_channels` and
  operation-result `diagnostics` field. Artifact channels stay in the artifact
  adapter and common assessment diagnostics remain separate.
- Duplicate time fields: `StudyEvent.timestamp`,
  `StudyStepReceipt.started_at`, and `StudyStepReceipt.completed_at`. Event
  sequence and final receipts are authority; resume never read these times.
- Unused terminal statuses: `StudyRunStatus.cancelled`,
  `StudyRunStatus.invalid`, and `RecordedArmRunResult.status="cancelled"`.
- Unused aggregate statistics: `median_effect`, `effect_range`, and
  `confidence_interval_95`. Pair-level results are retained. A study with
  enough repetitions can perform a named secondary uncertainty analysis.

## Adapter-owned concepts

The artifact adapter continues to own:

- `.aec-bench-learning/` and its `history`, `memory`, and `feedback` paths;
- `reset`, `raw-history`, and `structured-memory` behavior;
- safe public-feedback projector implementations;
- consolidation instructions, file formats, and write allowlists;
- arm roots, task workspaces, selected actor-snapshot export, and local-backend
  restrictions;
- the fixed model implementation and provider-specific usage capture.

The common layer sees opaque state, explicit feedback identity, normal trials,
and task-owned projection values only.

## Lifecycle input requirements

Detailed lifecycle PRDs can now assume the following boundary.

1. One complete lifecycle maps to one ordinary experience trial. The common
   layer does not add checkpoint steps or inspect lifecycle state.
2. A lifecycle adapter supplies isolated opaque learner-state snapshots and
   atomic restore. It owns any checkpoint or visibility channels.
3. Feedback released between lifecycle trials uses the common explicit release
   step. Checkpoint feedback inside one lifecycle remains lifecycle-owned.
4. The adapter must prove probe feedback hiding, probe-state discard, arm
   isolation, lineage completion, and no hidden-evaluation leakage.
5. Lifecycle task owners supply named outcome projections. The common assessor
   does not parse phase breakdowns.
6. Treatment-to-treatment and within-arm comparisons remain descriptive.
   Controlled status requires an exposure arm and matched cold control on the
   same probe.
7. Token and cost capture stays with the execution owner. Missing monetary cost
   stays missing.

Do not add common checkpoint, phase, channel, registry, content-addressing, or
provider concepts during lifecycle design without new evidence.

## Consequences and open questions

- Release A protocols remain maintained examples in the protocol collection;
  no A01-A04-specific production runtime exists.
- Full learner-state snapshots remain the simpler safe resume mechanism at the
  observed storage size.
- The local real-model runner remains study or research glue. Gate A found no
  evidence for a common CLI, callback registry, or provider contract.
- Independent domain review of the family assertions is still required before
  causal publication.
- Exact monetary cost was unavailable. A later execution-owner change can
  populate existing trial cost evidence; Learning Studies must not invent it.
