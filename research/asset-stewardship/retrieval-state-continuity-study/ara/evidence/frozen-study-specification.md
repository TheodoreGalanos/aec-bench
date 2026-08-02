# Frozen retrieval-state continuity study specification

## Authority and scope

- Study: Retrieval-state continuity under delayed evidence.
- Station profile: `AU-NSW-LH-SYN-SPS-v1`.
- Evidence profile: complete local deterministic snapshot.
- External evidence provider: excluded.
- Model execution: not authorized by this specification.
- Promotion: not permitted.

## Fixed treatment

Both arms use the same certified station package, complete realised world
history, complete current station view, retrieval-clean structured handover,
local corpus, availability event, search and fetch tools, remaining budget, and
decision deadline.

The only difference is:

- absent: the fresh tenure receives no unresolved retrieval-state projection;
- preserved: the fresh tenure receives the sanitized unresolved retrieval-state
  projection with visible results, unresolved searches, and remaining budget.

The projection excludes private failure reasons, hidden frontier data, material
target hints, and verifier labels.

## Fixed scenario and time

- Material evidence: `pump-a-delayed-condition-report.v1`.
- Pre-handover world time: `7,200,000` seconds.
- Evidence availability time: `7,203,600` seconds.
- Decision deadline: `7,207,200` seconds.
- Available-to-decision interval: `3,600` seconds.
- Both arms can search again after handover.

Three development-only query routes must hide the material record before
availability and retrieve it after availability. The real deterministic gateway
must also fetch the returned material reference within the common budget.

## Fixed plan and schedule

- Independent world histories: 8.
- Model sampling repeats per history: 4.
- Matched pairs: 32.
- Planned runs: 64.
- Schedule algorithm: `seeded_balanced_adjacent_pairs_v1`.
- Schedule seed: `20260802`.
- Treatment order: two first-arm assignments per treatment within each history.
- Pair execution: adjacent.
- Trial identifiers: opaque and treatment-label free.

## Fixed budget per run

- Search calls: 2.
- Fetch calls: 1.
- References per result: 5.
- Visible retrieval bytes: 8,000.
- Visible retrieval tokens: 2,000.
- Agent turns: 12.
- Simulated retrieval duration: 0.
- External retrieval-provider spend: 0.
- Budget reset at handover: forbidden.

Model-inference tokens and spend are separate measured values. They are not
retrieval-provider spend.

## Fixed endpoint and analysis

- Endpoint: binary epistemic decision failure before the fixed deadline.
- Estimand: mean paired risk difference.
- Difference: failure without retrieval state minus failure with retrieval state.
- Minimum meaningful risk difference: 0.25.
- Uncertainty: world-history-clustered paired bootstrap percentile interval.
- Resamples: 20,000.
- Bootstrap seed: `20260802`.
- Confidence level: 95%.
- Minimum eligible world histories: 7.
- Minimum eligible pairs: 28.
- Missing-pair replacement: none.

Decision rule:

- supported: point estimate is at least 0.25 and the interval lower bound is
  above zero;
- refuted: the interval upper bound is below 0.25;
- inconclusive: neither rule applies;
- coverage blocked: the minimum history or pair coverage is not met.

The ordered gates are integrity, validity, then endpoint. Failed integrity does
not become an endpoint. Candidate-owned failure after valid delivery does.

## Fixed exclusion rule

Only a host fault before treatment delivery, or a proven treatment-invariant
host fault, can make a pair ineligible. Missing delivery, corrupt delivery,
identity drift, and incomplete pairs have typed reasons. Poor search, empty
model output, model timeout, tool failure, carrier overflow, carrier
serialization failure, and output-contract failure after valid delivery count
as epistemic decision failure.

## Permitted conclusion

The strongest later confirmatory statement is:

> Under the frozen reference corpus, availability schedule, retrieval policy,
> base continuity carrier, model condition, and budget, supplying the declared
> retrieval-state projection at handover changed the paired risk of epistemic
> decision failure by the reported amount.

This study cannot establish model learning, general use across assets or
corpora, external-provider value, or the truth and authority of all retrieved
records.
