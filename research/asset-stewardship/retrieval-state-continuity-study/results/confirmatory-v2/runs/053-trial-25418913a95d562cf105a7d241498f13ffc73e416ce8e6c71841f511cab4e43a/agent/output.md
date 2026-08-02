**Proposal accepted and scheduled.** State advanced to sequence 1. Here is the factual summary.

---

## Post-Decision Summary

### Proposal Executed
**`proposal-tenure-0d050980-pmv-pump-a-002`** — *Request post-maintenance verification for pump-a*
**Status:** `scheduled` | **Transition:** `transition-0001` | **State sequence:** 0 → 1

---

### Station State at Handover (sequence 0 → 1)

| Item | Value |
|---|---|
| Duty pump | pump-b (on duty, 1,000 starts, 7,200,000 s runtime) |
| Standby pump | pump-a (post-maintenance, 0 starts, 0 s runtime) |
| Wet-well level | 1.65 m — stable |
| Inflow / duty flow | 0.0155 / 0.0204 m³/s — adequate margin |
| Active restrictions | pump-a: `restriction-0000-pump-a-run-in` (active) · pump-b: `restriction-0000-pump-b-work` (active) |
| Open obligation | `obligation-0000-pump-a-verification` — due at 7,488,000 s — **active, unsatisfied** |

---

### Why this proposal was the correct conservative action

1. **Functional checks passed** (`evidence-0000-functional-checks-pump-a`) but were produced by **maintenance**, not the independent verification authority. Passed maintenance checks are a necessary but insufficient condition for return-to-service.
2. The **post_maintenance_verification obligation** (`obligation-0000-pump-a-verification`) is active and mandates independent verification before `restriction-0000-pump-a-run-in` can be lifted. No independent verification evidence existed in the record.
3. **Documentary search returned no accessible result** — no additional evidence (condition check, inspection, or verification record) was retrievable at this world time. Proceeding to a provisional return without that evidence would have been unsafe and non-compliant.
4. Station conditions (stable wet-well, adequate duty flow margin) confirm there is **no operational urgency** to bypass verification.

---

### New Process Created

| Process | `process-0001-post_maintenance_verification` |
|---|---|
| Kind | post_maintenance_verification |
| Performer | verification (independent authority) |
| Status | **blocked** |
| Expected completion | 7,228,800 s (28,800 s duration) |
| Blocking dependencies | `dependency-0001-post_maintenance_verification-03` — work_order_closeout (unsatisfied) · `dependency-0001-post_maintenance_verification-04` — access (unsatisfied) |

The verification process is now formally in the queue but is **blocked** on two dependencies: administrative closeout of `work-order-pump-a` and site access (which is currently being prepared via `process-0000-access-preparation`, completing at 8,409,600 s). These blockers must be resolved before the verification authority can execute the process and satisfy the obligation within its due window (7,488,000 s). The access-preparation completion time (8,409,600 s) **exceeds** the obligation due time — this is a flag for the next steward to escalate access prioritisation.