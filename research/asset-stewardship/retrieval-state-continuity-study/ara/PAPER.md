---
ara_schema_version: "0.1"
title: Retrieval-state continuity study
---

# Research continuation summary

This artifact records the first study of retrieval-state continuity in the
synthetic wastewater pump-station world. It contains the provider-free design,
real-model shakedown, frozen confirmation, and independent reload evidence.

The research question is:

> Under a fixed local corpus, ranking policy, base continuity carrier, and
> retrieval budget, does a sanitized record of unresolved pre-handover
> retrieval activity reduce decision-time failure after material evidence
> becomes accessible to a fresh tenure?

The study compares the same realised world history in two fresh agent tenures.
Both receive the same complete current station view, retrieval-clean structured
handover, tools, budget, event schedule, and decision deadline. The only
difference is whether the handover contains the sanitized unresolved retrieval
state.

## Frozen design

The plan contains eight independent world histories and four model sampling
repeats per history. This gives 32 matched pairs and 64 planned runs. Treatment
order is balanced within each history. The fixed seeded schedule keeps each pair
adjacent and uses opaque trial identities.

The primary endpoint is binary epistemic decision failure. The paired
difference is failure without retrieval state minus failure with retrieval
state. A positive value favours state preservation. The minimum meaningful
risk reduction is 0.25. Uncertainty uses 20,000 paired bootstrap resamples
clustered by world history, with a two-sided 95% interval.

The study requires at least seven eligible world histories and 28 eligible
pairs. Missing pairs are not replaced. A host fault before treatment delivery,
or a proven treatment-invariant host fault, can make a pair ineligible. A model,
tool, output, or carrier failure after valid delivery remains an outcome.

## Provider-free result

Generated analysis records exercised the study-local manifest, paired plan,
treatment delivery, failure taxonomy, clustered reducer, immutable publication,
and independent reload. The known generated input produced a paired risk
difference of 0.5 with a 95% interval of [0.5, 0.5]. This proves the analysis
rule can detect its known input. It is not a model result.

The path made zero provider calls, used zero model tokens and spend, created
zero study outcomes, changed no task reward, and retained
`promotion_permitted=false`.

## Real-model result

The authorized runtime used Amazon Bedrock model
`au.anthropic.claude-sonnet-4-6` through the direct host tool loop. The
confirmation completed all 64 planned runs, all 32 matched pairs, and all eight
world histories. Integrity and validity passed. Independent reload reproduced
execution identity
`d6b674214e345de75c9190c1e41f101f99036365c2739b6725376c76c6322def`
and report identity
`e69328a71e314e3b18ed1683f606cf24aa862a489493804cc3a7399f3a6f439f`.

The paired risk difference was `0.03125`, with a 95% interval from `0.0` to
`0.09375`. The frozen decision rule therefore returned `refuted`: the result
did not reach the minimum meaningful effect of `0.25`.

The result used 260 provider calls, 2,293,157 input tokens, and 125,187 output
tokens, for total recorded spend of USD 9.633005. The adapter did not report
analysis tokens separately; they are included in output tokens.

## Interpretation limit

All 64 agents made a station proposal. Sixty-three proposals occurred at the
pre-window time of 7,200,000 seconds. One preserved-state proposal occurred at
the decision point of 7,203,600 seconds. No run fetched or relied on the delayed
condition report.

The frozen result is valid for its declared task and endpoint. It does not show
whether retrieval state helps when the host places the agent at the open
decision point. It also does not measure the quality of safe early action: the
agents saw an open verification requirement and made the reasonable
conservative request before the scored window. A later study should separate
temporal waiting from retrieval continuity and make the delayed record material
to the action choice.

## Boundary

The study code stays in
`aec_bench.experiments.retrieval_state_continuity`. The documentary corpus,
gateway, access process, and verifier stay in the wastewater pump-station task
template. No shared contract or provider adapter is added.

The shakedown records remain excluded from the confirmatory estimate. The
provider route kept credentials host-side, and the retained study evidence
contains no credential values or real client data.

Artifact layers:

- `logic/claims.yaml` records the supported design and result claims.
- `logic/experiments.yaml` records provider-free and real-model checks.
- `evidence/index.yaml` points to the frozen values and validation evidence.
- `trace/exploration_tree.yaml` records the failures, repairs, and result.
- `staging/observations.yaml` retains the open follow-up design questions.
