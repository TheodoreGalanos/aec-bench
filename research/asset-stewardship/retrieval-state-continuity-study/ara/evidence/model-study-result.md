# Real-model shakedown and confirmatory result

## Authorized boundary

- Provider: `amazon-bedrock-au-geographic`.
- Model: `au.anthropic.claude-sonnet-4-6`.
- Host credential profile: `BedrockViewer-831926582066`.
- Adapter: direct `tool_loop` over closed station tools.
- Data sent: synthetic pump-station handover and retrieval context only.
- Credentials and real client data sent: none.
- Analysis-token reporting: not reported separately by the adapter; included in
  output tokens.

## Shakedown record

The shakedown records cannot enter the confirmatory estimate.

| Generation | Outcome | Provider calls | Input tokens | Output tokens | Spend USD |
|---|---:|---:|---:|---:|---:|
| `model-shakedown-v1` | Default credential context rejected before inference | 0 | 0 | 0 | 0.000000 |
| `model-shakedown-v2` | Typed tool rejection became a fatal adapter failure | 4 | 23,485 | 1,722 | 0.105914 |
| `model-shakedown-v3` | Two-run runtime and verifier path completed | 8 | 59,681 | 3,523 | 0.255077 |

The v2 failure led to a bounded repair. The station tool wrapper now returns
typed contract rejections to the model so it can correct the request. It does
not bypass the station contract or convert a rejected action into an accepted
action.

## Frozen confirmation

- Generation: `confirmatory-v2`.
- Planned and observed runs: 64.
- Complete and analyzable matched pairs: 32.
- Eligible world histories: 8.
- Integrity gate: passed.
- Validity gate: passed.
- Paired risk difference, absent minus preserved: `0.03125`.
- 95% world-history-clustered interval: `[0.0, 0.09375]`.
- Minimum meaningful effect: `0.25`.
- Frozen conclusion: `refuted`.
- Provider calls: 260.
- Input tokens: 2,293,157.
- Output tokens: 125,187.
- Total tokens: 2,418,344.
- Recorded spend: USD 9.633005.
- Task reward mutations: 0.

Treatment endpoints were:

- retrieval state absent: 32 failures from 32 runs;
- retrieval state preserved: 31 failures and 1 success from 32 runs.

## Independent identities

- Manifest:
  `2a99ca0b59f26c7218fc6468a317554b59ebc3046f69375837221f2f25f2d046`.
- Plan:
  `27adfa26e78c0456d4a0ab64a783e942f2d06f1dad08da5dbd7cca2bdd63b23c`.
- Report:
  `e69328a71e314e3b18ed1683f606cf24aa862a489493804cc3a7399f3a6f439f`.
- Aggregate execution:
  `d6b674214e345de75c9190c1e41f101f99036365c2739b6725376c76c6322def`.

`reload_and_verify_model_study` reloaded the exact aggregate execution and
recomputed the report and trial totals. The reloaded identities matched the
stored identities.

## Proposal-time audit

All 64 runs contain a durable station proposal:

- 63 proposals occurred at 7,200,000 seconds, before the scored window;
- 1 preserved-state proposal occurred at 7,203,600 seconds, when the scored
  window opened;
- 0 runs fetched the delayed material record;
- 0 runs relied on the delayed material record.

The dominant action was a request for post-maintenance verification. This was a
safe response to an open verification requirement already visible in the live
station state. The frozen scorer only accepted a consequential proposal after
the evidence-availability event. The result is therefore valid for the frozen
operational rule, but it does not isolate retrieval continuity after the event
from the model's ability to wait for that event.

## Retained source evidence

- `research/asset-stewardship/retrieval-state-continuity-study/results/model-shakedown-v1`
- `research/asset-stewardship/retrieval-state-continuity-study/results/model-shakedown-v2`
- `research/asset-stewardship/retrieval-state-continuity-study/results/model-shakedown-v3`
- `research/asset-stewardship/retrieval-state-continuity-study/results/confirmatory-v2`
