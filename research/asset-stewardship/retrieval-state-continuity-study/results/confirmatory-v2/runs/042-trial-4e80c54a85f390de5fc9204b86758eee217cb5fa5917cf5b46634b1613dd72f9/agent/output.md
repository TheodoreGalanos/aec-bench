**Proposal accepted and scheduled.** Here is the factual summary:

---

## Station Management Summary — Tenure `incoming-tenure-9b16009ad85d21e4`

### Live Station State at Decision Window
| Item | Value |
|---|---|
| **Duty pump** | pump-b (active, flow 0.0204 m³/s) |
| **Standby pump** | pump-a (0 post-maintenance starts, 0 runtime seconds) |
| **Wet-well level** | 1.65 m (stable) |
| **Inflow** | 0.0155 m³/s |
| **Duty transfers used** | 0 of 1 permitted |

### Restrictions in Force
- **`restriction-0000-pump-a-run-in`** (active) — post-maintenance run-in on pump-a, linked to obligation below.
- **`restriction-0000-pump-b-work`** (active) — post-maintenance run-in on pump-b; work order `work-order-pump-b` is open.

### Active Obligation
- **`obligation-0000-pump-a-verification`** — independent post-maintenance verification for pump-a, due by calendar_seconds **7,488,000** (288,000 s from now). `responsible_authority: verification`. No satisfying evidence present (`evidence_id: null`).

### Consequential Proposal Made
**`proposal-002-pump-a-pmv` — `request_post_maintenance_verification` for pump-a — SCHEDULED** ✅

**Rationale:** The accepted functional-check (`evidence-0000-functional-checks-pump-a`) was produced *by maintenance*, not by independent verification. It does not satisfy the open obligation. Pump-a has zero post-maintenance runtime and cannot be returned to duty or standby service under the active run-in restriction until that obligation is resolved. Rather than prematurely calling for a provisional return or duty transfer without the required authority sign-off, the conservative and procedurally correct action is to formally initiate the independent post-maintenance verification process now — well ahead of the due window.

### New Process Created
- **`process-0001-post_maintenance_verification`** (status: **blocked**, performer: `verification`, estimated completion: calendar_seconds 7,228,800)
- Two blocking dependencies remain unsatisfied: `work_order_closeout` (admin closeout of `work-order-pump-a`) and `access` (no current access window). These must be resolved by work management before the verification process can proceed. The intervention slot and safety conditions are already satisfied.

### No duty transfer was proposed — correct, because:
1. Both pumps carry active post-maintenance restrictions.
2. Pump-a cannot be confirmed fit for duty without the independent verification.
3. Pump-b is currently performing within normal parameters; transferring to an unverified pump-a would be unsafe and unprocedural.