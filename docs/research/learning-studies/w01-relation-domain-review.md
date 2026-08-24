# W01 Dam Escalation Applicability-Boundary Relation: Domain Review

| Field | Value |
| --- | --- |
| Class | Research |
| Status | Research |
| Study | `w01-dam-escalation-applicability-boundary` |
| Relation | `unreliable-instrument-escalation-to-reliable-routine-surveillance` |
| Scope | Independent dam-monitoring domain review required by W01 §3 and §22 before `relations_reviewed=true` |

## Reviewer identity and standing

This review was performed by an AI reviewer (a GPT-5.6 Luna agent instance,
invoked with fresh context and no involvement in implementing PR #150, LS-09A,
LS-09B, LS-09C, or W01). It acted as an independent dam-safety/seepage
monitoring domain reviewer for the Learning Studies programme. The reviewer
read the protocol and maintained protocol data, then checked the live world
implementation, materialised profile data, and executed adversarial action
sequences against `evaluate()` and the named projections.

**The programme owner must decide whether this AI review satisfies the
protocol's "independently reviewed by a dam/domain reviewer" requirement, or
whether a credentialed human dam-safety engineer must additionally sign off
before a W01 result is treated as a causal claim.** The owner previously
accepted an AI-performed independent review for L01 (recorded in
`l01-relation-domain-review.md`); that precedent does not automatically decide
W01.

## Method

- Read `W01-dam-escalation-applicability-boundary.md`, including its invariant
  claims, changed dimensions, threats to validity, measurements, and domain
  review checklist.
- Read the tranche's LS-09B and LS-09C PRDs, then read the maintained
  `family.toml` and `study.toml`.
- Read `world.py`, `variants.py`, all three dam profile JSON files,
  `definition.py`, `episode_runtime.py`, `dam_learning.py`, the world adapter,
  `dam_w01.py`, and `dam_seepage_trial.py`.
- Read the existing dam-world, adapter, W01, and documentation-ownership tests
  as evidence of what is already guaranteed.
- Loaded both W01 profiles through `dam_seepage_world_definition()`, compared
  their JSON fields, and checked the registered content hashes.
- Applied transitions to direct opening states for an acquisition-success
  sequence, a probe copycat, a gold probe, and an immediate-response probe.
  Constructed valid synthetic `TrialRecord` values from those evaluations and
  called the four W01 projections.
- Inspected the initial actor observation before
  `CHECK_MEASUREMENT_SYSTEM`, and the observation after that action, to test
  whether reliability is actually released at the intended epistemic action.

## Defect that materially undermines the relation

The initial actor-visible `SeepageObservation` includes the literal
`profile_id` (`world.py:116-126, 161-188`; serialised by
`episode_runtime.py:199-208`). The probe's value is
`reliable-routine-surveillance`, and the acquisition's value is
`unreliable-instrument-escalation`. Thus, before any measurement-system check,
the observation names both the instrument condition and the intended response.
This directly defeats the protocol's requirement that reliability be learned
only through `CHECK_MEASUREMENT_SYSTEM` (W01 §5.2, §6.3, and §22; LS-09B
§13.5). A cold agent can read the probe slug and select routine surveillance
without taking the epistemic action, so the primary
`dam.inappropriate-escalation` outcome is likely to be at a zero ceiling.

There is a second, independent matching defect: the profiles use different
monitoring-point IDs and four different measured-flow values. The qualitative
pattern is matched, but the protocol and family claim that only the declared
instrument/applicability dimensions differ. These differences are not
represented as changed dimensions. Together, the leakage and surface mismatch
mean the relation is not currently suitable for a claim-bearing run.

## Verdicts on the W01 invariant claims

### 1. Same monitoring point type, action set, and prose objective

**QUALIFIED.**

The action set is genuinely shared: `SeepageAction` has the same five actions
(`world.py:42-47`), and `DamSeepageEpisodeHost.capabilities()` exposes that
same enum for every profile (`episode_runtime.py:110-122`). The objective
string and all task-level action semantics are byte-identical in the two JSON
profiles. Both IDs are `SEEP-WEIR-*`, so they are the same monitoring-point
type.

However, `unreliable-instrument-escalation.json` uses `SEEP-WEIR-02` while
`reliable-routine-surveillance.json` uses `SEEP-WEIR-03`. The claim is
confirmed only if "type" deliberately excludes point identity. The family
dimension says “monitoring point type”, but the W01 invariant dimension is
also described as `monitoring_point_id_pattern`; the different concrete
point IDs are an undeclared surface difference.

