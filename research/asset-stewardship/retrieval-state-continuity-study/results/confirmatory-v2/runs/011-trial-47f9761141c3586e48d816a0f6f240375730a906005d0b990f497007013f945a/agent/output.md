**Proposal accepted and scheduled.** Here is the factual summary:

---

## Decision-Window Summary

### Station Condition at Handover
| Item | Value |
|---|---|
| Duty pump | **pump-b** (1,000 starts, 7,200,000 s runtime) |
| Standby pump | **pump-a** (0 starts, 0 runtime — never run since maintenance) |
| Active flow | 0.0204 m³/s vs inflow 0.0155 m³/s — wet-well stable at 1.65 m |
| Duty transfer count | 0 (no transfers this tenure) |
| Station isolated | No |

### Open Obligations & Restrictions on Pump A
- **Obligation** `obligation-0000-pump-a-verification` — kind: `post_maintenance_verification`, status: **active**, due calendar_seconds 7,488,000 (~80,000 s from now), responsible authority: **verification**, evidence_id: *none attached*.
- **Restriction** `restriction-0000-pump-a-run-in` — kind: `post_maintenance_run_in`, status: **active**.
- `work-order-pump-a` — status: `scope_completed` (maintenance work done, but not yet closed out by verification).

### Pump B
- Restriction `restriction-0000-pump-b-work` active; `work-order-pump-b` open. Site resource processes (access preparation, repair kit delivery) active, both completing at calendar_seconds 8,409,600.

### Conservative Proposal Made
**`request_post_maintenance_verification` for pump-a** — `proposal-002-pump-a-pmv` — **scheduled** (permitted by authority policy; requires verification authority).

**Rationale:** The maintenance functional check (`evidence-0000-functional-checks-pump-a`) was produced *by maintenance*, not by the independent verification authority. The open obligation explicitly requires verification authority sign-off. Pump A has zero runtime since maintenance scope completion. No independent verification evidence exists in the register. The maintenance procedure (`pump-a-maintenance-procedure.v1`) confirms the pump must remain under run-in restriction until records are independently accepted. Provisionally returning pump-a to standby without that verification would be non-conservative and outside the obligation framework.

**Outcome of process creation:** `process-0001-post_maintenance_verification` is now **scheduled/blocked** pending two unsatisfied dependencies — `work_order_closeout` (admin closeout of `work-order-pump-a`) and `access` (access window currently 0). These are the correct gatekeeping conditions; the process will advance when those dependencies are satisfied. The run-in restriction and obligation remain active as required.