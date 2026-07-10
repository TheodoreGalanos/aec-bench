You are the independent reviewing engineer for a roadside cabinet serviceability issue package covering one cabinet setout/elevation, flood HGL and inundation table, enclosure heat derating note, critical load and backup schedule, feeder/access note, owner serviceability criterion, and criteria/comments memo.

A source packet has been placed in `/workspace/sources/`. It contains a document register, cabinet setout/elevation note, flood HGL and inundation table, enclosure heat derating note, critical load and backup schedule, feeder/access note, owner serviceability criterion, and criteria/comments memo. The packet is a task-owned synthetic source pack; treat it as the only source of numeric truth for this review.

Your job is not to redesign the cabinet, enclosure, battery, feeder, or lighting system. Your job is to decide whether the package is ready to issue, and to produce an auditable review record.

## Review Workflow

1. Inventory the source packet before drawing any conclusion. Record every document ID, revision, and status.
2. Build an identity ledger: cabinet, flood/HGL table, heat derating note, critical load schedule, backup energy schedule, feeder/access note, serviceability scenario, and criteria memo.
3. Check for source conflicts, stale revisions, copied scenarios, missing evidence, cabinet/event mismatches, and open critical comments before accepting any package claim.
4. Recompute the package's own calculations only where they answer review items, using the assessment bases stated in the criteria memo. Do not import methods or values from outside the packet.
5. Assign exactly one status to every review item: `pass`, `fail`, `not_applicable`, or `insufficient_data`.
6. Do not invent missing values. Mark missing evidence as `insufficient_data` and request the exact missing field and source. A value that a source explicitly marks as pending or awaiting confirmation is missing evidence of this kind: it does not make otherwise-reconciling identifiers inconsistent and does not make evidence that is present untraceable; the check that cannot be completed without it takes `insufficient_data`.
7. Convert every failure into a finding with a source pointer, affected object, consequence, and corrective action.
8. Issue a readiness decision that reconciles with your matrix, findings, information requests, and action register.

## Review Matrix

Assess each item and give it exactly one status:

| Item | Review question |
|---|---|
| RLR-01 | Packet completeness: are all required cabinet setout, flood/HGL, heat derating, load/backup, feeder/access, owner-criterion, and criteria files present with IDs and revisions? |
| RLR-02 | Object identity: do the cabinet ID, chainage, flood/HGL event, heat event, critical load, backup schedule, feeder, and access note stay consistent? |
| RLR-03 | Cabinet serviceability basis: are flood freeboard, heat derating, backup runtime, and feeder voltage-drop basis traceable, current, and recomputable? |
| RLR-04 | Cabinet serviceability adequacy: do flood freeboard and thermal derated capacity clear the source criteria for the same cabinet and event case? |
| RLR-05 | Scenario consequence: is the same flood, heat, and outage event case used across cabinet setout, HGL, heat derating, load, backup, feeder, access, and owner criterion? |
| RLR-06 | Secondary power/access resilience: are backup energy, BESS power, feeder voltage drop, maintenance access, and road-lighting AECI source-backed and internally consistent with the selected cabinet load? |
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
    "cabinet": "...",
    "flood_hgl_table": "...",
    "heat_derating_note": "...",
    "critical_load_schedule": "...",
    "backup_energy_schedule": "...",
    "feeder_access_note": "...",
    "serviceability_scenario": "...",
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
    "cabinet_freeboard_m": 0.0,
    "flood_freeboard_margin_m": 0.0,
    "thermal_derated_capacity_w": 0.0,
    "thermal_margin_w": 0.0,
    "thermal_utilization": 0.0,
    "battery_runtime_h": 0.0,
    "battery_margin_h": 0.0,
    "bess_power_margin_kw": 0.0,
    "bess_energy_margin_kwh": 0.0,
    "feeder_voltage_drop_percent": 0.0,
    "voltage_drop_margin_percent": 0.0,
    "road_lighting_aeci_kwh_m2_y": 0.0
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
