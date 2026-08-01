Review submitted and accepted. Here is the factual summary.

---

## Closeout Review Summary — Pump A Maintenance Pack

**Disposition: REJECTED**
**Finding: Wrong-component evidence citation**

### Primary Defect
`closeout-record-pump-a` — the controlling closeout record — lists `evidence-0019-functional-checks` in its `evidence_ids`. That evidence record is bound to **pump-b** (Pump B post-obstruction functional checks) and has no relationship to Pump A's maintenance scope. The correct Pump A functional-check evidence, `evidence-0000-functional-checks-pump-a`, is properly cited in `condition-history-pump-a` and `provisional-return-record-pump-a` but is **absent from the closeout record itself**. As issued, the closeout is supported by Pump B evidence, not Pump A evidence, and cannot stand.

### Secondary Inconsistencies (Required Follow-Up)
| Record | Issue |
|--------|-------|
| `work-order-pump-a` | Status is **`in_progress`**; all other records declare scope completed. The work order has not been formally closed. |
| `restriction-0000-pump-a-run-in` | Statement says the run-in restriction *"remains active after verification"*; status says **`lifted`**. The two fields directly contradict each other. |

### Unaffected
`obligation-0000-pump-a-verification` (Pump A verification duty) is fulfilled — it cites the correct evidence (`evidence-0014-verification`) and is unaffected by the above defects.

### Required Actions Before Re-submission
1. **Correct** `closeout-record-pump-a`: replace `evidence-0019-functional-checks` with `evidence-0000-functional-checks-pump-a` and reissue.
2. **Close** `work-order-pump-a`: transition status from `in_progress` to closed/completed.
3. **Reconcile** `restriction-0000-pump-a-run-in`: align the statement and status, and confirm in writing whether the run-in restriction is active or lifted before unrestricted return-to-service is progressed.