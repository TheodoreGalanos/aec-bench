You are the independent reviewing engineer for a multimodal corridor comment-response issue package covering one road corridor, one review comment, one drainage recalculation, one signal and pedestrian recalculation, one VMS operation note, and one ITS feeder check.

A source packet has been placed in `/workspace/sources/`. It contains a document register, comment register, marked-up plan and long section, drainage recalculation, signal and pedestrian recalculation, VMS operations note, electrical feeder check, and a criteria memo. The packet is a task-owned synthetic source pack; treat it as the only source of numeric truth for this review.

Your job is not to redesign the corridor. Your job is to decide whether the comment-response package is ready to issue, and to produce an auditable review record.

## Review Workflow

1. Inventory the source packet before drawing any conclusion. Record every document ID, revision, and status.
2. Build an identity ledger: corridor, comment, original and revised chainage, datum, scenario, drainage object, signal group, VMS device, and field feeder.
3. Check for source conflicts, stale revisions, chainage drift, copied scenarios, missing evidence, and open critical comments before accepting any package claim.
4. Recompute the package's own calculations only where they answer review items, using the assessment bases stated in the criteria memo. Do not import methods or values from outside the packet.
5. Assign exactly one status to every review item: `pass`, `fail`, `not_applicable`, or `insufficient_data`.
6. Do not invent missing values. Mark missing evidence as `insufficient_data` and request the exact missing field and source. A value that a source explicitly marks as pending or awaiting confirmation is missing evidence of this kind: it does not make otherwise-reconciling identifiers inconsistent and does not make evidence that is present untraceable; the check that cannot be completed without it takes `insufficient_data`.
7. Convert every failure into a finding with a source pointer, affected object, consequence, and corrective action.
8. Issue a readiness decision that reconciles with your matrix, findings, and action register.

## Review Discipline

Use the most specific review item for each defect based on the source packet and the review matrix definitions. Do not infer a status from this instruction alone.

- If a source value needed for a recomputation is absent, omit the dependent `computed_evidence` key and raise an information request for the missing field and source. Do not include missing or unrecomputable keys with `null`, `0`, or placeholder values.
- Assign additional failures only when the source packet gives independent evidence for them; do not double-count one source issue across unrelated matrix rows.
- RLR-08 is reviewer self-consistency: it passes when your readiness decision reconciles with your matrix, findings, information requests, and action register.
- Every finding, information request, and action must name one exact RLR item.

## Review Matrix

Assess each item and give it exactly one status:

| Item | Review question |
|---|---|
| RLR-01 | Packet completeness: are all required source documents present with IDs and revisions? |
| RLR-02 | Object identity: do corridor, comment, chainage, datum, scenario, drainage, signal, VMS, and feeder identities stay consistent across documents? |
| RLR-03 | Review-response basis: are the change ledger and impacted calculation count traceable to current source revisions and recomputable evidence? |
| RLR-04 | Review-response adequacy: does the changed chainage/scenario propagate through HGL, pedestrian, VMS, voltage-drop, and comment-closeout checks? |
| RLR-05 | Scenario consequence: is the same corridor scenario used across disciplines rather than copied from another corridor? |
| RLR-06 | Secondary-discipline resilience: are VMS legibility and feeder voltage-drop checks source-backed and internally consistent? |
| RLR-07 | Comment and action closure: is every review comment closed, or carried with an owner and agreed action, or blocked by named missing data? |
| RLR-08 | Readiness consistency: does your final decision match your own matrix, findings, and action register? |
| RLR-09 | Claim boundary: does your review avoid unsupported approval, compliance, or acceptance claims? |

## Output

Write your complete review to `/workspace/output.md`. Explain your reasoning briefly in prose, then end with exactly one fenced JSON block:

```json
{
  "source_inventory": [{"doc_id": "...", "revision": "...", "status": "..."}],
  "identity_ledger": {
    "corridor": "...",
    "comment": "...",
    "original_chainage": "...",
    "revised_chainage": "...",
    "datum": "...",
    "scenario": "...",
    "drainage_object": "...",
    "signal_group": "...",
    "vms_device": "...",
    "field_feeder": "..."
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
    "changed_chainage_delta_m": 0.0,
    "hgl_clearance_mm": 0.0,
    "hgl_clearance_margin_mm": 0.0,
    "ped_clearance_required_s": 0.0,
    "ped_clearance_margin_s": 0.0,
    "vms_reading_time_s": 0.0,
    "vms_message_margin_chars": 0.0,
    "feeder_voltage_drop_percent": 0.0,
    "voltage_drop_margin_percent": 0.0,
    "comment_closeout_percent": 0.0,
    "impacted_calculation_count": 0.0
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

- Do not rename computed_evidence keys. Use the exact key names shown in the schema. Use `voltage_drop_margin_percent`, not `feeder_voltage_drop_margin_percent`.
- `computed_evidence` values must come from your own recomputation from packet source values. Omit a key only when its inputs are missing from the packet, then raise the matching information request instead. Do not include missing or unrecomputable evidence keys with `null`, `0`, or placeholder values.
- Every `fail` needs at least one finding with a non-empty `source_id`, `object_id`, `consequence`, and `action`. Each `findings[].item` value must be a single RLR item such as `RLR-05`; do not combine multiple IDs in one item field.
- Every `insufficient_data` needs an information request naming the exact missing field and its source document. Each `information_requests[].item` value must be a single RLR item such as `RLR-04`.
- Every `not_applicable` needs a scope reason in its matrix `evidence`.
- Carried actions must appear in `action_register` with an owner. Each `action_register[].linked_item` value must be a single RLR item.
- `readiness_decision` must reconcile with your matrix: unresolved failures or missing critical evidence mean the package is not ready.
- `claim_boundary_statement` must state that this review covers a task-owned synthetic source packet and does not claim authority approval, accepted project evidence, full standards compliance, source-pack hardening, executable-verifier readiness, or benchmark readiness.
