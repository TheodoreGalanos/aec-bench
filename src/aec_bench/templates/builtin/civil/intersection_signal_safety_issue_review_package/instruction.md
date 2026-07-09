You are the independent reviewing engineer for an intersection signal safety issue package covering one road approach, one signal group, one pedestrian crossing, and one controller timing handoff.

A source packet has been placed in `/workspace/sources/`. It contains a document register, intersection layout, approach profile, signal timing sheet, pedestrian crossing sheet, sight-distance note, controller handoff note, and a criteria memo with review comments. The packet is a task-owned synthetic source pack; treat it as the only source of numeric truth for this review.

Your job is not to redesign the intersection. Your job is to decide whether the package is ready to issue, and to produce an auditable review record.

## Review Workflow

1. Inventory the source packet before drawing any conclusion. Record every document ID, revision, and status.
2. Build an identity ledger: intersection, approach, approach chainage, datum, signal group, pedestrian crossing, controller, timing case, and sight-distance case.
3. Check for source conflicts, stale revisions, contradictory datums, copied scenarios, missing evidence, and open critical comments before accepting any package claim.
4. Recompute the package's own calculations only where they answer review items, using the assessment bases stated in the criteria memo. Do not import methods or values from outside the packet.
5. Assign exactly one status to every review item: `pass`, `fail`, `not_applicable`, or `insufficient_data`.
6. Do not invent missing values. Mark missing evidence as `insufficient_data` and request the exact missing field and source. A value that a source explicitly marks as pending or awaiting confirmation is missing evidence of this kind: it does not make otherwise-reconciling identifiers inconsistent and does not make evidence that is present untraceable; the check that cannot be completed without it takes `insufficient_data`.
7. Convert every failure into a finding with a source pointer, affected object, consequence, and corrective action.
8. Issue a readiness decision that reconciles with your matrix, findings, and action register.

## Review Matrix

Assess each item and give it exactly one status:

| Item | Review question |
|---|---|
| RLR-01 | Packet completeness: are all required source documents present with IDs and revisions? |
| RLR-02 | Object identity: do intersection, approach, chainage, datum, signal group, crossing, controller, and case stay consistent across documents? |
| RLR-03 | Traffic safety basis: are stopping distance, yellow interval, all-red interval, and sight-distance calculations traceable to the current basis and recomputable? |
| RLR-04 | Approach user safety: do available sight distance and pedestrian clearance both clear the source-owned criteria? |
| RLR-05 | Timing scenario consequence: does the timing case use this approach's design speed and crossing case rather than a copied scenario? |
| RLR-06 | Signal handoff resilience: are controller timing, clearance intervals, and exported signal group values source-backed and internally consistent? |
| RLR-07 | Comment and action closure: is every review comment closed, or carried with an owner and agreed action, or blocked by named missing data? |
| RLR-08 | Readiness consistency: does your final decision match your own matrix, findings, and action register? |
| RLR-09 | Claim boundary: does your review avoid unsupported approval, compliance, or acceptance claims? |

## Output

Write your complete review to `/workspace/output.md`. Explain your reasoning briefly in prose, then end with exactly one fenced JSON block:

```json
{
  "source_inventory": [{"doc_id": "...", "revision": "...", "status": "..."}],
  "identity_ledger": {
    "intersection": "...",
    "approach": "...",
    "approach_chainage": "...",
    "datum": "...",
    "signal_group": "...",
    "pedestrian_crossing": "...",
    "controller": "...",
    "timing_case": "...",
    "sight_distance_case": "..."
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
    "stopping_distance_m": 0.0,
    "sight_distance_margin_m": 0.0,
    "yellow_interval_s": 0.0,
    "all_red_interval_s": 0.0,
    "ped_clearance_required_s": 0.0,
    "ped_clearance_margin_s": 0.0,
    "grade_adjusted_braking_distance_m": 0.0
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

- `computed_evidence` values must come from your own recomputation from packet source values. Omit a key only when its inputs are missing from the packet, then raise the matching information request instead.
- Every `fail` needs at least one finding with a non-empty `source_id`, `object_id`, `consequence`, and `action`.
- Every `insufficient_data` needs an information request naming the exact missing field and its source document.
- Every `not_applicable` needs a scope reason in its matrix `evidence`.
- Carried actions must appear in `action_register` with an owner.
- `readiness_decision` must reconcile with your matrix: unresolved failures or missing critical evidence mean the package is not ready.
- `claim_boundary_statement` must state that this review covers a task-owned synthetic source packet and does not claim authority approval, accepted project evidence, full standards compliance, source-pack hardening, executable-verifier readiness, or benchmark readiness.
