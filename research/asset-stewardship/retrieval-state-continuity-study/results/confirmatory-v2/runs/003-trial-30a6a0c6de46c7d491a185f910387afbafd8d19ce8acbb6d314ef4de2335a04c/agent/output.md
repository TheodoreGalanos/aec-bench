**Proposal accepted and scheduled.** Here is the factual summary:

---

## Station Summary — Tenure `incoming-624a8ac87e1a9361`

### Station Condition at Decision Window
| Item | Value |
|---|---|
| Duty pump | **Pump B** (1,000 starts, 7,200,000 s runtime) |
| Standby pump | **Pump A** (0 starts, 0 runtime this assignment) |
| Active flow | 0.0204 m³/s vs inflow 0.0155 m³/s — wet well stable at 1.65 m |
| Station isolated | No |

### Active Restrictions
- **`restriction-0000-pump-a-run-in`** (`post_maintenance_run_in`, Pump A) — active; linked to passed functional-check evidence (`evidence-0000-functional-checks-pump-a`, produced by maintenance).
- **`restriction-0000-pump-b-work`** (`post_maintenance_run_in`, Pump B) — active; no evidence_id attached yet.

### Outstanding Obligation
- **`obligation-0000-pump-a-verification`** — independent post-maintenance verification by the **verification authority**, due by calendar second **7,488,000** (~80 hours remaining). Not yet satisfied (no independent verification evidence present).

### Key Risk
The functional-check evidence was produced **by maintenance**, not by the independent verification authority. A passed maintenance functional check does **not** satisfy the independent verification obligation, and the `post_maintenance_run_in` restriction on Pump A cannot be lifted until that obligation is resolved.

### Proposal Made — `proposal-002-pump-a-pmv` ✅ SCHEDULED
**Action:** `request_post_maintenance_verification` for **Pump A**

**Outcome:** Process `process-0001-post_maintenance_verification` created and scheduled. It is currently **blocked** on two unmet dependencies:
1. `dependency-0001-post_maintenance_verification-03` — **work_order_closeout** for `work-order-pump-a` (administrative; scope_completed but not formally closed)
2. `dependency-0001-post_maintenance_verification-04` — **access** (access window is currently 0; access preparation process is active, completing at second 8,409,600)

**Why conservative:** Rather than attempting a provisional return or waiver, this proposal requests the mandatory independent verification gate directly. It preserves the restriction until verification authority accepts the result, protects standby readiness integrity, and ensures the obligation is met well within the due window once blockers clear.

### Next Steward Actions Required
1. **Resolve work-order closeout** for `work-order-pump-a` — administrative closeout dependency must be cleared before verification can proceed.
2. **Monitor access preparation** (`process-0000-access-preparation`) — completing ~second 8,409,600; access must be granted before the verification process can execute.
3. **Monitor Pump B restriction** (`restriction-0000-pump-b-work`) — open work order and no backing evidence; requires attention before Pump B becomes a reliable long-term duty pump.
4. **Repair kit delivery** is also pending (same completion window); coordinate with site work order.