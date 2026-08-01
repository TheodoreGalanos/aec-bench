# ASW-6A-R real-agent result

## Outcome

The one approved real-agent run completed without a provider error. It
published one typed review through the closed reviewer tools. The independent
review verifier rejected the content, so C005 is rejected for this run.

The submission receipt status `accepted` means that the immutable review was
published. It is not a pass claim. The independent verification report owns
the content result and has `valid: false`.

## Correct parts

- Finding: `wrong_component_evidence_citation`.
- Missing evidence: `evidence-0000-functional-checks-pump-a`.
- Disposition: `reject_closeout`.
- Unaffected duty: `obligation-0000-pump-a-verification`.
- The review correctly explained that Pump A closeout cited Pump B functional
  checks.

## Rejected parts

- The expected affected set contains only `closeout-record-pump-a`. The agent
  also included `work-order-pump-a` and
  `restriction-0000-pump-a-run-in`.
- The expected follow-up contains the canonical actions
  `correct-functional-check-citation` and `reissue-pump-a-closeout`. The agent
  supplied natural-language actions and extra work for the two added records.
- The expected source references are the closeout record and the two functional
  check records. The agent supplied those records and six additional records.

The exact report therefore records:

- `finding_matches: true`
- `affected_records_match: false`
- `unaffected_duties_match: true`
- `missing_evidence_matches: true`
- `disposition_matches: true`
- `follow_up_matches: false`
- `source_references_match: false`
- `valid: false`

## Usage and cost

- Provider calls: 3 of 6.
- Model turns: 3 of 6.
- Tool calls: 2 of 4.
- Input tokens: 13,852.
- Output tokens: 2,075.
- Total tokens: 15,927.
- Reported analysis tokens: not reported separately.
- Analysis-token accounting: included in output tokens.
- Cache read and write tokens: 0.
- Estimated spend: 79,949 micro-USD, or USD 0.079949.

The production cost function independently reproduced 79,949 micro-USD from
the stored authority and token counts.

## Interpretation

The provider, closed tools, durable evidence path, token capture, cost capture,
and private verifier all operated as designed. The model found the planted
issue but did not match the private exact target.

The run also exposed a contract question for later work: the public
`required_follow_up` field accepts arbitrary non-empty strings, while the
private target expects exact canonical action codes. This run is preserved as
a negative result. The target was not relaxed and the provider was not called
again.
