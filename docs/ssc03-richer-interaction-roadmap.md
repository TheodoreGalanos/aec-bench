# ABOUTME: Defines the staged path from SSC-03 evidence review to action-conditioned hydraulic interactions.
# ABOUTME: Separates implemented substrate claims from future environment, holdout, and model-evidence work.

# SSC-03 Richer Interaction Roadmap

## Direction

The objective is not to make a static task longer. It is to approach a richer interaction in controlled steps: evidence arrives over time, the model can choose bounded information-gathering actions, those actions change what it can observe, later actions can produce engineering consequences, and every observation remains attributable to a host-owned state transition.

This is a substrate for ordinary post-training and evaluation first. It is not yet continual learning. A persistent conversation, durable state, or behavior that improves later in one rollout does not establish learning across runs or parameter updates.

## Established stack

| Layer | Established capability |
| --- | --- |
| PR10 | Host-controlled staged evidence and memory-visibility conditions |
| PR11 | Reward-independent acquisition, retention, update, and interference metrics |
| PR12 | Controlled public SSC-03 calibration variants |
| PR13 | Reproducible campaigns, immutable TrialRecords, recovery, and ledger summaries |
| PR14 | Typed host/environment episode ownership without verifier or reward delegation |
| PR15 | Local Prime rollout spanning one complete persistent lifecycle |
| PR16 | Build-only descriptive holdout evaluation from immutable evidence |
| PR17 | Bounded actions that condition model-visible evidence |
| PR18 | Deterministic, source-bound public hydraulic screening world |
| PR19 | Bounded hydraulic operations, source revision, selective recomputation, and closeout verification |

## PR17: action-conditioned evidence protocol

PR17 introduces one generic host operation:

```text
request_evidence(checkpoint_id, request_id, reason)
```

The public checkpoint contract declares request IDs, descriptions, prerequisites, and a finite budget. It contains no source paths or expected outcomes. A task-owned hidden manifest resolves each declared ID to a confined package directory.

The host binds the active session and attempt; the model cannot provide either. The first valid request publishes only the selected packet and consumes one budget unit. A repeated successful request is idempotent and consumes zero. Unknown, inactive, unsupported, prerequisite-blocked, and budget-exhausted requests produce typed, non-leaking rejections and consume zero.

Every boundary-valid request receives a globally ordered action record with pre/post observable-state hashes, budget arithmetic, outcome, session/attempt ownership, and released artifact hashes. Malformed or blank tool arguments return a bounded error without creating a lifecycle action. Canonical transactions live under `run/evidence_requests/<action-id>/`; model-visible projections live under `workspace/inbox/<checkpoint>/requests/<request-id>/`. Publication is lock-serialized, staged, fsync-durable, crash-recoverable, and reconciled to the append-only lifecycle ledger.

Requested evidence survives a failed attempt, remains consumed on retry, and is inherited by a branch through its branch point. Visibility remains policy-controlled: cumulative evidence policies retain it, while `current_release_only` hides it after checkpoint advancement without deleting audit files.

Conditional packages expose the same three-argument tool through persistent local, fresh-context, and local Prime execution. Packages with no request catalogue keep their prior tool set. Invocation manifests hash the protocol and exact tool schema; reward-independent metrics count released, repeated, rejected, and budget-consuming actions. Immutable snapshots contain the canonical transactions, workspace projections, and public catalogues.

What PR17 proves:

- a model-visible action can condition subsequent model-visible evidence;
- the resulting observation is bounded, hash-bound, and attributable;
- retry, branch, local adapter, Prime, ledger, and snapshot boundaries preserve the same action history.

What PR17 does not prove:

- that an action changes a hydraulic system;
- that a model selects useful evidence;
- transfer to a distinct target;
- learning across runs or continual learning.

## PR18: executable hydraulic world

PR18 built a small deterministic public detention/outlet/network world around the SSC-03-LH-01 direction. It uses two upstream catchments, a detention basin, an orifice and emergency weir, a short pipe/pit network, tailwater, and explicit discharge, velocity, hydraulic grade line (HGL), storage, and freeboard criteria.

The first gate was engine compatibility. Earlier probes found that `swmm-toolkit==0.17.0` imported its namespace but its native solver/output modules exited unsuccessfully under the tested Python 3.12 and 3.13 runtimes, with no local `swmm5` executable available. PR18 therefore ran a controlled compatibility matrix before selecting its explicitly named benchmark-owned deterministic fallback.