### 2. The response is determined by measurement-system evidence and the
flow/visual pattern, with nothing else

**QUALIFIED.**

The world authority supports the intended causal statement:
`requires_engineering_review()` returns true for an unreliable instrument,
for an inspected visual alert, or for the required number of consecutive flow
alerts (`world.py:279-293`). Both W01 profiles have clear downstream
conditions, four flows below the 27 L/min alert threshold, and no consecutive
breach. Therefore the derived required response differs only because
instrument condition differs. The same `evaluate()` function derives
`required_response`, evidence completeness, correctness, and success for both
profiles (`world.py:316-341`).

The learner-facing statement is not true as implemented: the profile slug
provides a second route to the answer before the measurement-system check.
The evaluation method is evidence-governed, but the observable surface makes
the intended evidence path optional.

### 3. The acquisition flow/visual pattern does not itself require escalation;
only the unreliable instrument does

**CONFIRMED (for the scenario data), subject to the leakage defect above.**

Every acquisition reading has `downstream_condition = "clear"` and measured
flow below 27 L/min (19.5, 20.0, 20.2, and 20.1 L/min). The world’s
consecutive-alert loop therefore never fires; the only true branch is
`InstrumentCondition.UNRELIABLE` (`world.py:279-293`). A direct acquisition
sequence of `CHECK_MEASUREMENT_SYSTEM` followed by
`ESCALATE_FOR_ENGINEERING_REVIEW` produced `required_response =
engineering-review`, `response_correct = true`, `evidence_complete = true`,
and `successful = true`.

### 4. The probe has the same flow/visual pattern as the acquisition; only
instrument condition differs

**REJECTED.**

The two profiles agree on task world, objective, baseline note, alert
threshold (27 L/min), expected flow (20 L/min), cadence (0/6/12/18 hours),
reservoir levels, rainfall (0 mm), visual-alert set, reading count, and all
downstream conditions. They do not agree on the complete reading values:

```text
acquisition -> probe measured flow (L/min)
19.5 -> 19.8
20.0 -> 20.1
20.2 -> 20.0
20.1 -> 19.9
```

They also use different monitoring-point IDs. The qualitative below-alert and
clear pattern is shared, but `family.toml` declares `reading_pattern` as
including flow values and cadence, while `study.toml`/W01 rationale says the
surface reading pattern is held constant. Numeric flow changes are therefore
an undeclared parameter confound, not merely the declared instrument change.

### 5. A checked-and-evidence-governed learner should reach two different,
individually correct conclusions

**QUALIFIED.**

At the world-contract level this is true. Checking the unreliable acquisition
instrument and escalating is successful; checking the serviceable probe
instrument, reviewing all readings, inspecting the latest downstream area,
and selecting routine surveillance is successful. The same transition and
evaluation functions are used for both profiles, with no profile-specific
evaluation branch.

The initial observation leak means a learner need not check the instrument or
reason from the currently released evidence to reach the probe conclusion.
Consequently, the implementation demonstrates two correct state-machine
outcomes but does not cleanly test the claimed epistemic discipline.

## Contract and dimension audit

| Invariant requested by W01/family | Verdict | Evidence |
| --- | --- | --- |
| Same action set | CONFIRMED | One `SeepageAction` enum and one host capability catalogue are used for every profile. |
| Same episode contract | CONFIRMED | One `DamSeepageEpisodeHost`, `Episode`, transition path, terminal-on-response behaviour, and replay path are used for both (`episode_runtime.py:55-87`; `dam_seepage_trial.py:63-88, 123-135`). |
| Same observation shape | CONFIRMED structurally; QUALIFIED as a surface | One frozen `SeepageObservation` shape is constructed by `observe()` for both (`world.py:116-126, 161-188`), but its always-released `profile_id` leaks the profile semantics. |
| Same evaluation method | CONFIRMED | Both call the same `evaluate()` and `requires_engineering_review()` functions (`world.py:279-341`). |
| Only declared dimensions differ | REJECTED | Instrument condition and derived response differ as declared, but monitoring-point ID and four flow values also differ; profile IDs necessarily differ and are learner-visible. |
| Evidence-governed escalation is the same discipline | QUALIFIED | The action/evaluation rule is the same, and the public feedback principles state the rule (`dam_learning.py:30-36`), but the probe slug supplies the answer without evidence gathering. |

