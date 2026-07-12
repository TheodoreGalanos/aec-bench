---
title: From Evidence Requests to Consequential Engineering Worlds
date: 2026-07-13
topic: AEC-Bench long-horizon work from PR18 through PR21
tags: [aec-bench, long-horizon, ssc-03, hydraulics, calibration]
status: captured
---

# Learning Capsule: From Evidence Requests to Consequential Engineering Worlds

## One-Line Takeaway

PR18–PR21 turned a controlled review lifecycle into an auditable hydraulic world that a real model can act inside and complete, while campaign selection, holdout generalisation, post-training, and continual learning remain future evidence.

## Starting Intuition

**First reading:** Read [the four-step stack](#the-four-step-stack), [the concrete hydraulic story](#the-concrete-hydraulic-story), [what the two pilots taught us](#what-the-two-pilots-taught-us), and [the laboratory analogy](#best-analogy). The detailed PR sections are reference material.

**Scope:** This guide freezes the story after PR21 and its second out-of-campaign pilot. Here, “built” means implemented, tested, and published on the named branch. At the capture date, PR10 is merged and PR11–PR21 are still stacked draft pull requests.

At the end of PR17, the model could make one meaningful choice: it could request one of several declared evidence packets. The host checked the request, revealed only the selected packet, and recorded the action.

That was a genuine interaction, but the world still answered mainly with documents. A request changed what the model could see. It did not change a flow, water level, storage volume, or downstream decision.

The next tempting idea was simple:

> Connect the model to a hydraulic solver and call the environment realistic.

That skips several hard questions.

- Which exact source revision did the calculation use?
- Which earlier result is still current after a revision?
- Which dependency makes a later result stale?
- Can the model invent an operation or escape the declared task?
- Who decides whether a reported engineering conclusion is correct?
- How can a private target remain private while using the same host machinery?
- How do we choose one public execution condition before seeing that target?

The real task was therefore larger than adding a calculation function. We needed a small engineering world whose state transitions, calculations, evidence, and decisions remained attributable from beginning to end.

The supported SWMM Python package was probed first. Its namespace imported, but its native solver and output modules did not run successfully in the tested local Python environments, and no compatible local executable was available. Rather than relabel a different calculation as SWMM, PR18 introduced an explicitly synthetic, benchmark-owned deterministic hydraulic world.

That choice matters. The current world is useful because it is controlled and auditable. It is not authority-approved design software, a project model, or proof of SWMM fidelity.

## Refined Understanding

PR18–PR21 should be understood as four different control layers:

```text
PR18: build a deterministic engineering world
  ↓
PR19: let bounded model actions operate inside that world
  ↓
PR20: let a structurally different private authority use the same host safely
  ↓
PR21: preregister the public comparison and freeze one condition before private use
```

The key distinction is between **environment richness** and **learner persistence**.

- Environment richness asks whether actions reveal information, produce calculations, change current state, and create consequences that later decisions must respect.
- Learner persistence asks whether the model itself changes across separate encounters—for example through updated weights or another durable learning state.

PR18–PR21 move strongly along the first axis. The model weights remain fixed. A continuing conversation can adapt to evidence inside one rollout, but that is context use, not continual learning.

### The four-step stack

| Step | Pull request | Plain-language question |
|---|---|---|
| 1 | [PR #18](https://github.com/TheodoreGalanos/aec-bench/pull/18) | Can we build one checked hydraulic world where the same declared inputs always produce the same source-bound outputs? |
| 2 | [PR #19](https://github.com/TheodoreGalanos/aec-bench/pull/19) | Can a model request bounded calculations, encounter a source revision, reuse current work, and recompute stale work? |
| 3 | [PR #20](https://github.com/TheodoreGalanos/aec-bench/pull/20) | Can a private task authority mount one sealed target without teaching the public repository how to discover or export it? |
| 4 | [PR #21](https://github.com/TheodoreGalanos/aec-bench/pull/21) | Can we preregister the public comparison, preserve every result, and freeze one exact condition before the sealed target is used? |

### Four different kinds of evidence

These layers produce different evidence and should not be mixed together.

| Evidence | What it establishes | What it does not establish |
|---|---|---|
| Deterministic task proof | The host, operations, calculations, and verifier agree on a known execution path. | That a language model can find or follow that path. |
| One real-model pilot | One fixed model completed or failed one specific interaction under one condition. | Reliable performance across variants or conditions. |
| Completed preregistered campaign | Comparable immutable records exist for every declared public cell. | Generalisation to an unseen private target. |
| Sealed holdout audit | The frozen public condition was evaluated on a structurally different private target. | That earlier interaction caused learning or that model weights changed. |

### The concrete hydraulic story

The public SSC-03 interaction uses two scenarios:

- `design-10yr`, the smaller design event; and
- `major-100yr`, the larger major event.

The lifecycle has three checkpoints.

#### 1. Baseline analysis

The model receives the baseline source and a public catalogue of permitted operations. It must execute six calculations:

```text
design hydrology -> design detention/outlet -> design HGL
major hydrology  -> major detention/outlet  -> major HGL
```

Each downstream calculation names the exact prerequisite action that produced its input. The model then submits two source-bound decisions and an honest readiness judgement.

#### 2. Revision analysis

A declared public revision becomes available. In the `major_idf_revision` case, the major-event rainfall intensity changes while the design-event inputs remain the same.

The correct path is selective:

```text
activate the source revision

design chain:
  hydrology already current
  detention/outlet already current
  HGL already current

major chain:
  recompute hydrology
  recompute detention/outlet
  recompute HGL
```

An `already_current` result is not a shortcut invented by the model. The host compares exact calculation inputs and prerequisite lineage. It points back to the canonical earlier artifacts and consumes no calculation budget.

The model must retain the unaffected design decision byte-for-byte, replace the affected major decision, and record the supersession lineage connecting old and new decision IDs.

#### 3. Closeout review

Closeout permits no new hydraulic operations. The model must propagate the selected run references, report references, accepted decisions, supersession lineage, readiness decision, and claim boundary into one final memo.

This checks whether engineering evidence reaches the downstream document that relies on it. A correct calculation that never reaches the decision record is not a complete review.

### Why physical failure can still earn full task reward

The hydraulic world contains screening criteria for flow, velocity, hydraulic grade line, storage, and freeboard. A revised scenario may fail one of them.

The task does not reward the model for pretending the design passes. It rewards correct review behaviour. A model can earn full task reward by reporting that the current source-bound result is not screening-ready and naming the failed criteria accurately.

### Step 1 — PR18: Build the deterministic hydraulic world

PR18 created `ssc03.public.detention-network.v1`, a small metric detention, outlet, and pipe-network world. It includes:

- two catchments;
- a detention basin;
- an orifice and emergency weir;
- a short pipe and pit network;
- downstream tailwater; and
- explicit checks for discharge, velocity, HGL, storage, and freeboard.

A run is bound to the exact source state and calculation request. It produces deterministic JSON results, time-series evidence, a report, and a run manifest. The verifier independently recomputes the expected values and checks the file hashes and tolerances rather than trusting a stored `passed` field.

PR18 also preserved the recovered EPA SWMM Example 3 source packet and its provenance as a separate reference. It did not pretend that the seven-subcatchment example was the new two-catchment benchmark world.

Why PR18 mattered: AEC-Bench gained an executable engineering consequence with content-bound inputs and outputs.

Boundary: PR18 was model-independent. It did not give the AI a hydraulic tool, establish SWMM equivalence, or produce model-performance evidence.

### Step 2 — PR19: Connect bounded actions to the world

PR19 exposed four kinds of public lifecycle operation:

- activate the one declared source revision;
- run hydrology for one declared scenario;
- run detention and outlet analysis for the declared option; and
- project network HGL for the declared boundary.

The model supplies the checkpoint, public operation ID, current visible-source hash, and a reason. The host supplies session and attempt ownership. The model cannot name arbitrary files, code, physical parameters, or hidden expected results.

Every valid call becomes an immutable transaction. It records:

- the pre-action and post-action observable-state hashes;
- exact physical source hashes;
- calculation input projection;
- prerequisite action IDs;
- budget arithmetic;
- result and artifact hashes; and
- whether the operation was computed, reused, activated, or rejected.

The same operation contract works in persistent local execution, fresh-context execution, and the local Prime/Verifiers surface. The environment still cannot award reward. The host invokes the task-owned verifier after the lifecycle is complete.

Why PR19 mattered: the model's action could now produce an engineering calculation whose output constrained later work.

Boundary: deterministic scripted task proofs showed the path worked, but they did not show that a real language model could navigate it.

### Step 3 — PR20: Add a sealed private-provider boundary

Public calibration is useful only if a later target remains separate. PR20 added an explicit external provider protocol for one private package builder, operation resolver, and verifier.

The provider is bound to one canonical package path and its exact file and directory-tree hashes for one active execution context. It is never added to public template, lifecycle, variant, resolver, or verifier registries. There is no automatic plugin scan or target discovery.

A generic host-written receipt says only that the package is a holdout and that public registration and export are forbidden. It contains no target name, source path, prompt, operation ID, expected answer, verifier rule, or free-form note.

Normal Prime export, public experiment recording, and ordinary TrialRecord finalisation reject a sealed package. Those records are full-fidelity audit artifacts and would expose private prompts, paths, hashes, and verifier identity. PR20 refuses to call them redacted when they are not.

An out-of-tree pump-station proof exercised the production tools and provider boundary. It completed three checkpoints and four prerequisite-bound operations, and the provider-supplied verifier passed all five gates. That was a deterministic boundary proof, not a language-model holdout run.

Why PR20 mattered: a structurally different target could use the same host machinery without becoming publicly discoverable.

Boundary: private full-fidelity recording, redacted publication, model execution, and holdout generalisation remain PR22 work.

### Step 4 — PR21: Preregister public calibration and freeze one condition

PR21 connected the four public PR19 variants to the campaign runner. The runner cannot use static gold action IDs because real operation IDs are created during execution. A registered task-owned smoke environment therefore executes the real operation graph and builds valid submissions from runtime evidence during credential-free inspection.

The public plan contains four variants:

- an administrative revision that changes no calculation input;
- a major-event rainfall revision;
- an outlet-geometry revision; and
- a tailwater revision.

Each variant is planned under four context and memory conditions. The current one-repetition design expands to 16 public trials. It is descriptive calibration, not a randomised causal experiment.

The selection policy is declared before execution. After every planned immutable TrialRecord exists, the selector:

1. checks complete public coverage;
2. rejects incomplete, unverifiable, identity-drifting, or protocol-drifting candidates;
3. retains valid incorrect outcomes instead of discarding inconvenient scores;
4. selects the highest mean verifier reward; and
5. uses a canonical identity tie-break declared in advance.

The write-once freeze binds the selected model, adapter, dependency bytes, execution mode, visibility policy, request limit, operation protocol, tool schema, public records, and selection policy. It refuses to run while a sealed holdout is mounted.

Why PR21 mattered: the public condition can be chosen from preregistered evidence before the private target is exposed.

Boundary: the full public campaign has not run, so no condition has been selected or frozen.

### What the two pilots taught us

The first real-model pilot used `au.anthropic.claude-sonnet-4-6`, persistent context, and the public `major_idf_revision` package. The model completed all three checkpoints and followed the intended 13-operation path. It retained the design chain, recomputed the major chain, and reached the correct engineering readiness conclusion.

The immutable reward was still `0.0`.

The failure came from the public interface. One shared instruction described fields that belonged only at closeout and named two memo concepts differently from the verifier's exact keys. The model wrote a substantively coherent record in a structurally invalid shape. The host accepted undeclared top-level fields and revealed the mismatch only at terminal verification.

A diagnostic replay changed only the submission shape: it removed undeclared top-level fields and renamed the two ambiguous memo keys. The unchanged operation evidence and engineering decisions then passed all 11 verifier gates. This isolated an interface defect; it did not rewrite the pilot or turn it into passing model evidence.

PR21 then made each checkpoint contract explicit:

- the public instruction lists the exact permitted top-level keys;
- closeout-only fields no longer appear at earlier checkpoints;
- the exact memo keys are named directly;
- the model-facing write tool rejects missing or undeclared fields while correction is still possible; and
- the host submission gate checks the same contract again before archival.

The contract change also preserved historical identity. Extensible checkpoints omit the behaviour-neutral default from canonical hashing, while strict checkpoints encode the stricter policy. The first immutable pilot remains readable under the repaired runtime.

The second pilot used a freshly materialised fixed-contract package under the same model, variant, persistent condition, and request cap. It completed:

- one persistent session;
- one submitted attempt at each checkpoint;
- 13 operation actions;
- all three required selective-reuse decisions; and
- closeout with no new calculation.

It produced no rejected submission or provider failure. The terminal verifier passed all 11 gates at reward `1.0`.

That result establishes one narrow but important fact:

> One fixed real model can complete one repaired-contract public hydraulic lifecycle while respecting selective recomputation and evidence propagation.

It does not establish reliable performance across variants, the best memory condition, holdout generalisation, transfer, post-training improvement, or continual learning. Both pilots sit outside the preregistered campaign and cannot select a condition.

### Where the stack stands after PR21

We have:

- a deterministic public hydraulic world;
- model-facing operations with physical consequences;
- source revision and dependency invalidation;
- selective recomputation and exact reuse;
- immutable operation, session, attempt, and submission history;
- one structurally distinct sealed-provider proof;
- a preregistered public campaign and deterministic condition selector; and
- one successful real-model confirmation pilot.

We still need:

- final integration of the stacked PRs;
- the complete public campaign;
- one write-once selected-condition freeze;
- private full-fidelity storage and allowlisted redacted reporting;
- the preregistered sealed holdout audit;
- descriptive holdout generalisation results;
- broader SME-reviewed engineering worlds; and
- any training or durable learner update.

## Core Concepts

- **Deterministic world:** The same declared source and operation inputs produce the same checked engineering outputs.
- **Source-bound operation:** Every calculation names the exact visible and physical source state used.
- **Prerequisite lineage:** A downstream calculation points to the exact upstream action that supplied its input.
- **Currentness:** The host decides whether exact inputs and dependencies still match; the model cannot merely declare a result current.
- **Selective recomputation:** Recalculate the affected chain while retaining unaffected canonical evidence.
- **Task authority:** The task owns verifier meaning; the host invokes verification and reward; the model-running environment owns neither.
- **Sealed provider:** One explicit private authority bound to one exact package, absent from public discovery and export.
- **Public calibration:** Declared public cases used to compare execution conditions before private evaluation.
- **Frozen condition:** One write-once selected setup whose complete identity must match later evaluation.
- **Interface validity:** The public submission contract must expose the exact shape the host accepts, separately from engineering correctness.
- **Descriptive generalisation:** Reporting performance on a separate target without claiming that earlier interaction caused learning.
- **Continual learning:** Durable learner change across encounters; persistent context inside one rollout is not enough.

### Glossary

| Term | Plain-language meaning |
|---|---|
| **Hydrology** | The calculation that turns rainfall and catchment properties into inflow. |
| **Detention/outlet analysis** | The calculation of temporary storage, water level, and controlled discharge. |
| **HGL** | Hydraulic grade line, used here to check water level and pressure through the downstream network. |
| **Source revision** | A declared change to the input basis used by later calculations. |
| **Operation catalogue** | The public menu of calculations currently available to the model. |
| **Operation budget** | The finite number of calculations the checkpoint permits. Reusing current work consumes none. |
| **Action ID** | The permanent identity of one requested operation and its recorded outcome. |
| **Run manifest** | The receipt tying a calculation result to its exact request, source, engine, and output files. |
| **Supersession lineage** | The explicit link from an outdated decision to its justified replacement. |
| **Claim boundary** | The structured statement preventing synthetic screening evidence from being described as project approval or real design evidence. |
| **Pilot** | A deliberately limited run used to test the complete model-facing path before the campaign. |
| **Campaign cell** | One planned combination of public variant, execution condition, model setup, and repetition. |
| **Freeze** | The immutable record of the selected public condition and the evidence used to choose it. |
| **Redaction** | Publishing a small allowlisted summary while keeping target content and full traces private. |

## Best Analogy

Use this as an analogy, not a literal description: imagine a controlled hydraulic laboratory attached to a strict project records office.

| In AEC-Bench | In the laboratory and records office |
|---|---|
| Model | The reviewing engineer |
| Host | The records clerk controlling access and signing every transaction |
| PR18 world | The calibrated laboratory rig |
| Source state | The approved test setup sheet |
| Operation catalogue | The menu of tests the engineer may request |
| Action ID | The laboratory job number |
| Prerequisite lineage | The chain showing which earlier test supplied the next test's input |
| `already_current` | Reusing a valid certified result because the relevant setup did not change |
| Source revision | A formally issued change to the test setup |
| Verifier | The independent checker comparing the record with the rig's rules |
| PR20 sealed provider | A separate locked laboratory whose specimen and checking rules stay private |
| Public campaign | The declared qualification programme run before the private exam |
| Frozen condition | The sealed choice of engineer, procedure, and records policy used for the exam |
| PR22 redacted result | A public pass/fail summary that does not reveal the private specimen |

The analogy's limit is the same as before PR18: a human engineer may retain durable learning from the work. The current AI model uses a conversation and saved artifacts during one run, but its weights do not change.

## Boundary Examples

| Case | Fit | Why |
|---|---|---|
| Run the deterministic hydraulic engine directly and pass its verifier | Good deterministic proof | It checks the world and verifier, but no language model chose the operations. |
| Let a model request a declared hydrology calculation using the current source hash | Good PR19 interaction | A bounded action produces source-bound engineering evidence. |
| Recompute every chain after a revision even when one chain's inputs are unchanged | Poor selective behaviour | It may reach the right answer, but it ignores available currentness evidence and wastes actions. |
| Reuse a result after one of its exact dependencies changed | Invalid | The host should mark the result stale and reject unsupported reuse. |
| Correctly report that the revised major event fails a screening criterion | Good review behaviour | Physical failure is evidence to report, not a reason to fabricate readiness. |
| Treat the PR20 deterministic pump-station proof as model holdout performance | Invalid claim | No model provider executed that proof. |
| Use the first pilot's diagnostic shape repair as its official reward | Invalid | The immutable pilot remains reward zero; the diagnostic only isolates root cause. |
| Use the successful second pilot to choose the best memory condition | Insufficient | It covers one variant and one condition outside the preregistered campaign. |
| Complete all 16 public campaign cells and freeze the declared selector's winner | Good public calibration | It supports one selected public condition, not unseen-target generalisation. |
| Run that frozen condition once on the sealed target and report allowlisted aggregates | Good descriptive holdout audit | It reports separate-target performance without revealing the target. |
| Claim that good holdout performance proves the model learned from public runs | Invalid causal claim | The fixed model may simply have had the capability already. |
| Update model weights offline using public interactions and compare on untouched targets | Future post-training fit | This could test post-training, but the training pipeline and comparison do not yet exist. |
| Carry versioned learner updates through a nonstationary stream and measure forgetting | Future continual-learning fit | Durable cross-run updates and retention tests are required. |

## Flashcards

| Front | Back |
|---|---|
| What did PR18 add that PR17 did not have? | A deterministic hydraulic world whose source-bound calculations produce checked physical outputs. |
| Why is the PR18 world not called SWMM? | The tested native SWMM path did not run reliably, so the benchmark uses an explicitly synthetic deterministic fallback rather than making a false fidelity claim. |
| What makes a PR19 operation source-bound? | It records the exact visible and physical source hashes, input projection, prerequisites, request, result, and artifacts. |
| Who decides whether an operation result is correct and whether the task earns reward? | The task-owned verifier, invoked and validated by the host—not the model or execution environment. |
| What does `already_current` mean? | Exact inputs and prerequisite lineage still match an earlier canonical result, so the host can reuse it without recomputation. |
| What does PR20 keep out of public registries and records? | The private target identity, content, operation map, verifier rules, prompts, paths, and full-fidelity artifacts. |
| Why can the two PR21 pilots not select a condition? | They were deliberately run outside the preregistered complete public campaign. |
| What did the first pilot reveal? | The engineering path was coherent, but the public submission shape was ambiguous and caused an immutable zero-reward result. |
| What did the second pilot establish? | One real fixed model completed one repaired-contract public lifecycle and passed all 11 task gates. |
| What must exist before the PR21 freeze can be written? | A valid immutable TrialRecord for every planned public campaign cell under the exact preregistered manifest. |
| What is the strongest allowed PR16/PR22 result wording? | Descriptive holdout generalisation under the frozen condition. |
| Why is persistent context not continual learning? | The model can use earlier conversation within one rollout, but no durable learner state or weights change across separate runs. |

## Recall Prompts

- Reconstruct the baseline, revision, and closeout hydraulic lifecycle without looking back.
- Explain why the design chain is reusable under `major_idf_revision` while the major chain is stale.
- Describe the authority split among model, environment, host, and task verifier.
- Explain why an exact hash proves identity but does not prove engineering realism.
- State what the deterministic pump-station proof establishes and what it does not.
- Explain why the first model pilot remains reward zero even though a shape-only diagnostic passed.
- State the strongest honest claim supported by the second pilot.
- Describe every condition that must be satisfied before the public selector may freeze a winner.
- Explain why a successful sealed audit would still not demonstrate learner transfer.
- Place environment richness, post-training, and continual learning on separate axes in your own words.

## Open Questions

- What does the final base-to-head audit require before PR11–PR21 can be merged and used as the evidence-grade experiment commit?
- How will the full public campaign behave across all four variants and all four memory conditions?
- Does the one-repetition descriptive design provide enough stability for condition selection, or should a later campaign increase repetitions before conclusions are strengthened?
- Which condition will the preregistered selector freeze, and which candidates will be ineligible because of failures or identity drift?
- What access-controlled record store and allowlisted publication schema should PR22 use for full private evidence and redacted public results?
- Which engineering reviewers must sign off the pump-station ranges, curves, NPSH checks, wet-well rules, and tolerances before the target is frozen?
- Which additional worlds are structurally different enough to test broader generalisation without becoming unrelated tasks?
- When should a future environment allow actions that change design variables rather than only execute declared analyses?
- What ordinary post-training experiment would separate training benefit from selection and contamination effects?
- What durable learner state, update authority, rollback, and forgetting tests would be required before continual learning becomes a legitimate claim?
