---
title: From Long Prompts to Rich Engineering Interactions
date: 2026-07-12
topic: AEC-Bench long-horizon work from PR10 through PR17
tags: [aec-bench, long-horizon, ssc-03, provenance, evaluation]
status: captured
---

# Learning Capsule: From Long Prompts to Rich Engineering Interactions

## One-Line Takeaway

PR10–PR17 turned one static AI task into a staged review where evidence arrives over time and progress is recorded; a configured task can now offer limited evidence requests, but hydraulic calculations and durable learning remain future work.

**First reading:** Read [the three-checkpoint story](#the-concrete-three-checkpoint-story), [the stack at a glance](#the-whole-stack-at-a-glance), each PR's “Why it mattered” sentence, [where we stand](#where-we-stand-before-pr18), and [the records-room analogy](#best-analogy). Use the detailed PR sections as a reference when PR18 depends on them.

**Scope:** This guide freezes the story at the end of PR17, before PR18. Here, “added” means implemented and tested on the named branch; it does not necessarily mean merged into `main`.

## Starting Intuition

The tempting first idea was that a **long-horizon task** should be a longer task: more pages, more calculations, more steps, and a larger final answer.

That idea is understandable, but it misses the difficult part of real engineering work. An AI can receive a 200-page report in one prompt and still complete a one-shot task. The input is large, but nothing changes while the AI is working. It does not have to wait for a revised drawing, preserve an earlier decision, notice that a new report contradicts an old memo, or refuse to close a finding—a logged review issue—when evidence is missing.

Our course correction was:

> A task becomes meaningfully long-horizon when the situation changes over time and later work depends on preserving the right meaning from earlier work.

That led us away from a “formula marathon” and toward an engineering review loop:

```text
inspect the current files
  -> record what passes, fails, or is missing
  -> receive revised evidence
  -> update only what the revision justifies
  -> preserve everything that should stay stable
  -> close findings only when the required evidence exists
  -> decide honestly whether the package is ready for use
```

We chose **SSC-03**, the project label for a stormwater and drainage task family, as the working example. This guide uses **AI model** for the reviewer and **hydraulic model** for the drainage calculation program. The first lifecycle does not ask the AI model to design the whole drainage system. It asks the AI model to check whether a hydraulic-model run, its report, and the later design memo that relies on that report share a trustworthy chain of evidence.

The harness does not update the AI model's learned **weights**, the numerical settings created during training, during these runs. The AI may remember earlier messages or reread saved files, but no durable learner state changes across separate runs. We are building a foundation that may later support **post-training**—training performed after a base model has been created. We are not yet demonstrating **continual learning**, where a system keeps durable learning from a stream of encounters over time.

## Refined Understanding

The work from PR10 to PR17 is best understood as building a trusted structure around the AI model one layer at a time.

The smallest useful mental model is:

```text
task files
   ↓
AEC-Bench reveals the files allowed at this stage
   ↓
the AI reviews them and writes a submission
   ↓
if the submission has the required structure,
AEC-Bench archives it and advances the task
   ↓
the task's checker, which is separate from the model-running environment,
scores the completed work
   ↓
for campaign runs, a frozen copy protected by a digital fingerprint
preserves the declared evidence supporting the recorded result
```

The AI model is the participant. AEC-Bench is the trusted supervisor and records clerk. The model-running environment is the room where the participant works. The task's checker—not the AI or the room operator—decides whether the work is correct.

### Three different meanings of “memory” or “state”

These are easy to mix up:

1. **Conversation memory:** The model can still see earlier messages in the same conversation.
2. **Saved task state:** AEC-Bench has stored earlier files, submissions, attempts, and decisions on disk.
3. **Durable learner change:** Training or another learning process changes what the system carries into later, separate runs—for example, updated model weights.

PR10–PR17 build mechanisms for exposing and measuring the first two. They do not yet provide comparative model results or establish the third.

### Why the work came as a stack of pull requests

A **pull request**, or **PR**, is a reviewable bundle of code and documentation changes. Each PR below establishes one rule about who may control what before the next layer depends on it:

```text
stage the task
  -> measure changes
  -> create controlled cases
  -> run reproducible campaigns
  -> separate host and environment authority
  -> test one continuing lifecycle in a local external environment
  -> define honest reporting for separate test cases
  -> let AI requests reveal limited extra evidence
```

“Stacked” means that each later draft branch starts from and depends on the earlier branch. Review the layers from PR10 upward. At this guide's capture date, PR10 is merged and PR11–PR17 are open draft PRs.

Trying to jump straight to a rich hydraulic environment would have left basic questions unanswered. Who controls evidence and reward? What survives a crash, and how do we know which model and files produced a result? Can a retry silently inherit an old answer, or can a secret test-case result leak into public summaries? The stack answers those questions before the physical world becomes more complicated.

## Core Concepts

- **Long-horizon means change over time:** A large prompt is not enough; later work must depend on earlier evidence and decisions.
- **The host remains trusted:** AEC-Bench controls evidence, checkpoint progression, verification, and reward.
- **Memory is controlled, not assumed:** Conversation history and saved task files are separate from learning in model parameters.
- **Every result needs receipts:** Files, code, settings, attempts, and scores must remain traceable to their exact sources, and later alterations must be detectable.
- **The progression is deliberate:** First build trustworthy interaction and records, then add executable engineering consequences.

### Meet the main pieces

| Term | Simple meaning |
|---|---|
| **AEC-Bench** | Software for building and testing AI tasks in architecture, engineering, and construction. |
| **Task world** | The engineering situation: its files, rules, events, tools, and expected state. |
| **SSC-03** | The project label for this stormwater and drainage task family. Treat it as a name; do not invent an expansion for “SSC.” |
| **Host** | The trusted AEC-Bench controller. It decides what is visible, which stage is active, and when checking occurs. |
| **Environment** | The runtime that presents prompts and tools to the model and returns execution details. It does not decide correctness or reward. |
| **Model or agent** | The AI participant doing the engineering review. |
| **Verifier** | Task-owned checking code that decides whether the submitted work meets the task rules. |
| **Reward** | The score produced from verifier-owned evidence. |
| **Harness** | The software that runs one task and records what happened. |
| **Meta-harness** | The experiment manager around the harness. It plans and compares many task runs. |

### The concrete three-checkpoint story

The original SSC-03 lifecycle has three checkpoints.

- A **checkpoint** is a formal stopping point where the AI records its decisions before more evidence appears.
- **Governing** means accepted as a source that design decisions may rely on.
- A **finding** is a logged review issue.
- **Ready to issue** means this synthetic package meets the task's internal closeout rules.

“Ready to issue” does not mean the evidence is approved or safe for use on a real project.

1. **Initial provenance review**
   - The list of files used for the drainage calculation, called an input manifest, points to an older catchment file and area even though the project's accepted basis contains newer values.
   - The model should identify that the current run cannot yet govern the design.
   - One finding remains open and the package is not ready to issue.

2. **Response and rerun review**
   - A corrected input manifest, a replacement run, and a reissued hydraulic report arrive.
   - The run and report may now be accepted.
   - The design memo still refers to the old run, so the final design claim remains unsupported.
   - A fluent but unsafe reviewer may be tempted to declare victory too early. The task should reject that.

3. **Final closeout review**
   - A corrected memo arrives and properly cites the governing run and report.
   - The remaining finding can now close.
   - Only at this point should the package become ready to issue.

This is intentionally a provenance review. **Provenance** means the receipt trail showing where a conclusion came from: which source revision, which model run, which report, which memo, and which decision.

### The whole stack at a glance

| Step | Pull request | Question answered in plain language |
|---|---|---|
| 1 | [PR #10](https://github.com/TheodoreGalanos/aec-bench/pull/10) | Can one task unfold safely through several evidence deliveries? |
| 2 | [PR #11](https://github.com/TheodoreGalanos/aec-bench/pull/11) | Can we tell whether the model updated correctly rather than merely ending correctly? |
| 3 | [PR #12](https://github.com/TheodoreGalanos/aec-bench/pull/12) | Can we expose several controlled kinds of change and non-change? |
| 4 | [PR #13](https://github.com/TheodoreGalanos/aec-bench/pull/13) | Can we plan, run, recover, and preserve a whole calibration campaign? |
| 5 | [PR #14](https://github.com/TheodoreGalanos/aec-bench/pull/14) | Can another model-running environment execute a checkpoint without taking control of correctness or reward? |
| 6 | [PR #15](https://github.com/TheodoreGalanos/aec-bench/pull/15) | Can a local external model-running environment carry one continuing review through every checkpoint without taking over checking? |
| 7 | [PR #16](https://github.com/TheodoreGalanos/aec-bench/pull/16) | Can we report results on separate test cases without pretending they prove learning or cause and effect? |
| 8 | [PR #17](https://github.com/TheodoreGalanos/aec-bench/pull/17) | Can a limited AI request change which evidence becomes visible next? |

### Step 1 — PR10: Turn one review into an evidence lifecycle

Before PR10, a large task could still reveal everything at once. PR10 created the three-checkpoint story above and made AEC-Bench control the order of evidence release.

An **evidence lifecycle** is one evolving review in which information arrives in stages and later work depends on earlier work.

PR10 added several important rules:

- Future evidence stays hidden until the submission is readable JSON with the correct checkpoint ID and required top-level fields. This checks only that an answer was submitted in the expected shape; the verifier judges engineering correctness later.
- A submitted checkpoint is archived and cannot be silently rewritten.
- A **revisit** can read an earlier submission without changing it.
- A **branch** creates a new derived run from an earlier checkpoint instead of editing the parent history.
- A crash can be resumed from durable state instead of pretending the run never happened.
- The run records identifying receipts for the repository and checker code, hashes every task-package file, and records the model setup, prompts, tool calls, timing, token use, estimated cost, and result files.

PR10 also created four execution-and-visibility conditions controlling which earlier information remains available to the model:

| Condition | What the model receives |
|---|---|
| **Persistent context** | The same conversation continues across all checkpoints. |
| **Fresh context with artifact memory** | A new conversation starts with accumulated released evidence and earlier submitted review files visible. |
| **Fresh context with raw evidence only** | A new conversation sees accumulated source evidence but not earlier submissions. |
| **Fresh context with current release only** | A new conversation sees only the current checkpoint's instruction and evidence. |

A **visibility policy** is simply the rule deciding which saved materials the model may see. It does not delete the audit copy.

Why PR10 mattered: we could now ask whether a model preserved findings and decisions across revisions instead of asking only whether its final review looked plausible.

Boundary: PR10 kept the evidence schedule fixed. It added neither AI-chosen evidence, hydraulic execution, nor a model-performance campaign.

Why the next step was needed: PR10's final score and runtime logs could not show whether the model changed its engineering conclusions for the right reason.

### Step 2 — PR11: Measure acquisition, retention, and interference

Suppose two models give the same final answer. Their journeys may still be very different:

- one began correctly and updated when new evidence arrived;
- one guessed the future answer before the evidence existed;
- one fixed the changed fact but damaged several facts that should have stayed stable;
- one reached the right final answer only by correcting its own earlier error.

PR11 extracts a few named fields from each checkpoint submission and stores each as one small fact that can be compared over time. The code calls these facts **semantic atoms**. Examples include “the run is non-governing,” “finding F-PRV03-001 is open,” and “the package is not ready.”

It then added diagnostics that do not change reward:

| Diagnostic | Simple question |
|---|---|
| **Initial accuracy** | Was the first review correct? |
| **Acquisition** | When new evidence justified a change, did the model move from the correct old state to the correct new state? |
| **Update precision** | Of everything the model changed, how much changed to a correct value? |
| **Update recall** | Of everything that needed to change, how much ended correctly? |
| **Update F1** | What single score balances update precision and update recall? |
| **Retention** | Did correct facts that should remain stable stay correct? |
| **Interference** | After new evidence arrived, did a correct fact that should have stayed stable become wrong? |

A model that predicts a future answer before supporting evidence arrives does not receive acquisition credit later. It may be correct later, but the metric does not count that as evidence-driven acquisition because its earlier state did not match the correct earlier state.

If a metric had no opportunity to occur—for example, no facts were supposed to change—AEC-Bench leaves that rate blank (`null`) rather than calling it either a failure or a perfect score.

Why PR11 mattered: “eventually correct” and “updated correctly” became different measurable behaviours.

Boundary: these diagnostics describe behaviour within one lifecycle run. They do not change reward or show that the learner itself changed.

Why the next step was needed: measurements need controlled situations that exercise different kinds of update and non-update.

### Step 3 — PR12: Create four controlled public variants

A **variant** is a deliberately changed version of the same basic task. A **public calibration variant** is a publicly defined diagnostic case used to understand behaviour and choose a setup before a separate evaluation. A **holdout** is meant to be a different test case kept out of that calibration work—the secret final exam, in the analogy. PR12 added four public variants:

1. **Full correction** (`staged_full_correction`)
   - A corrected input manifest, a replacement run, and a reissued hydraulic report arrive.
   - A corrected memo arrives later.
   - The model should update and eventually close the package.

2. **Irrelevant note** (`semantic_no_op_release`)
   - A new administrative note arrives but changes no engineering fact.
   - The model should preserve its current conclusions instead of inventing progress.
   - At closeout, the corrected run, report, and memo arrive together. Only then should the model update and close the package.

3. **Claim without evidence** (`response_assertion_only`)
   - At the response checkpoint, a note says the model was corrected but supplies no corrected technical files.
   - The complete corrected chain arrives only at closeout.
   - The model should not treat an assertion as proof.

4. **Missing closeout memo** (`memo_closeout_missing`)
   - The rerun is valid, but the required corrected memo is not supplied.
   - The package should remain not ready.

These are public calibration cases whose definitions live in the repository, but the AI is not shown which variant label is active. AEC-Bench records that label outside visible evidence and ties it to the exact package bytes using a **hash**—a digital fingerprint.

Why PR12 mattered: we could test useful non-change, unsupported claims, delayed closure, and full correction using one controlled family.

Boundary: these were public cases with a host-fixed schedule. PR12 added no model campaign, holdout run, or learner update.

Why the next step was needed: we had good cases and records for individual runs, but no runner for a planned batch and no standard TrialRecord stored in a permanent register.

### Step 4 — PR13: Build the calibration campaign runner and frozen-record pipeline

PR13 turned the variants and memory conditions into an exact plan. The example committed in PR13 expands to:

```text
4 public variants
× 4 conversation and visibility conditions
× 1 model setup
× 1 repetition
= 16 planned trials
```

A **manifest** is the configuration file stating what should run. A **dry run** expands and checks that plan without calling a model provider or writing campaign ledger records.

Every trial identity is built from the exact variant, task files, checker and AEC-Bench source, requested model and adapter, runtime files actually used by the adapter, provider, and checker, memory condition, repetition, and turn limit. Changing any of these changes the trial identity. An **adapter** is the bridge between AEC-Bench and the model-running system. A **turn limit** is the maximum number of model exchanges allowed in one session. A **repetition** means running the same planned setup again.

PR13 added the standardized campaign-level record-keeping machinery:

- A **TrialRecord** is the structured cover sheet for one trial.
- A **snapshot** is the frozen copy of the exact files supporting that cover sheet.
- A **ledger** is the append-only archive of finalized TrialRecords.
- **Append-only** means new history may be added, but old history is not silently replaced.
- An **atomic write** makes each published file appear complete rather than half-written. If a valid snapshot lands before its TrialRecord, recovery can finish publication without rerunning the model.
- **Recovery** finishes publication from already saved evidence without unnecessarily rerunning the model.
- **Fail closed** means stop on conflicting evidence instead of guessing.

“Finalized” means sealed against silent replacement, not successful. A finalized record may describe a passing run, a zero-reward failure, or a run marked partial because some provenance was unavailable.

The word `ablation` appears in some code and filenames. It usually means changing one factor at a time to test cause and effect. Our campaign does less: it runs a fixed grid of public cases and context settings to describe what happens.

The turn limit applies per session. A persistent trial normally has one session, while a fresh-context trial opens one session per checkpoint and another session for each retry. The conditions therefore do not have equal total turn capacity. The run order is fixed too. The averages can help us spot questions, but they cannot prove that one memory condition caused better results.

Why PR13 mattered: once a result was final, its supporting files and software identity were frozen. Later code edits, changed working files, or a different model connector could not silently redefine that historical record. If a completed run had already saved valid evidence, publication could resume without rerunning the model.

Boundary: PR13 made campaign records trustworthy. It did not establish a causal effect or add the richer engineering world.

Why the next step was needed: the handover between trusted AEC-Bench logic and a model-running environment still needed an exact, enforceable boundary.

### Step 5 — PR14: Separate host authority from environment execution

PR14 introduced two strict forms:

1. The host sends an **episode request**.
2. The environment returns an **episode result**.

An **episode** is one work session with a fixed identity and limits across this boundary. In fresh-context mode, one episode handles one checkpoint.

“Typed” means the forms allow an exact set of named fields. Extra fields are rejected.

A **session** is one continuous AI conversation. An **attempt** is one try at completing a checkpoint; a retry opens another attempt.

The request tells the environment:

> Work on this checkpoint, in this workspace, under this host-created session and attempt identity, using this AI setup, visibility policy, and turn limit—the maximum number of conversation turns.

The environment may report:

> This exact session completed or failed. The environment used this connector and model and counted this many tokens—small pieces of text used for usage accounting.

It may not report:

> The engineering answer is correct, the task passed, or the reward is 1.

Those decisions remain with AEC-Bench and the task-owned verifier. The environment cannot grade itself.

The episode request receives a hash, so recovery and finalization can prove which exact request the environment received. A failed attempt's candidate answer is preserved under that failed attempt and cannot silently become the retry's answer.

Why PR14 mattered: a compatible fresh-context environment could execute one checkpoint without gaining control over advancement, correctness, or reward.

Boundary: PR14 defined the handover for fresh-context episodes; it did not demonstrate hosted execution or training.

Why the next step was needed: PR14 covered one fresh conversation working on one checkpoint. PR15 needed to show that an external framework could carry one continuing conversation across the whole lifecycle while AEC-Bench kept the same control.

### Step 6 — PR15: Export and test one persistent lifecycle in a local Prime/Verifiers-compatible environment

**Prime** is a platform for evaluating and training AI models. **Verifiers** is the Python framework used to define environments that Prime can run. PR15 used Verifiers locally only; it did not use Prime's hosted service. A **rollout** is one AI journey through a task.

PR15 added and tested a local Verifiers environment capable of letting one rollout cover one complete persistent lifecycle:

```text
one model
+ one continuing conversation
+ all three checkpoints
= one rollout
```

The connection to Prime/Verifiers is intentionally small. It reuses the existing task package and current AEC-Bench source code instead of copying them, and checks their digital fingerprints before setup and reward.

Inside the rollout, the AI can list and read visible files, write the current submission, submit a checkpoint, and revisit an earlier accepted checkpoint. AEC-Bench still controls evidence release. Only the final task verifier can award reward; an incomplete rollout receives zero.

Why PR15 mattered: a locally generated Verifiers environment could carry scripted actions through all three checkpoints while AEC-Bench retained control of evidence, progression, checking, and reward.

Boundary: PR15 established a tested local execution capability using scripted tool actions. It did not call a model provider or demonstrate hosted training, model performance, or a fresh-versus-persistent comparison.

Why the next step was needed: before running separate test cases, we needed a conservative rule for what a holdout result is allowed to mean.

### Step 7 — PR16: Define honest holdout reporting

The word **transfer** is easy to misuse. Good performance on a different case does not automatically show that the model learned from an earlier case or that the earlier interaction caused the improvement.

PR16 added an evidence-only evaluator. Although its code name includes `transfer`, its allowed claim is narrower: **descriptive holdout generalisation**, meaning a report of how one selected setup performed on separate records without claiming that earlier cases caused any improvement.

The evaluator does not call a model, rerun a task, or rerun a verifier. It reads TrialRecords and frozen snapshots; incomplete or unverifiable records are marked ineligible.

It receives:

- **public calibration records:** records declared as public calibration support for the chosen setup;
- **holdout target records:** records explicitly labelled as targets outside public calibration; and
- a **selected condition**, meaning the exact AI setup: model, connector, software fingerprint, context mode, visibility policy, and turn limit that every eligible record must match.

The evaluator rejects incomplete records, records not labelled as public calibration or holdout, runs made with a different setup, and records whose saved fingerprints no longer match. It also requires every holdout package to differ from every valid calibration package. Only then does it report the existing verifier scores.

PR16 cannot prove that the setup was chosen before anyone saw the holdout. Different file contents also do not prove that the holdout is a genuinely different engineering problem. Later work must create the private boundary and freeze the condition before any holdout is used.

PR16 is **build-only**. That means the checking function exists for other code to call, but there is no public command, private-target campaign runner, or standard place to publish its summaries yet. This avoids creating a path through which secret holdout information could accidentally be written into public results.

Why PR16 mattered: it established the wording and evidence contract before we spent money on model runs or exposed a private target.

Boundary: PR16 defines eligibility rules and permitted wording only. It creates neither the holdout cases nor a transfer result.

Why the next step was needed: the interaction still followed a mostly fixed evidence schedule. The model could react to new information but could not choose what information to seek.

### Step 8 — PR17: Let an AI request more evidence and change what it sees next

In real engineering work, reviewers ask for information:

- “Show me the governing source revision.”
- “Give me the outlet inspection record.”
- “I need the updated calculation note before I can close this finding.”

PR17 added generic support for that behaviour. A checkpoint may now declare a public **request catalogue** containing:

- safe request names;
- a plain description of each request;
- any prerequisite request that must come first; and
- a finite request budget.

The public catalogue's fixed schema has no hidden source-path or expected-answer field. Its titles and descriptions are free text, so task authors must still avoid leaking hints through that prose. A task-owned hidden map connects each public request name to its real evidence folder.

The model calls:

```text
request_evidence(checkpoint_id, request_id, reason)
```

The host supplies the real session and attempt identity. The first valid request for an item reveals only the selected packet and consumes one request ticket. Repeating the same successful request is safe and costs nothing extra. A well-formed but disallowed request—wrong checkpoint, unknown name, missing prerequisite, or no tickets left—reveals nothing and consumes no ticket.

AEC-Bench records every nonblank request made from the active session after checking that the task package is intact. This includes requests that release evidence, repeat an earlier request, or are rejected by the request rules. Each permanent receipt shows the attempt, reason, budget change, outcome, and file fingerprints. Blank calls, wrong-session calls, and damaged packages do not become request actions; they return a system error and may fail the attempt. Only one process can update the run at a time, and an interrupted save can be recovered from the saved record.

Requested evidence and spent budget survive a retry. A branch inherits the request history, released evidence, and spent budget accumulated through its branch point. Its visibility policy may still hide some inherited evidence from the model, while the audit copy remains.

The request tool works in all three local execution modes: one continuing conversation, fresh conversations, and the Prime/Verifiers environment. Tasks with no request choices keep their existing tools, and each run uses one consistent tool set. AEC-Bench includes the request history in its saved experiment records so later checks can see exactly what the model asked for.

PR17 tested this general mechanism with generated local task packages and scripted request calls. It proves the capability and audit contract, not that a model will choose useful evidence. It did **not** add request choices to SSC-03's four public calibration variants; the richer hydraulic task still needs to define useful engineering requests.

Why PR17 mattered: this is the first layer where the model can choose which one of several declared evidence packets becomes visible within a checkpoint. Earlier submission actions could trigger the next fixed release, but could not choose its contents.

```text
model chooses a permitted request
  -> host checks the menu, prerequisites, and budget
  -> one selected evidence packet becomes visible
  -> the model's next decision can use that evidence
```

Boundary: PR17 changed which evidence a task with request choices could make visible. It did not change hydraulic physics, measure model performance, or update the learner.

Why PR18 is needed: we now need an executable engineering world whose outputs follow deterministically from its inputs.

### Optional reference: the full run sequence after PR17

For a package configured with request choices, the complete flow is now:

1. AEC-Bench validates the task package and creates the run state.
2. It reveals the active checkpoint's ordinary evidence and, if that checkpoint declares requestable extra evidence, its public request catalogue. Future checkpoint catalogues remain hidden.
3. It opens an attempt owned by one model session.
4. The model reads visible files.
5. The model may spend its finite request budget on declared evidence packets.
6. Every recorded request action and every released file is durably preserved.
7. The model writes its checkpoint submission.
8. AEC-Bench archives a submission that has the expected shape and only then reveals the next checkpoint.
9. The lifecycle repeats until closeout or failure.
10. The task verifier checks the accumulated engineering state.
11. The experiment manager records metrics and exact provenance.
12. AEC-Bench freezes a TrialRecord and snapshot.
13. A later evaluator may read those frozen records without rerunning the model.

Steps 1–10 describe lifecycle execution itself. Steps 11–13 occur when that run is wrapped in the campaign and finalization machinery; a bare local or Prime rollout does not automatically publish a TrialRecord.

### Where we stand before PR18

We now have:

- controlled evidence release;
- explicit memory and visibility conditions;
- checks for correct changes and correct non-changes;
- four public, controlled test cases;
- reproducible planning for batches of runs and frozen records protected by digital fingerprints;
- a strict host/environment boundary;
- a tested local external model-running environment capable of carrying one continuing review through all checkpoints;
- rules for honestly reporting results on separate test cases; and
- limited request actions that can reveal declared evidence.

We still do not have:

- an executable drainage-calculation world containing temporary stormwater storage, flow-control outlets, pipes, pits, and a checked water-level profile;
- model actions that change physical engineering state;
- a protected source of private test cases;
- a completed public model campaign;
- evidence that a model improved across runs; or
- continual learning.

PR18 will add a deterministic hydraulic world: the same inputs must always produce the same checked outputs, and every run must remain tied to the exact set and revisions of its input files. PR18 will not yet give the AI hydraulic control. The planned PR19 layer will connect limited AI actions to those computations.

For the planned steps beyond PR17, read the [SSC-03 richer interaction roadmap](ssc03-richer-interaction-roadmap.md).

### Glossary for the terms most likely to appear during PR18

The implementation terms below are safe to skip on a first reading.

| Term | Plain-language translation |
|---|---|
| **Adapter** | The connector between AEC-Bench and a model-running system. |
| **Provider** | The service or local runtime that supplies model responses. |
| **Package** | The generated task folder containing public instructions, evidence, hidden host data, and lifecycle rules. |
| **Materialize** | Generate that concrete package folder from a reusable task definition. |
| **Artifact** | Any saved file used or produced by a run. |
| **Content-bound** | Tied to exact file contents, so changing the bytes changes the identity. |
| **Immutable** | Treated as unchangeable after publication; later edits are detected and rejected. |
| **Canonical** | The authoritative copy used for checking and recovery. |
| **Projection** | A controlled model-visible copy or view of authoritative information. |
| **Transaction** | The complete durable record of one request and its result. |
| **Atomic** | A save becomes visible as a complete unit or not at all. |
| **`fsync`-durable** | The program asks the operating system to push saved data to durable storage before declaring success. |
| **Lock-serialized** | Only one writer may change the relevant run state at a time. |
| **Idempotent** | Repeating the same successful action has no extra effect or cost. |
| **Hydraulic engine or solver** | The calculation program that turns drainage inputs into flows, levels, velocities, and storage results. |
| **Detention basin** | Temporary stormwater storage that slows the release of water. |
| **Outlet** | The structure through which stored water leaves the basin. |
| **Orifice** | A restricted opening used to control flow. |
| **Emergency weir** | A higher overflow path used when normal storage or outlet capacity is exceeded. |
| **Tailwater** | The downstream water level pushing back against an outlet or pipe. |
| **HGL** | Hydraulic grade line: a way of showing water pressure and level along the network. |
| **Freeboard** | The safety height between the expected water level and the top of a basin or structure. |
| **Deterministic** | The same declared inputs always produce the same checked outputs. |

## Best Analogy

Use this as an analogy, not as a literal description: imagine a drainage engineer reviewing a project inside a controlled records room run by a strict clerk.

| In our system | In the records room |
|---|---|
| Model | The reviewing engineer |
| Host | The clerk controlling the room |
| Lifecycle | The review from initial issue through response and closeout |
| Checkpoint | One formal review meeting |
| Evidence release | The folder issued for that meeting |
| Submission | The engineer's signed review sheet |
| Persistent context | The same engineer attends every meeting and remembers the discussion |
| Fresh context | A new engineer starts each meeting |
| Visibility policy | Which old folders and review sheets the new engineer receives |
| Verifier | The checker separate from the room operator who decides whether the review is correct |
| Ledger | The permanent project register |
| TrialRecord and snapshot | The register entry plus a sealed evidence box |
| PR17 request catalogue | A menu of extra folders the engineer may request |
| PR17 request budget | A limited number of request tickets |
| Holdout | A different sealed project used as the later test |

PR10–PR16 built the staged room, memory experiments, authority rules, and records vault around the existing checker. PR17 made it possible for a task with request choices to let the engineer choose from a limited menu of extra folders. PR18 begins constructing the working hydraulic model. PR19 will connect the engineer's choices to hydraulic calculations.

The analogy's limit is important: a human engineer may learn permanently from the project. Our current runs do not update the AI model. It receives context and files during a run; no durable model learning has been shown.

## Boundary Examples

| Case | Fit | Why |
|---|---|---|
| Give an AI one 200-page report in one prompt | Not a lifecycle | This is a large-input task, but evidence does not arrive over time. |
| Release evidence A, require a submission, then release B | Good for PR10 | This is a staged evidence lifecycle, but the schedule is still fixed by the host. |
| Keep one conversation across all three checkpoints | Good for persistent context | The model has conversation memory, but this is not continual learning. |
| Start a fresh conversation and provide earlier submissions | Good for artifact memory | The conversation is new, but saved task memory is deliberately visible. |
| Release an administrative note that changes no engineering fact | Good for PR12 | The correct behaviour is retention, not unnecessary editing. |
| Let a task offer the AI one declared source packet to request | Good for PR17 | A limited action changes what the AI sees next. It does not change the hydraulic world. |
| Let an AI change a flow-control opening, called an orifice, and recompute water levels | Future fit | This is a physically consequential interaction planned after the executable world exists. |
| Read frozen public and holdout TrialRecords | Partial | This supports descriptive holdout reporting, not a causal transfer claim. |
| Update model weights later from a collected batch of runs | Outside PR10–PR17 | This is post-training. |
| Repeatedly update durable learner state as new encounters arrive | Outside PR10–PR17 | This is continual learning. |

## Flashcards

| Front | Back |
|---|---|
| What makes a task long-horizon rather than merely long? | Information and decisions unfold over time, and later work depends on preserving the right earlier state. |
| Why does AEC-Bench control evidence release and reward? | So the model or execution environment cannot reveal future evidence, advance itself, or grade its own work. |
| What is the difference between persistent context and continual learning? | Persistent context remembers one conversation. Continual learning creates durable learning across encounters or runs. |
| What did PR11 add beyond the final reward? | Diagnostics for initial accuracy, acquisition, update quality, retention, and interference. |
| Why are PR12's four variants called calibration variants? | They are public, controlled cases used to understand behaviour and choose a future setup, not secret holdouts. |
| Why is PR13's campaign descriptive rather than causal? | Runs stay in one fixed order, and some conditions receive more total model turns than others, so differences cannot confidently be attributed to the memory condition alone. |
| What authority does the PR14 environment not have? | It cannot decide checkpoint acceptance, correctness, pass/fail, or reward. |
| What exactly did PR17 allow a model action to change? | Which declared evidence packet becomes visible, within prerequisites and a finite request budget. It did not change hydraulic physics. |

## Recall Prompts

- Reconstruct the three-checkpoint SSC-03 story without looking back. Why is the package not ready after the response review?
- Explain the difference between conversation memory, saved task state, and learning in model weights.
- Describe a case where the final answer is correct but PR11 acquisition should still be poor.
- Explain why an irrelevant new document is useful for testing retention.
- Describe the difference between the host and the environment using your own analogy.
- Explain why a matching hash establishes identity but not engineering truth.
- State the strongest honest claim supported by PR16.
- State exactly what PR17 proves and the first thing it still cannot do.

## Open Questions

- Which hydraulic engine can run reliably and reproducibly in the supported PR18 environment?
- What is the smallest detention, outlet, pipe, tailwater, and HGL world that is still recognisably an engineering system?
- Which input changes should force recomputation, and which outputs should remain unchanged?
- How will we prove that the executable world's reports and checker calculations use the same set and revisions of input files?
- Which public evidence requests are genuinely equivalent in information value, and how should request budgets be set?
- At what point should a model action change physical state rather than only reveal evidence?
- What private target is structurally different enough to test generalisation without leaking its rules?
- Which AI setup will be chosen and locked before any holdout is used?
- What additional evidence would be required before we could say “post-training helped,” “the model transferred,” or “continual learning occurred”?