The maintained family overlay declares only
`monitoring_point_pattern` and `reading_pattern` invariant and
`instrument_reliability`/`response_applicability` changed
(`family.toml:5-23, 47-59`). The concrete JSON does not satisfy that
strict reading of the overlay.

## Surface-diff analysis

This is a field-by-field comparison of the two checked-in W01 JSON profiles.

| JSON field | Acquisition | Probe | Classification |
| --- | --- | --- | --- |
| `task_world_id` | `dam-seepage-monitoring` | same | invariant |
| `profile_id` | `unreliable-instrument-escalation` | `reliable-routine-surveillance` | Declared task identity, but an undeclared learner-facing semantic leak because `observe()` releases it. |
| `monitoring_point_id` | `SEEP-WEIR-02` | `SEEP-WEIR-03` | **Undeclared surface confound**; same point type, different concrete point. |
| `objective` | exact common text | exact common text | invariant |
| `baseline_note` | exact common text | exact common text | invariant |
| `required_consecutive_alert_readings` | `2` | `2` | invariant |
| `visual_alert_conditions` | `cloudy`, `sediment-observed`, `new-seep` | same | invariant |
| `instrument_condition` | `unreliable` | `serviceable` | **Declared causal change**. |
| `readings[*].elapsed_hours` | `0, 6, 12, 18` | same | invariant cadence |
| `readings[*].reservoir_level_m` | `100.0, 100.1, 100.1, 100.0` | same | invariant |
| `readings[*].recent_rainfall_mm` | all `0.0` | same | invariant |
| `readings[*].expected_flow_l_min` | all `20.0` | same | invariant |
| `readings[*].alert_flow_l_min` | all `27.0` | same | invariant |
| `readings[*].measured_flow_l_min` | `19.5, 20.0, 20.2, 20.1` | `19.8, 20.1, 20.0, 19.9` | **Undeclared parameter confound**; qualitative below-alert status is implied invariant, exact values are not. |
| `readings[*].downstream_condition` | all `clear` | same | invariant qualitative visual pattern |

`required_response` is not a JSON field: it is derived by
`requires_engineering_review()` and is the declared applicability change.
The variant registry also gives the two profiles different title, summary,
tags, and rationale (`variants.py:34-67`). Those metadata values are not passed
to the actor by the trial harness, but the profile ID is passed in every
observation.

## Sequence-copy detectability (executed against the live world)

The acquisition's minimal successful sequence is:

```text
CHECK_MEASUREMENT_SYSTEM
ESCALATE_FOR_ENGINEERING_REVIEW
```

Replaying that sequence on the probe is a direct terminal-action copy. The
gold probe sequence checked the instrument, recorded all three remaining
readings, inspected the latest downstream area, and selected routine
surveillance. The incompetent sequence submitted routine surveillance
immediately without any evidence review.

For each row below, the state was replayed with `transition()` and evaluated
with the live `evaluate()`. The projection values came from a synthetic
completed `TrialRecord` whose `verifier_completed` was true and whose
canonical reward was `1.0` exactly when `SeepageEvaluation.successful` was
true.

| Sequence | `assessment_submitted` | `selected_response` | `required_response` | `response_correct` | `all_scheduled_readings_reviewed` | `measurement_system_checked` | `latest_downstream_area_inspected` | `evidence_complete` | `successful` |
| --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Copycat: check, then escalate | true | `engineering-review` | `routine-surveillance` | false | false | true | false | false | false |
| Gold: check, 3 readings, inspect latest, routine | true | `routine-surveillance` | `routine-surveillance` | true | true | true | true | true | true |
| Lazy: immediate routine response | true | `routine-surveillance` | `routine-surveillance` | true | false | false | false | false | false |

The corresponding projection outputs were:

| Sequence | `world.canonical-reward` | `dam.response-correct` | `dam.evidence-complete` | `dam.inappropriate-escalation` |
| --- | ---: | ---: | ---: | ---: |
| Copycat | `0.0` | `0.0` | `0.0` | **`1.0`** |
| Gold | `1.0` | `1.0` | `1.0` | `0.0` |
| Lazy | `0.0` | `1.0` | `0.0` | **`0.0`** |

Thus the required diagnostic distinction works: the copycat is penalised on
canonical reward and response correctness, and
`dam.inappropriate-escalation` fires for the false-positive escalation but
not for generic evidence failure. A full acquisition-shaped probe replay
(check, all readings, inspect latest, then escalate) also produced
`response_correct=false`, `evidence_complete=false`, `successful=false`,
canonical reward `0.0`, and inappropriate escalation `1.0`.

