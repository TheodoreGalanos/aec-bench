You are the independent reviewing engineer for a level-crossing warning, controls, backup-power, and communications issue package.

A source packet has been placed in `/workspace/sources/`. It contains a document register, route profile, sighting and warning-time worksheet, crossing control layout, backup-power and communications schedule, degraded-mode operations note, and criteria/comments memo. The packet is a task-owned synthetic source pack; treat it as the only source of truth for this review.

Your job is not to redesign the crossing. Your job is to decide whether the package is ready to issue, and to produce an auditable review record.

## Review Workflow

1. Inventory the source packet before drawing any conclusion.
2. Build an identity ledger for the route profile, crossing ID, sighting worksheet, control layout, backup schedule, communications link, degraded-mode scenario, and criteria memo.
3. Check for source conflicts, stale revisions, copied scenarios, missing evidence, crossing identity drift, and open critical comments before accepting package claims.
4. Recompute only the evidence needed for review items, using the assessment bases stated in the criteria memo.
5. Assign exactly one status to every review item: `pass`, `fail`, `not_applicable`, or `insufficient_data`.
6. Do not invent missing values. Mark missing evidence as `insufficient_data` and request the exact missing field and source.
7. Convert every failure into a finding with a source pointer, affected object, consequence, and corrective action.
8. Issue a readiness decision that reconciles with your matrix, findings, information requests, and action register.

## Review Matrix

| Item | Review question |
|---|---|
| RLR-01 | Packet completeness: are the required route, sighting, control, backup, communications, degraded-mode, criteria, and comment sources present with IDs and revisions? |
| RLR-02 | Object identity: do the route profile, sighting worksheet, control layout, backup schedule, communications link, and degraded-mode note refer to the same crossing and approach? |
| RLR-03 | Warning-time basis: are speed, strike-in distance, warning-time, gate timing, backup-power, feeder, and fiber bases traceable, current, and recomputable? |
| RLR-04 | Crossing warning and backup adequacy: do warning time, gate-horizontal timing, and backup runtime clear the source-owned criteria? |
| RLR-05 | Degraded-mode scenario: is the same degraded operating case used across warning, backup, feeder, fiber, and operator sources? |
| RLR-06 | Feeder and communications resilience: are voltage-drop and fiber-link margins source-backed and internally consistent with the selected load? |
| RLR-07 | Comment and action closure: is every critical comment closed, and are carried minor comments owner/action controlled? |
| RLR-08 | Readiness consistency: does your final decision match your own matrix, findings, information requests, and action register? |
| RLR-09 | Claim boundary: does your review avoid unsupported approval, compliance, source-hardening, executable-verifier, or benchmark-readiness claims? |

## Boundary Rules

- Use the review matrix definitions to decide the most specific affected item from the source packet.
- If a source value needed for recomputation is absent, omit the dependent `computed_evidence` key and raise an information request for the missing field and source.
- Assign additional failures only when the source packet gives independent evidence for them; do not double-count one source issue across unrelated matrix rows.
- RLR-08 passes when the readiness decision reconciles with the review matrix, findings, information requests, and action register.
- Every finding, information request, and action must name one exact RLR item.
- Do not rename computed_evidence keys.

## Output

Write your complete review to `/workspace/output.md`. Explain your reasoning briefly in prose, then end with exactly one fenced JSON block:

```json
{
  "source_inventory": [{"doc_id": "...", "revision": "...", "status": "..."}],
  "identity_ledger": {
    "route_profile": "...",
    "sighting_warning_time": "...",
    "crossing_layout": "...",
    "backup_power_comms": "...",
    "degraded_mode": "...",
    "criteria_comments": "...",
    "crossing_id": "..."
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
    "maximum_train_speed_m_s": 0,
    "provided_warning_time_s": 0,
    "strike_in_distance_m": 0,
    "warning_time_margin_s": 0,
    "gate_horizontal_margin_s": 0,
    "design_signal_load_w": 0,
    "required_battery_capacity_ah": 0,
    "installed_battery_capacity_ah": 0,
    "battery_runtime_h": 0,
    "battery_runtime_margin_h": 0,
    "dc_voltage_drop_margin_percent": 0,
    "fiber_link_margin_db": 0
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
- Carried actions must appear in `action_register` with an owner.
- `readiness_decision` must reconcile with your matrix.
- `claim_boundary_statement` must state that this review covers a task-owned synthetic source packet and does not claim authority approval, accepted project evidence, full standards compliance, source-pack hardening, executable-verifier readiness, or benchmark readiness.
