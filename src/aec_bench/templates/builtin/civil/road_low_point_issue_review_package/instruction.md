You are the independent reviewing engineer for a road-corridor issue package covering a sag low point near roadside field equipment.

A source packet has been placed in `/workspace/sources/`. It contains a document register, road geometry, a drainage design package, a field equipment layout, a power and network schedule, a traffic operations case, and a criteria memo with review comments. The packet is a task-owned synthetic source pack; treat it as the only source of numeric truth for this review.

Your job is not to redesign the package. Your job is to decide whether it is ready to issue, and to produce an auditable review record.

## Review Workflow

1. Inventory the source packet before drawing any conclusion. Record every document ID, revision, and status.
2. Build a corridor identity ledger: road segment, chainage frame, datum, low point, cabinet, VMS, storm case, network case, and battery.
3. Check for source conflicts, stale revisions, contradictory datums, and missing evidence first.
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
| RLR-02 | Object identity: do chainage, datum, low point, cabinet, storm case, and scenario stay consistent across documents? |
| RLR-03 | Drainage basis: are the package's runoff, spread, and HGL results traceable to the stated storm case and current tailwater basis, and do they reconcile when recomputed? |
| RLR-04 | Equipment exposure: is the CAB-01 pad level adequate against the controlling water level and the required freeboard? |
| RLR-05 | Traffic operation consequence: does the VMS legibility case use this corridor's design speed and scenario? |
| RLR-06 | Power/comms resilience: do battery runtime and network headroom clear the criteria using source-backed values? |
| RLR-07 | Comment and action closure: is every review comment closed, or carried with an owner and agreed action, or blocked by named missing data? |
| RLR-08 | Readiness consistency: does your final decision match your own matrix, findings, and action register? |
| RLR-09 | Claim boundary: does your review avoid unsupported approval, compliance, or acceptance claims? |

## Output

Write your complete review to `/workspace/output.md`. Explain your reasoning briefly in prose, then end with exactly one fenced JSON block:

```json
{
  "source_inventory": [{"doc_id": "...", "revision": "...", "status": "..."}],
  "identity_ledger": {
    "road_segment": "...",
    "low_point": "...",
    "low_point_chainage": "...",
    "datum": "...",
    "cabinet": "...",
    "vms": "...",
    "storm_case": "...",
    "network_case": "...",
    "battery": "..."
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
    "peak_runoff_m3_s": 0.0,
    "gutter_approach_flow_m3_s": 0.0,
    "spread_width_m": 0.0,
    "allowable_spread_m": 0.0,
    "controlling_water_level_m": 0.0,
    "cabinet_freeboard_m": 0.0,
    "vms_message_margin_chars": 0.0,
    "battery_runtime_h": 0.0,
    "network_headroom_mbps": 0.0
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

- `computed_evidence` values must come from your own recomputation from packet source values. Omit a key only when its inputs are missing from the packet (then raise the matching information request instead).
- Every `fail` needs at least one finding with a non-empty `source_id`, `object_id`, `consequence`, and `action`.
- Every `insufficient_data` needs an information request naming the exact missing field and its source document.
- Every `not_applicable` needs a scope reason in its matrix `evidence`.
- Carried actions must appear in `action_register` with an owner.
- `readiness_decision` must reconcile with your matrix: unresolved failures or missing critical evidence mean the package is not ready.
- `claim_boundary_statement` must state that this review covers a task-owned synthetic source packet and does not claim authority approval, accepted project evidence, full standards compliance, source-pack hardening, executable-verifier readiness, or benchmark readiness.
