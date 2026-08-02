---
ara_schema_version: "0.1"
title: Retrieval-state continuity study specification
---

# Research continuation summary

This artifact freezes the first study of retrieval-state continuity in the
synthetic wastewater pump-station world. It does not use a model or an external
evidence service.

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

## Boundary

The study code stays in
`aec_bench.experiments.retrieval_state_continuity`. The documentary corpus,
gateway, access process, and verifier stay in the wastewater pump-station task
template. No shared contract or provider adapter is added.

A real model-agent shakedown needs separate approval. It can test model,
harness, tool, carrier, cost, cleanup, attrition, and token instrumentation. Its
records cannot enter the confirmatory estimate. It must capture input, output,
reported analysis, and total tokens, including a clear marker when the provider
does not report analysis tokens separately.

Artifact layers:

- `logic/claims.yaml` records the supported design and analysis claims.
- `logic/experiments.yaml` records the provider-free checks.
- `evidence/index.yaml` points to the frozen values and validation evidence.
- `trace/exploration_tree.yaml` records the decision and next approval gate.
- `staging/observations.yaml` retains the open shakedown authority.
