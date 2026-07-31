# ASW-4 result audit

## Frozen question

Under matched continuing pump-station histories, does a structured handover
reduce required-follow-up continuity failure when compared with a complete
current station view?

## Exact result

- Planned trajectories: 64.
- Durable completion records: 64.
- Analyzable matched blocks: 28.
- Required minimum analyzable blocks: 28.
- Host faults: 4.
- Host-fault arm imbalance: 2.
- Permitted maximum arm imbalance: 2.
- Both-treatment success pairs: 16.
- Both-treatment failure pairs: 12.
- Pairs with different outcomes: 0.
- Structured-handover minus current-view paired risk difference: `0.00`.
- Two-sided 95 percent interval: `0.00` to `0.00`.
- Frozen conclusion: `inconclusive`.
- Repeated or replacement trajectories: 0.

The frozen conclusion stays `inconclusive` because the decision rule used
`refuted` only for a meaningful harmful effect. The exact zero difference is
neither a supported benefit nor a qualifying harmful effect.

## Execution evidence

- Provider requests: 380.
- Retained measured input tokens: 3,356,400.
- Retained measured output tokens: 169,046.
- Retained measured total tokens: 3,525,446.
- Estimated spend: USD 13.865403.
- Explicit token-measurement gap: two calls in one concurrent-tool host fault.
- Endpoint-prefix recoveries: 2.
- Final report content identity:
  `20486a67ea13f9c41b0ee7b790d484d1930d15a382f137a499ac84cdd8ced18b`.

The four host faults were an expired AWS credential, the initial adapter token
stop, a concurrent stale-view mutation, and a denied provider token-count
request. They were retained under the frozen rules. No affected trajectory was
repeated or replaced.

## Permitted interpretation

The study machinery completed and the evidence is usable under the frozen
rules. Structured handover did not change the binary outcome in the tested
world. The study does not prove that handover can never help. It also does not
support a claim that handover helps under greater world complexity.

The exact zero difference and the absence of a frozen no-effect category show
that a later study needs a better bounded rule for negligible effects. The
binary endpoint also does not measure invalid actions, time to safe resolution,
resource efficiency, or reasoning cost.

## Sources

- `research/asset-stewardship/asw-4a-study-freeze/ara/PAPER.md`
- `research/asset-stewardship/asw-4c-confirmatory-study/ara/evidence/confirmatory-result.md`
- `research/asset-stewardship/asw-4c-confirmatory-study/ara/evidence/execution-recovery-findings.md`
- `research/asset-stewardship/asw-4c-confirmatory-study/ara/evidence/provider-free-gates.md`