## Leakage findings

### Probe observation

The initial direct observations were:

```text
acquisition opening: profile_id=unreliable-instrument-escalation,
                    instrument_condition=None
probe opening:      profile_id=reliable-routine-surveillance,
                    instrument_condition=None
after CHECK on acquisition: instrument_condition=unreliable
after CHECK on probe:       instrument_condition=serviceable
```

`instrument_condition` itself is correctly withheld until
`CHECK_MEASUREMENT_SYSTEM` (`world.py:177-187`). However, `profile_id` is
released at the same initial observation and is semantically explicit. This
is a **confirmed, material leakage defect**, not a theoretical naming concern.
The generic W01 instruction is identical for both profiles
(`dam_w01.py:153-166`), and the baseline note is appropriately caveated as
site-specific. The public flow values, alert thresholds, and visual-alert
vocabulary are intended current scenario evidence; they do not disclose
instrument reliability by themselves, although the benign pattern encourages
routine surveillance.

### Acquisition feedback

The dam projector constructs a fixed allowlist containing public identity,
canonical reward/public validity, the learner's own action sequence and
selected response, selected boolean outcomes, and four bounded monitoring
principles (`dam_learning.py:51-86`). Its validator rejects extra top-level
fields and forbidden evaluation names (`dam_learning.py:89-136`). It does not
emit `required_response`, `instrument_condition`, visual thresholds, replay
internals, or host paths. The adapter also recursively rejects forbidden keys
and hidden-path strings (`worlds.py:629-669`).

The feedback's acquisition `task_id` contains the descriptive source slug,
but that is the learner's own source identity and is not the hidden probe
truth. The principles are deliberately declared treatment content, including
the rule that routine surveillance is appropriate when released evidence
does not indicate unreliability or an alert. No probe profile ID or probe
required response is added by the projector. `study.toml` releases feedback
only from the acquisition and never from the probe (`study.toml:89-111`).
Within the planned W01 runtime, source-experience identity is checked by the
common runtime (`runtime.py:370-387`).

**Feedback verdict: no hidden evaluation leakage found in the planned W01
release path.** This does not repair the independent observation leak.

## Domain-realism findings

### Plausible aspects

- Four readings at six-hour intervals over 18 hours are a plausible bounded
  monitoring episode.
- Expected flow of 20 L/min and alert flow of 27 L/min, with stable reservoir
  level, no recent rainfall, and clear downstream conditions, form a coherent
  benign synthetic baseline. The two-consecutive-alert rule is explicit and
  professionally recognisable as a persistence criterion.
- Treating a confirmed unreliable instrument as sufficient reason for
  engineering review is plausible: the monitor cannot rely on the primary
  measurement and should escalate for engineering/instrument follow-up even
  when current values are below the alert threshold.
- Treating a serviceable instrument plus stable below-alert flow and clear
  visual evidence as routine surveillance is professionally plausible within
  this bounded action set. The baseline note correctly says its limits are
  task-owned synthetic values, not general dam-safety limits.

### Domain and interpretation caveats

- The descriptive profile IDs are not realistic operational observations and
  expose the answer. A real monitor would see a monitoring-point identifier,
  not a task slug saying “reliable routine surveillance”.
- `INSPECT_DOWNSTREAM_AREA` releases only the condition for the current
  reading, and `evaluate()` marks routine evidence complete when the latest
  reading is inspected (`world.py:254-264, 323-340`). It does not require
  inspection of each historical reading. A competent dam monitor may accept a
  current downstream inspection plus the recorded history, but the protocol's
  wording “no visual alert condition ever occurs” is stronger than the
  learner-visible evidence contract. This weakens `evidence-complete` as a
  professional measure, although it is held constant across profiles.
- The small numeric flow perturbations remain below the threshold and are not
  implausible, but they can create model-facing surface differences unrelated
  to applicability. They should not be retained while claiming an otherwise
  exact match.
- This is a synthetic decision-support task, not authority to make a real
  dam-safety determination. The source comments and profile baseline make that
  boundary clear.

## Measurement sufficiency and ceiling/floor risks

The five maintained measurements (`study.toml:16-54`) cover the intended
probe-level outcomes:

1. structured-memory versus cold `dam.inappropriate-escalation`;
2. reset-after-acquisition versus cold inappropriate escalation;
3. structured-memory versus cold response correctness;
4. structured-memory versus cold evidence completeness; and
5. structured-memory versus cold canonical reward.