The existing EPA SWMM Example 3 detention source packet was reconciled into the PR18 stack rather than duplicated. It carries official source URLs and hashes, a model summary, manual targets, mismatch notes, verification cases, and an implementation brief.

PR18 completed with deterministic, content-bound source state, run identity, report outputs, tolerances, and verifier calculations. Its model-independent world still exposes no model-controlled hydraulic action by itself.

### PR18 implementation decision

The controlled local matrix was repeated on macOS ARM64 with `swmm-toolkit==0.17.0`. Its Python namespace imported on Python 3.13.2 and 3.12.9, but both native `solver` and `output` imports terminated with exit status 137 and no Python exception. No `swmm5` or `runswmm` executable was available. The exact evidence is recorded in `docs/ssc03-swmm-compatibility-matrix.yaml`.

PR18 therefore uses the approved fallback: `ssc03.public.detention-network.v1`, an explicitly synthetic, metric, benchmark-owned deterministic screening world. The recovered seven-file EPA Example 3 packet remains at its canonical path as a separate provenance and manual-target reference; its seven-subcatchment SWMM model is not relabelled as the new two-catchment world.

The public world exposes a model-independent materialize, run, and verify seam plus a Linux gate. It still exposes no model-facing hydraulic action. See `docs/ssc03-hydraulic-world.md`.

## PR19: interactive hydraulic lifecycle

PR19 connects the PR17 host-action pattern to PR18's executable world. Its public tool remains bounded and typed:

- activate the one declared source revision;
- run hydrology for one declared scenario;
- run detention/outlet analysis for the declared option;
- project network HGL for the declared downstream boundary.

Every boundary-valid call binds its arguments to the visible source-state hash and produces an immutable transaction. A completed calculation publishes a new result and artifact set. An `already_current` call points to the original artifacts and consumes zero budget; a rejected call publishes no result and also consumes zero. The four public calibration variants change the major-event rainfall input, tailwater, outlet geometry, or only administrative revision identity. The host identifies current work from exact calculation inputs and prerequisite action IDs, while a stale dependency is rejected.

The terminal verifier checks selective recomputation, affected-decision replacement, unaffected-decision retention, canonical PR18 run validity, run/report/memo propagation, readiness, and the claim boundary. Physical failure is not hidden: a reviewer can receive full task reward for correctly reporting that the current source does not meet a screening criterion. Extra rejected actions do not change reward. Action efficiency remains diagnostic because the public catalogue exposes currentness and prerequisite status.

Persistent local, fresh-context, and local Prime execution expose the same four-argument operation tool. Episode requests bind the public operation catalogue when active, current source, and visible operation artifacts. Immutable snapshots, TrialRecords, and experiment manifests additionally bind the canonical transactions. See [the plain-language PR19 guide](ssc03-interactive-hydraulic-lifecycle.md).

## PR20: sealed holdout boundary

Introduce an external provider seam for private materializers, operation resolvers, and verifiers. The public repository contains only generic fake-provider fixtures. Real target IDs, prompts, source packets, action mappings, gold outputs, verifier rules, and per-trial annotations remain outside public registries and exports.

The first private synthetic target should be a pump-station duty lifecycle. It shares the abstract interaction contract but changes the physical and documentary graph: wet-well levels, rising main and pump curve, system curve, duty point, power/NPSH, and selection note. This is a stronger structural holdout than a renamed stormwater network.

## PR21: preregistered campaign and condition selection

Run the public calibration campaign, select one execution condition using only public evidence, and freeze model, adapter, realized runtime dependency hash, execution mode, visibility policy, turn limit, action-protocol hash, and tool-schema hash before mounting any holdout target.

This is the first phase that needs provider credentials and a spend/repetition budget. It also needs approval that private synthetic target content may be sent to the selected provider.

## PR22: redacted one-shot audit

Run the frozen condition against the sealed target once under the preregistered repetition policy. Publish only aggregate descriptive results and generic behavioral categories. Keep exact target content, traces, verifier details, and action mappings internal. Use PR16's evaluator to report holdout generalization, not causal transfer or continual learning.

## Inputs still needed

No provider credentials are needed through PR20.

Engineering review is needed for plausible parameter ranges, coupled scenarios, tolerances, dependency invalidation, equivalent information requests, closure policy, pump curves, NPSH, wet-well behavior, and operating rules. Infrastructure work is needed for the controlled solver matrix, private package storage, access-controlled ledgers, and redacted reporting.

The progression is deliberate: first make actions observable and auditable, then make them physically consequential, then hide a structurally distinct target, and only then spend model budget.
