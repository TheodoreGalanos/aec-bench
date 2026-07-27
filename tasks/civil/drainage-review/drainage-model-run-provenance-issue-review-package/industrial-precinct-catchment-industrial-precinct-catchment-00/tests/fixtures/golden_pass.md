## Provenance Review

The source packet has been inventoried and traced from governing inputs through the downstream design claim.

```json
{
  "source_inventory": [
    {
      "doc_id": "CATCH-03-BASIS-01",
      "revision": "Rev D",
      "status": "current"
    },
    {
      "doc_id": "RAIN-03-BASIS-01",
      "revision": "Rev C",
      "status": "current"
    },
    {
      "doc_id": "NET-03-MODEL-01",
      "revision": "Rev F",
      "status": "current"
    },
    {
      "doc_id": "CFG-03-MODEL-01",
      "revision": "Rev B",
      "status": "current"
    },
    {
      "doc_id": "MANIFEST-03-042",
      "revision": "Rev A",
      "status": "current"
    },
    {
      "doc_id": "RUN-03-REGISTER-01",
      "revision": "Rev E",
      "status": "current"
    },
    {
      "doc_id": "REPORT-03-042",
      "revision": "Rev A",
      "status": "current"
    },
    {
      "doc_id": "MEMO-03-DESIGN-01",
      "revision": "Rev D",
      "status": "current"
    },
    {
      "doc_id": "CRIT-SSC03-001",
      "revision": "Rev C",
      "status": "current"
    }
  ],
  "provenance_ledger": {
    "site": "SITE-03",
    "catchment": "CATCH-03-A",
    "catchment_basis": "CATCH-03-BASIS-01 Rev D",
    "rainfall_basis": "RAIN-03-BASIS-01 Rev C",
    "design_storm": "STORM-03-A",
    "network_model": "NET-03-MODEL-01 Rev F",
    "model_config": "CFG-03-MODEL-01 Rev B",
    "run_manifest": "MANIFEST-03-042",
    "reviewed_run": "RUN-03-042",
    "reviewed_report": "REPORT-03-042",
    "design_memo": "MEMO-03-DESIGN-01",
    "criteria_memo": "CRIT-SSC03-001"
  },
  "review_matrix": {
    "PRV-01": {
      "status": "pass",
      "evidence": "Required source files are inventoried with IDs, revisions, and status."
    },
    "PRV-02": {
      "status": "pass",
      "evidence": "Site, catchment, source authority, run, report, and memo identities are reconciled."
    },
    "PRV-03": {
      "status": "pass",
      "evidence": "The model manifest is checked against every governing input revision."
    },
    "PRV-04": {
      "status": "pass",
      "evidence": "Run-to-report identity and intrinsic report acceptance are checked."
    },
    "PRV-05": {
      "status": "pass",
      "evidence": "The governing design storm is preserved into the run manifest."
    },
    "PRV-06": {
      "status": "fail",
      "evidence": "Memo citation and value propagation are checked independently of governing state."
    },
    "PRV-07": {
      "status": "pass",
      "evidence": "Critical comments are closed and carried actions are controlled."
    },
    "PRV-08": {
      "status": "pass",
      "evidence": "The transition and readiness decisions reconcile with the review record."
    },
    "PRV-09": {
      "status": "pass",
      "evidence": "The review remains inside the task-owned synthetic claim boundary."
    }
  },
  "computed_evidence": {
    "all_input_revisions_match_score": 1.0,
    "scenario_match_score": 1.0,
    "report_run_match_score": 1.0,
    "continuity_error_percent": 1.73,
    "continuity_margin_percent": 0.7,
    "report_peak_flow_m3_s": 3.16,
    "memo_peak_flow_m3_s": 2.67,
    "peak_flow_propagation_delta_m3_s": 0.49,
    "report_max_hgl_m_ahd": 21.09,
    "memo_max_hgl_m_ahd": 20.95,
    "hgl_propagation_delta_m": 0.14
  },
  "transition_decision": {
    "model_run": "governing",
    "model_report": "governing",
    "design_claim": "unsupported"
  },
  "findings": [
    {
      "item": "PRV-06",
      "severity": "critical",
      "source_id": "MEMO-03-DESIGN-01",
      "object_id": "MEMO-03-DESIGN-01",
      "consequence": "The model evidence chain cannot support design issue in its current state.",
      "action": "Correct the affected source, rerun or reissue as needed, and repeat the provenance review."
    }
  ],
  "information_requests": [],
  "action_register": [],
  "readiness_decision": "not_ready_to_issue",
  "claim_boundary_statement": "This review covers a task-owned synthetic source packet. It does not claim authority approval, accepted project evidence, full standards compliance, source-pack hardening, executable-verifier readiness, or benchmark readiness."
}
```
