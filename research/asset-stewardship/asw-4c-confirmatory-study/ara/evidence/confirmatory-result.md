# Confirmatory result

Status: complete.

## Frozen authority

- Authorization ID: `asw-4c-theo-approved-2026-07-31`.
- Token-measurement amendment:
  `asw-4c-theo-token-measurement-2026-07-31`.
- Maximum provider requests: 1,024.
- Maximum phase spend: USD 37.00.
- Maximum model turns per trajectory: 16.
- Maximum output tokens per provider call: 2,048.
- Provider cache, advisor, bash, and external search: disabled.

Token use was measured and was not a validity stop. The runner retained input
and output token use separately.

## Coverage

- Planned trajectories: 64.
- Observed trajectories: 64.
- Complete matched blocks: 32.
- Eligible trajectory outcomes: 60.
- Analyzable matched blocks: 28.
- Required minimum analyzable blocks: 28.
- Host faults, current-view arm: 3.
- Host faults, structured-handover arm: 1.
- Host-fault arm imbalance: 2.
- Permitted maximum arm imbalance: 2.

Four matched blocks were excluded under the frozen host-fault rule. No missing
pair was replaced.

## Paired result

The estimand is structured handover minus current station view.

- Paired risk difference: 0.00.
- Two-sided 95% interval: 0.00 to 0.00.
- Bootstrap replicates: 20,000.
- Bootstrap seed: 20260729.
- Meaningful absolute effect threshold: 0.25.
- Pairs with continuity success in both arms: 16.
- Pairs with continuity failure in both arms: 12.
- Pairs with different outcomes between arms: 0.

The frozen conclusion is `inconclusive`. The structured handover did not change
the binary outcome in an analyzable pair. The frozen rule uses `refuted` only
for a meaningful harmful effect, so a precisely observed zero difference
remains `inconclusive`.

## Treatment totals

Current station view:

- 32 trajectories;
- 29 eligible outcomes;
- 13 eligible continuity failures;
- 16 eligible continuity successes; and
- 3 host faults.

Structured handover:

- 32 trajectories;
- 31 eligible outcomes;
- 15 eligible continuity failures;
- 16 eligible continuity successes; and
- 1 host fault.

Treatment totals include eligible counterparts from host-fault blocks. The
paired estimate uses only the 28 complete eligible blocks.

## Provider use

- Provider requests: 380.
- Retained measured input tokens: 3,356,400.
- Retained measured output tokens: 169,046.
- Retained measured total tokens: 3,525,446.
- Estimated spend: USD 13.865403.
- Maximum retained output tokens in one call: 2,048.
- Cache use: zero.
- Advisor calls: zero.
- Task-reward mutations: zero.

One concurrent-tool host fault retained two provider calls but did not retain
their token counts. The token totals above are the retained measured totals and
exclude this one explicit gap.

## Integrity

The final report was independently reloaded and recomputed from all 64
completion records. Its content identity is
`20486a67ea13f9c41b0ee7b790d484d1930d15a382f137a499ac84cdd8ced18b`.
No trajectory was repeated or replaced, and the retained evidence passed the
credential scan.
