**Proposal accepted and scheduled.** Here is the factual summary:

---

## Decision-Window Summary — Incoming Tenure `727f0bbe`

### Station Condition at Handover
| Parameter | Value |
|---|---|
| Duty pump | Pump-B (runtime 7,200,000 s, 1,000 starts) |
| Standby pump | Pump-A (0 runtime, 0 starts — post-maintenance) |
| Wet-well level | 1.65 m, stable |
| Active flow / inflow | 0.0204 m³/s / 0.0155 m³/s — duty pump keeping up |

### Open Restrictions
- **Pump-A** — `restriction-0000-pump-a-run-in` (post_maintenance_run_in, **active**): Pump-A has not yet accumulated any run-in runtime.
- **Pump-B** — `restriction-0000-pump-b-work` (post_maintenance_run_in, **active**, no linked evidence): Pump-B's work order (`work-order-pump-b`) remains open.

### Open Obligation
- `obligation-0000-pump-a-verification` — independent post-maintenance verification for Pump-A, due by calendar_seconds **7,488,000** (288,000 s from handover), responsible authority: **verification**. No evidence was linked at handover — the obligation was unmet.

### Proposal Made
**`prop-incoming-727f-pmv-pump-a-002`** — `request_post_maintenance_verification` for Pump-A.

**Outcome: Permitted / Scheduled** → `process-0001-post_maintenance_verification` created (performer: verification, duration: 28,800 s, currently **blocked** on two unmet dependencies):
1. `dependency-0001-post_maintenance_verification-03` — **work_order_closeout** (administrative): `work-order-pump-a` is `scope_completed` but not yet closed out.
2. `dependency-0001-post_maintenance_verification-04` — **access** (resource): access window is currently 0 s; access preparation process completes at 8,409,600 s.

### Rationale
Maintenance-produced functional checks (`evidence-0000-functional-checks-pump-a`, passed, accepted) are a necessary but not sufficient condition for return-to-service. The independent verification obligation was active, unmet, and time-bounded. With both pumps carrying active post-maintenance restrictions and Pump-B on an open work order, deferring this request would have narrowed the safety margin without justification. Requesting verification now is the conservative action; the two blocked dependencies are administrative and resource constraints that must be resolved through normal work-management channels before the verification process can run.