You are the independent reviewing engineer for a road visual operations issue package covering one road segment, lighting grid, luminaire group, CCTV schedule, VMS device, ITS network, PoE/UPS schedule, storm sensor, and night storm operating case.

A source packet has been placed in `/workspace/sources/`. It contains a document register, road segment and lighting grid, device register, network and storage schedule, PoE and UPS schedule, storm operations note, and criteria/comments memo. The packet is a task-owned synthetic source pack; treat it as the only source of numeric truth for this review.

Your job is not to redesign the road systems. Your job is to decide whether the package is ready to issue, and to produce an auditable review record.

## Review Workflow

1. Inventory the source packet before drawing any conclusion. Record every document ID, revision, and status.
2. Build an identity ledger: road segment, lighting grid, luminaire group, CCTV schedule, VMS device, ITS network, cabinet power/PoE, storm sensor, operating case, and datum.
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
| RLR-01 | Packet completeness: are all required visual, device, network, power, storm, and criteria files present with IDs and revisions? |
| RLR-02 | Object identity: do the road segment, lighting grid, luminaires, CCTV, VMS, storm sensor, cabinet, network, PoE switch, and operating case stay consistent? |
| RLR-03 | Visual operations basis: are lighting grid and method traceable, current, and recomputable? |
| RLR-04 | Visual/field-device adequacy: do controlling lighting uniformity and PoE budget clear the source criterion for the same device set? |
| RLR-05 | Scenario consequence: is the same night/storm operating case used across lighting, CCTV/VMS, network, power, and storm operations? |
| RLR-06 | Secondary-discipline resilience: are network headroom, CCTV storage, storm margin, and UPS energy source-backed and internally consistent? |
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
    "road_segment": "...",
    "lighting_grid": "...",
    "luminaire_group": "...",
    "cctv_schedule": "...",
    "vms_device": "...",
    "its_network": "...",
    "cabinet_power_poe": "...",
    "storm_sensor": "...",
    "operating_case": "...",
    "datum": "..."
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
    "average_illuminance_lux": 0.0,
    "minimum_illuminance_lux": 0.0,
    "uniformity_ratio": 0.0,
    "minimum_uniformity_ratio": 0.0,
    "total_network_load_mbps": 0.0,
    "network_headroom_mbps": 0.0,
    "total_cctv_storage_tb": 0.0,
    "poe_load_w": 0.0,
    "poe_headroom_w": 0.0,
    "water_level_margin_m": 0.0,
    "ups_energy_kwh": 0.0
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
