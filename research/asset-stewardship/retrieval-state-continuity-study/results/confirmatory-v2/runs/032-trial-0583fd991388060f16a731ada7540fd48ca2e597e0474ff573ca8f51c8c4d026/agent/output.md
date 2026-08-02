**Proposal accepted and scheduled.** Here is the factual summary:

---

## Decision Window Summary — Incoming Tenure `2b021d30a762e9c0`

### Station State at Handover
| Item | Value |
|---|---|
| Duty pump | **Pump B** (1,000 starts, 7,200,000 s runtime) |
| Standby pump | **Pump A** (0 starts, 0 s runtime post-maintenance) |
| Wet-well level | 1.65 m — stable |
| Active inflow | 0.0155 m³/s; duty flow 0.0204 m³/s — adequate margin |
| Station isolated | No |

### Active Restrictions
- **restriction-0000-pump-a-run-in** (`post_maintenance_run_in`) — Pump A, active, linked to `evidence-0000-functional-checks-pump-a`
- **restriction-0000-pump-b-work** (`post_maintenance_run_in`) — Pump B, active (no source evidence on file)

### Active Obligation
- **obligation-0000-pump-a-verification** — independent `post_maintenance_verification` for Pump A, due at calendar_seconds 7,488,000 (288,000 s / ~3.3 days remaining), responsible authority: **verification**

### Evidence Position
The only accepted evidence for Pump A is `evidence-0000-functional-checks-pump-a`, produced by **maintenance** — not by the independent verification authority. No independent verification evidence has been accepted. Return to unrestricted service cannot proceed until the obligation is discharged.

### Conservative Proposal Made
**`request_post_maintenance_verification` for Pump A — Proposal `proposal-tenure-2b021d30a762e9c0-pmv-pump-a-v3`**

✅ **Status: Scheduled** (`process-0001-post_maintenance_verification`, performer: verification, duration 28,800 s)

**Currently blocked on two unsatisfied dependencies:**
1. `dependency-0001-post_maintenance_verification-03` — `work_order_closeout` (administrative): `work-order-pump-a` is `scope_completed` but not yet closed out
2. `dependency-0001-post_maintenance_verification-04` — `access`: no access window is currently open (access preparation process completes at 8,409,600 s)

Physical safety and intervention-slot dependencies are satisfied. The next steward action is to pursue work-order closeout for `work-order-pump-a` and monitor the access-preparation process (`process-0000-access-preparation`) to unblock verification. No provisional return or duty transfer was proposed — doing so without independent verification evidence would be premature against an active run-in restriction.