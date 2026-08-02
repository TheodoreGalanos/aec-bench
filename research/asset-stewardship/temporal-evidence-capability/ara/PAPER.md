---
ara_schema_version: "0.1"
title: Temporal evidence capability
---

# Temporal evidence capability

This artifact records the provider-free implementation of time-bound documentary
evidence for the synthetic wastewater pump-station world.

The work is one implementation stage. Historical TE0 through TE4 labels remain
planning references only. Production code and tests use functional names.

The intended result includes a rights-preserving immutable corpus, deterministic
search and fetch, durable access state, exact budget accounting, information-set
binding, handover, replay, independent verification, Harbor evidence, and
`TrialRecord` reload.

Temporal Study 1, external archive providers, and opaque provider pilots are not
part of this provider-free stage.

## Result

The complete local capability passed its focused technical gate. The gate
contained 22 corpus, retrieval, persistence, session, verification, Harbor,
`TrialRecord`, and installed-interface tests. Scoped Ruff and MyPy checks also
passed. No evidence-provider or model-provider call was made.

The review retains task semantics in the wastewater pump-station template and
promotes only strict `TrialRecord` subtypes for completed temporal world
evidence. A real model-agent run remains part of the later, separately approved
shakedown and must capture analysis-token use with the other usage measures.