They are sufficient to score the state-machine distinction demonstrated above,
including the required separate false-positive diagnostic. The reset control
also addresses ordering/provider contamination. The named projections are
bounded and ineligibility-safe: the dam projections require a completed,
replay-valid evaluation and a submitted response, while canonical reward reads
the completed replay-valid evaluation.

Important blind spots remain:

- There is no registered acquisition-quality measurement or gate. A real
  structured-memory arm can fail the acquisition response and still receive
  the declared feedback/principles and consolidate memory. The resulting
  effect is the bundle “acquisition attempt + feedback + consolidation”, not
  specifically transfer from a correctly learned escalation. Acquisition
  success, selected response, and feedback eligibility must be reported and
  stratified or gated before attributing a result to prior correct escalation.
- `dam.evidence-complete` is an aggregate boolean; it does not separately
  measure whether the learner checked the instrument, reviewed all readings,
  and inspected the relevant visual evidence. The existing fields can report
  those components, but W01 does not register them as separate measurements.
- The projections detect the outcome of copying escalation but cannot establish
  whether a model reasoned conditionally versus read the leaked profile slug.
  Removing the slug is therefore a prerequisite for interpreting the causal
  mechanism.
- The treatment bundles declared public principles, feedback, and
  consolidation. W01 cannot isolate which of those components caused a probe
  effect, as the protocol acknowledges.

The dominant ceiling risk is the profile-ID leak: a cold agent can identify the
probe's intended answer from the initial observation, so
`dam.inappropriate-escalation = 0.0` and `dam.response-correct = 1.0` may be
uniform across arms without testing negative transfer. The protocol's own
“all arms at ceiling” rule (§19.2 and §20) would then prohibit a learning
conclusion. A secondary floor/selection risk is that malformed or
replay-invalid episodes are ineligible for the named projections rather than
counted as generic failure, potentially reducing the analysed sample.

## Overall recommendation

**REJECTED for `relations_reviewed=true` in the current state.**

The world rule and the copycat diagnostic are sound, and the dam scenario is
reasonable as a bounded synthetic exercise. Nevertheless, the relation is not
currently a clean causal applicability boundary because:

1. the initial observation literally names `reliable-routine-surveillance`
   (and the acquisition slug names its own answer) before the epistemic check;
2. the two profiles differ in concrete monitoring-point ID and measured flows
   despite those differences not being declared; and
3. acquisition success is not gated or measured, which weakens any statement
   specifically about transfer from a correctly acquired escalation.

Before any claim-bearing W01 run, require:

1. **Remove or neutralise the semantic profile slug from actor-visible
   observations.** Keep the task/profile identity available to the harness,
   but expose only a non-semantic monitoring-point identifier or another
   neutral actor-facing value. Add a regression test showing that the opening
   probe observation does not disclose reliability or the required response;
   retain the post-`CHECK_MEASUREMENT_SYSTEM` release test.
2. **Make the matched profiles actually matched.** Prefer the same
   `monitoring_point_id` and byte-identical readings (including measured
   values), with only `instrument_condition` changed and the required response
   derived accordingly. Alternatively, explicitly re-author the family and
   study to declare and justify each remaining surface/parameter difference,
   then obtain a new relation review.
3. **Record acquisition fidelity.** Require or report a successful,
   evidence-complete acquisition with the intended escalation before calling a
   result transfer from prior escalation experience; otherwise label the
   estimand as the full declared treatment bundle.
4. **Pilot for headroom and visual-evidence interpretation.** If cold and
   exposed probes are at ceiling on inappropriate escalation, response
   correctness, or evidence completeness, apply W01 §20 and make no learning
   claim. Clarify whether one current downstream inspection is the intended
   professional evidence contract or require historical visual checks.
5. **Repeat this relation review after the observation and matching fixes.**

After these conditions are met and the programme owner accepts the reviewer
standing, `relations_reviewed=true` may be considered. This document does not
authorise it for the current implementation.

## Commands used

The following commands were run from the W01 worktree. The Python probes wrote
only short evidence files under the repository during projection checks and
removed them before completion; no scratch artifacts remain.

```bash
uv run python - <<'PY'  # load profiles, field-diff JSON, evaluate sequences
...
PY

uv run python - <<'PY'  # build synthetic TrialRecords and call four projections
...
PY

uv run python - <<'PY'  # inspect opening and post-check observations
...
PY
```

The final documentation-ownership validation is recorded after registering
this document:

```bash
uv run pytest tests/docs/test_documentation_ownership.py -q
```
