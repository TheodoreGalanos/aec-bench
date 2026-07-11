You are the independent reviewing engineer for a drainage model-run provenance package. The packet links governing catchment, rainfall, network, and configuration sources to a model manifest, run register, hydraulic report, and downstream design memo.

A task-owned synthetic source packet has been placed in `/workspace/sources/`. Treat it as the only source of truth. Your job is not to rebuild the drainage model. Your job is to decide which evidence can govern the design issue and to leave an auditable transition record.

## Review Workflow

1. Inventory every registered source with document ID, revision, and status.
2. Build a provenance ledger preserving the site, catchment, governing inputs, model manifest, reviewed run, report, design memo, and criteria source.
3. Establish source authority before relying on dates or filenames. Trace the exact input revisions and scenario into the reviewed run.
4. Recompute only the comparisons needed by the review matrix, using the source-owned assessment basis.
5. Assign exactly one status to every review item: `pass`, `fail`, `not_applicable`, or `insufficient_data`.
6. Do not invent missing values. Mark missing evidence as `insufficient_data` and request the exact missing field and source. A value explicitly marked pending or awaiting confirmation is missing evidence; it does not create unrelated identity failures.
7. Convert every failure into one finding with a source pointer, affected object, consequence, and corrective action.
8. Record the resulting state of the reviewed model run, its report, and the downstream design claim.
9. Issue a readiness decision that reconciles with the matrix, transition decision, findings, information requests, and carried actions.

## Review Matrix

| Item | Review question |
|---|---|
| PRV-01 | Packet completeness: are all required input-basis, manifest, run-register, report, design-memo, and criteria records present with IDs and revisions? |
| PRV-02 | Source authority and identity: do site, catchment, governing source, run, report, memo, and criteria identities remain traceable without mixing objects? |
| PRV-03 | Input-revision provenance: does the reviewed run manifest identify the governing input revisions declared by the packet? |
| PRV-04 | Run/report integrity: does the report belong to the registered run and satisfy the packet's intrinsic report acceptance checks? The upstream input-governance state is recorded in the transition decision. |
| PRV-05 | Scenario propagation: is the governing design scenario preserved into the reviewed run? |
| PRV-06 | Downstream claim propagation: does the design memo preserve citation and value-propagation integrity for the reviewed run and report? Whether the cited evidence governs is recorded in the transition decision. |
| PRV-07 | Comment and action closure: is every critical comment closed, and is every carried action controlled by owner and action? |
| PRV-08 | Transition and readiness consistency: do the final states reconcile with the matrix and registers? |
| PRV-09 | Claim boundary: does the review avoid unsupported approval, compliance, source-hardening, executable-verifier, or benchmark-readiness claims? |

## Boundary Rules

- Use the matrix definitions and source packet to locate the most specific affected item. Do not infer a status from this instruction alone.
- If evidence needed for a comparison is absent, omit its `computed_evidence` key and raise an information request. Do not use `null`, zero, or placeholders for missing evidence.
- Do not double-count one source defect across unrelated matrix items. Consequences may propagate through the transition decision without becoming additional findings.
- Every finding, information request, and action must name one exact PRV item.
- Do not rename `computed_evidence` keys.

## Output

Write the complete review to `/workspace/output.md`. Explain the provenance decision briefly, then end with exactly one fenced JSON block:

```json
{
  "source_inventory": [{"doc_id": "...", "revision": "...", "status": "..."}],
  "provenance_ledger": {
    "site": "...",
    "catchment": "...",
    "catchment_basis": "...",
    "rainfall_basis": "...",
    "design_storm": "...",
    "network_model": "...",
    "model_config": "...",
    "run_manifest": "...",
    "reviewed_run": "...",
    "reviewed_report": "...",
    "design_memo": "...",
    "criteria_memo": "..."
  },
  "review_matrix": {
    "PRV-01": {"status": "pass|fail|not_applicable|insufficient_data", "evidence": "..."},
    "PRV-02": {"status": "...", "evidence": "..."},
    "PRV-03": {"status": "...", "evidence": "..."},
    "PRV-04": {"status": "...", "evidence": "..."},
    "PRV-05": {"status": "...", "evidence": "..."},
    "PRV-06": {"status": "...", "evidence": "..."},
    "PRV-07": {"status": "...", "evidence": "..."},
    "PRV-08": {"status": "...", "evidence": "..."},
    "PRV-09": {"status": "...", "evidence": "..."}
  },
  "computed_evidence": {
    "all_input_revisions_match_score": 0,
    "scenario_match_score": 0,
    "report_run_match_score": 0,
    "continuity_error_percent": 0,
    "continuity_margin_percent": 0,
    "report_peak_flow_m3_s": 0,
    "memo_peak_flow_m3_s": 0,
    "peak_flow_propagation_delta_m3_s": 0,
    "report_max_hgl_m_ahd": 0,
    "memo_max_hgl_m_ahd": 0,
    "hgl_propagation_delta_m": 0
  },
  "transition_decision": {
    "model_run": "governing|non_governing|insufficient_data",
    "model_report": "governing|non_governing|insufficient_data",
    "design_claim": "supported|unsupported|insufficient_data"
  },
  "findings": [
    {"item": "PRV-0X", "severity": "critical|minor", "source_id": "...", "object_id": "...", "consequence": "...", "action": "..."}
  ],
  "information_requests": [
    {"item": "PRV-0X", "missing_field": "...", "source_id": "..."}
  ],
  "action_register": [
    {"action": "...", "owner": "...", "linked_item": "PRV-0X"}
  ],
  "readiness_decision": "ready_to_issue|ready_with_carried_actions|not_ready_to_issue",
  "claim_boundary_statement": "..."
}
```

Omit a `computed_evidence` key only when its required source field is missing, and raise the matching information request. Every `fail` needs a complete finding. Every `insufficient_data` needs an exact request. Every carried action needs an owner. The claim-boundary statement must say this is a task-owned synthetic source packet and does not claim authority approval, accepted project evidence, full standards compliance, source-pack hardening, executable-verifier readiness, or benchmark readiness.
