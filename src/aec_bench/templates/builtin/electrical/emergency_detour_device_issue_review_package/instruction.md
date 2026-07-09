You are the independent reviewing engineer for an emergency detour device issue package covering one closure scenario, detour plan, traffic management plan, VMS message library, CCTV/VMS device set, RF link, ITS network uplink, and roadside cabinet power-continuity schedule.

A source packet has been placed in `/workspace/sources/`. It contains a document register, detour plan, VMS message library, device inventory, communications topology, power-continuity schedule, and criteria/comments memo. The packet is a task-owned synthetic source pack; treat it as the only source of numeric truth for this review.

Your job is not to redesign the detour system. Your job is to decide whether the package is ready to issue, and to produce an auditable review record.

## Review Workflow

1. Inventory the source packet before drawing any conclusion. Record every document ID, revision, and status.
2. Build an identity ledger: closure scenario, detour plan, traffic management plan, VMS device set, CCTV device set, communications link, network uplink, cabinet power supply, and message library.
3. Check for source conflicts, stale revisions, copied scenarios, missing evidence, mismatched device IDs, and open critical comments before accepting any package claim.
4. Recompute the package's own calculations only where they answer review items, using the assessment bases stated in the criteria memo. Do not import methods or values from outside the packet.
5. Assign exactly one status to every review item: `pass`, `fail`, `not_applicable`, or `insufficient_data`.
6. Do not invent missing values. Mark missing evidence as `insufficient_data` and request the exact missing field and source. A value that a source explicitly marks as pending or awaiting confirmation is missing evidence of this kind: it does not make otherwise-reconciling identifiers inconsistent and does not make evidence that is present untraceable; the check that cannot be completed without it takes `insufficient_data`.
7. Convert every failure into a finding with a source pointer, affected object, consequence, and corrective action.
8. Issue a readiness decision that reconciles with your matrix, findings, information requests, and action register.

## Review Matrix

Assess each item and give it exactly one status:

| Item | Review question |
|---|---|
| RLR-01 | Packet completeness: are all required detour, message, device, communications, power, and criteria files present with IDs and revisions? |
| RLR-02 | Object identity: do the closure scenario, detour plan, traffic management plan, VMS, CCTV, RF link, network uplink, power supply, and message library stay consistent? |
| RLR-03 | Detour and message basis: are the detour speed, VMS character height, reading rate, and selected message traceable, current, and recomputable? |
| RLR-04 | Continuity adequacy: does the battery runtime clear the required closure duration for the same critical detour device set? |
| RLR-05 | Scenario consequence: is the same emergency closure scenario used across the detour plan, device inventory, communications, power, and comments? |
| RLR-06 | Secondary-discipline resilience: are network headroom, RF link margin, and feeder voltage-drop margin source-backed and internally consistent? |
| RLR-07 | Comment and action closure: is every critical comment closed, and are carried minor comments owner/action controlled? |
| RLR-08 | Readiness consistency: does your final decision match your own matrix, findings, information requests, and action register? |
| RLR-09 | Claim boundary: does your review avoid unsupported approval, compliance, source-hardening, executable-verifier, or benchmark-readiness claims? |

## Boundary Rules

- Use the review matrix definitions to decide the most specific affected item from the source packet. Do not infer a status from this instruction alone.
- If a source value needed for a recomputation is absent, omit the dependent `computed_evidence` key and raise an information request for the missing field and source. Do not include missing or unrecomputable keys with `null`, `0`, or placeholder values.
- Assign additional failures only when the source packet gives independent evidence for them; do not double-count one source issue across unrelated matrix rows.
- Every finding, information request, and action must name one exact RLR item. Use a single RLR item per register row; do not write combined items such as `RLR-04/RLR-06`.
- Do not rename computed_evidence keys.

## Output

Write your complete review to `/workspace/output.md`. Explain your reasoning briefly in prose, then end with exactly one fenced JSON block:

```json
{
  "source_inventory": [{"doc_id": "...", "revision": "...", "status": "..."}],
  "identity_ledger": {
    "closure_scenario": "...",
    "detour_plan": "...",
    "traffic_management_plan": "...",
    "vms_device_set": "...",
    "cctv_device_set": "...",
    "communications_link": "...",
    "network_uplink": "...",
    "cabinet_power_supply": "...",
    "message_library": "..."
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
    "vms_reading_time_s": 0.0,
    "vms_message_margin_chars": 0.0,
    "required_network_mbps": 0.0,
    "network_headroom_mbps": 0.0,
    "rf_received_power_dbm": 0.0,
    "rf_link_margin_db": 0.0,
    "battery_runtime_h": 0.0,
    "battery_margin_h": 0.0,
    "feeder_voltage_drop_percent": 0.0,
    "voltage_drop_margin_percent": 0.0
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
