You are the independent reviewing engineer for a product submittal issue package covering steel product identity, mill certificates, heat traceability, application schedule, deviations, review comments, and criteria.

A source packet has been placed in `/workspace/sources/`. It contains a document register, submittal manifest, mill certificates, heat traceability table, product application schedule, deviation register, and a criteria memo with review comments. The packet is a task-owned synthetic source pack; treat it as the only source of numeric truth for this review.

Your job is not to redesign the product or accept the material for construction. Your job is to decide whether the package is ready to issue, and to produce an auditable review record.

## Review Workflow

1. Inventory the source packet before drawing any conclusion. Record every document ID, revision, and status.
2. Build an identity ledger: submittal, product, grade, heats, certificates, application schedule, deviation register, and criteria memo.
3. Check for source conflicts, stale revisions, copied standards or use cases, missing evidence, heat/certificate mismatches, unresolved deviations, and open critical comments before accepting any package claim.
4. Recompute the package's own checks only where they answer review items, using the assessment bases stated in the criteria memo. Do not import methods or values from outside the packet.
5. Assign exactly one status to every review item: `pass`, `fail`, `not_applicable`, or `insufficient_data`.
6. Do not invent missing values. Mark missing evidence as `insufficient_data` and request the exact missing field and source. A value that a source explicitly marks as pending or awaiting confirmation is missing evidence of this kind: it does not make otherwise-reconciling identifiers inconsistent and does not make evidence that is present untraceable; the check that cannot be completed without it takes `insufficient_data`.
7. Convert every failure into a finding with a source pointer, affected object, consequence, and corrective action.
8. Issue a readiness decision that reconciles with your matrix, findings, information requests, and action register.

## Review Matrix

Assess each item and give it exactly one status:

| Item | Review question |
|---|---|
| RLR-01 | Packet completeness: are all required submittal, certificate, traceability, application, deviation, and criteria files present with IDs and revisions? |
| RLR-02 | Object identity: do the submittal, product, grade, heat numbers, certificates, application rows, deviations, and criteria memo stay consistent? |
| RLR-03 | Certificate and property basis: are chemistry, mechanical properties, certificate scope, and source revisions traceable, current, and recomputable? |
| RLR-04 | Product compliance adequacy: do carbon equivalent, yield strength, tensile strength, certificate coverage, and traceability clear the source criteria for the same product use case? |
| RLR-05 | Application consequence: is the same product grade, standard, and application use case used across the schedule, certificates, deviations, and criteria? |
| RLR-06 | Source-status resilience: are certificate coverage and heat traceability source-backed for the issue package? |
| RLR-07 | Comment and action closure: is every critical comment closed, and are carried minor comments owner/action controlled? |
| RLR-08 | Readiness consistency: does your final decision match your own matrix, findings, information requests, and action register? |
| RLR-09 | Claim boundary: does your review avoid unsupported approval, compliance, source-hardening, executable-verifier, or benchmark-readiness claims? |

## Boundary Rules

- Use the review matrix definitions to decide the most specific affected item from the source packet. Do not infer a status from this instruction alone.
- If a source value needed for a recomputation is absent, omit the dependent `computed_evidence` key and raise an information request for the missing field and source. Do not include missing or unrecomputable keys with `null`, `0`, or placeholder values.
- Assign additional failures only when the source packet gives independent evidence for them; do not double-count one source issue across unrelated matrix rows.
- RLR-08 passes when the readiness decision reconciles with the review matrix, findings, information requests, and action register.
- Every finding, information request, and action must name one exact RLR item. Use a single RLR item per register row; do not write combined items such as `RLR-04/RLR-06`.
- Do not rename computed_evidence keys.

## Output

Write your complete review to `/workspace/output.md`. Explain your reasoning briefly in prose, then end with exactly one fenced JSON block:

```json
{
  "source_inventory": [{"doc_id": "...", "revision": "...", "status": "..."}],
  "identity_ledger": {
    "submittal": "...",
    "product": "...",
    "grade": "...",
    "heat_a": "...",
    "heat_b": "...",
    "certificates": "...",
    "application_schedule": "...",
    "deviation_register": "...",
    "criteria_memo": "..."
  },
  "review_matrix": {
    "RLR-01": {"status": "pass|fail|not_applicable|insufficient_data", "evidence": "..."},
    "RLR-02": {"status": "...", "evidence": "..."},
    "RLR-03": {"status": "...", "evidence": "..."},
    "RLR-04": {"status": "...", "evidence": "..."},
    "RLR-05": {"status": "...", "evidence": "..."},
    "RLR-06": {"status": "...", "evidence": "..."},
    "RLR-07": {"status": "...", "evidence": "..."},
    "RLR-08": {"status": "...", "evidence": "..."},
    "RLR-09": {"status": "...", "evidence": "..."}
  },
  "computed_evidence": {
    "carbon_equivalent_max": 0.0,
    "carbon_equivalent_margin": 0.0,
    "yield_strength_margin_mpa": 0.0,
    "tensile_strength_margin_mpa": 0.0,
    "certificate_coverage_count": 0.0,
    "traceability_match_count": 0.0
  },
  "findings": [
    {"item": "RLR-0X", "severity": "critical|minor", "source_id": "...", "object_id": "...", "consequence": "...", "action": "..."}
  ],
  "information_requests": [
    {"item": "RLR-0X", "missing_field": "...", "source_id": "..."}
  ],
  "action_register": [
    {"action": "...", "owner": "...", "linked_item": "RLR-0X"}
  ],
  "readiness_decision": "ready_to_issue|ready_with_carried_actions|not_ready_to_issue",
  "claim_boundary_statement": "..."
}
```

Rules for the structured block:

- `computed_evidence` values must come from your own recomputation from packet source values. Omit a key only when its inputs are missing from the packet, then raise the matching information request instead. Do not include missing or unrecomputable keys with `null`, `0`, or placeholder values.
- Every `fail` needs at least one finding with a non-empty `source_id`, `object_id`, `consequence`, and `action`.
- Every `insufficient_data` needs an information request naming the exact missing field and its source document.
- Every `not_applicable` needs a scope reason in its matrix `evidence`.
- Carried actions must appear in `action_register` with an owner.
- `readiness_decision` must reconcile with your matrix: unresolved failures or missing critical evidence mean the package is not ready.
- `claim_boundary_statement` must state that this review covers a task-owned synthetic source packet and does not claim authority approval, accepted project evidence, full standards compliance, source-pack hardening, executable-verifier readiness, or benchmark readiness.
