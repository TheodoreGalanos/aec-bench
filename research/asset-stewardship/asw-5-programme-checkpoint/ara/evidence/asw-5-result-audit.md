# ASW-5 result audit

## Frozen question

Can overlapping required follow-ups, work processes, operating limits, and
reserved resources survive interruption, cancellation, durable replay, and
agent handover without duplicated effects, lost state, or conservation errors?

## Exact result

- ASW-5 merge: `be24edd42dc16b01ff13f8a860c402ecde297501`.
- Focused ASW-5 gate: 17 passed.
- Complete pump-station cumulative gate: 163 passed.
- Strict MyPy: 24 changed source files and 5 changed test files passed.
- Ruff: the complete changed source and test boundary passed.
- Provider calls: 0.
- Direct and Harbor final state: identical.
- Direct and Harbor evaluation vector: identical.
- Replay verifier: passed.
- Independent Harbor verifier: passed.
- Fresh-agent handover count: 1.
- Live-process handover omissions: 0.
- Required-follow-up breaches: 1.
- Imported `TrialRecord` reward: `0.0`.

The access interruption suspended access-dependent work. It did not pause the
Pump A post-maintenance verification deadline. The resulting breach follows the
approved ASW-5 rule and remains visible in the evaluation vector.

## Compatibility and conservation result

- Version 1 states and receipts remain byte-preserving on reload and replay.
- Continuing a version 1 run under version 2 creates a content-addressed
  version 2 state and an explicit migration record.
- Unknown versions fail closed.
- Access and the intervention slot release on suspension, cancellation, and
  completion.
- The repair kit stays reserved during suspension and is consumed only after
  successful obstruction clearance.
- Cancelled or completed work ignores stale completion events.
- Suspended or interrupted work has no partial physical effect.
- The parent and child operating-limit chain remains visible without latent
  state leakage.

## Wider repository result

The repository-wide run recorded 7,601 passes, 21 existing skips, and 10
failures outside ASW-5. Eight failures reproduced at unchanged `origin/main`.
One test depends on the checkout directory name. One Azure reviewer test passes
alone on ASW-5 and the baseline and is order-dependent in the full run. These
existing failures remain visible but do not falsify the bounded ASW-5 claims.

## Sources

- `research/asset-stewardship/asw-5-rich-work-processes/ara/PAPER.md`
- `research/asset-stewardship/asw-5-rich-work-processes/ara/evidence/current-test-status.md`
- `research/asset-stewardship/asw-5-rich-work-processes/ara/evidence/compatibility-boundary.md`
- `research/asset-stewardship/asw-5-rich-work-processes/ara/evidence/rule-freeze.md`
