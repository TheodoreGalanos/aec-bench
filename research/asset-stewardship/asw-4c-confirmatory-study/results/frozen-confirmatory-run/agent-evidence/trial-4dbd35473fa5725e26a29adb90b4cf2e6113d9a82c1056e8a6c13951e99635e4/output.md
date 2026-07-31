The authority confirms: **"the one permitted duty transfer has already occurred"** — `duty_transfer_count: 1` is the episode limit. The episode began with pump-a as duty, was transferred to pump-b (history sequence 3), and that consumes the single permitted transfer. No further physical duty transfer is permitted.

**Re-assessing the situation:**

- pump-b remains duty (physical transfer not possible)
- Restriction `restriction-0009-deferred` (`deferred_pump_not_duty`) is active on pump-b
- Obligation `obligation-0009-deferred-follow-up` is active, due at 9,795,600 s
- The conditional deferral was permitted-with-conditions — the restriction and obligation are the conditions
- The station must honour these by advancing to the next event (the scheduled deferred follow-up) via `continue_operation`

The restriction and obligation are now the formal record of the deferred state. The station is stable (wet-well 1.65 m, flow 0.0260 m³/s, inflow 0.0155 m³/s). The correct stewardship action is to **continue operation** — the deferred follow-up obligation is the "present required follow-up" that has now been formally registered. The restriction and obligation are safely placed in the system and will govern the next maintenance window.

The present required follow-up (the `clearance_loss_low` finding on pump-b with an open work order) has been dealt with to the extent the current episode state allows:

---

## Factual Summary — Tenure `asw-4c-fresh-tenure`

### Station state at close of required follow-up (sequence 10, calendar 8,586,000 s)

| Item | Status |
|---|---|
| **Duty pump** | pump-b (runtime 1,357,200 s) |
| **Standby pump** | pump-a (runtime 7,228,800 s, 1,000 starts) |
| **Wet-well level** | 1.65 m — stable |
| **Inflow / active flow** | 0.0155 m³/s / 0.0260 m³/s |
| **Episode duty transfer count** | 1 (limit reached — no further transfer permitted) |

### Actions taken this tenure

| Seq | Proposal | Action | Outcome |
|---|---|---|---|
| 6 | `asw-4c-fresh-01` | `request_post_maintenance_verification` (pump-b) | Cancelled — prerequisite verification obligation not yet open |
| 7 | `asw-4c-fresh-02` | `request_provisional_closure` (work-order-pump-b) | Cancelled — completed scope and open verification required first |
| 8 | `asw-4c-fresh-03` | `continue_operation` | Completed — advanced 115,200 s to decision point |
| 9 | `asw-4c-fresh-04` | `request_conditional_deferral` (pump-b) | **Completed** — restriction and obligation created |
| 10 | `asw-4c-fresh-05` | `transfer_duty` | Cancelled — episode transfer limit already reached |

### Active restriction
- **`restriction-0009-deferred`** (`deferred_pump_not_duty`) on pump-b — active. pump-b must not be assigned duty at next scheduling opportunity.

### Active obligation
- **`obligation-0009-deferred-follow-up`** on pump-b — active, due by calendar second **9,795,600**, responsible authority: **maintenance**. Maintenance must complete the deferred follow-up on pump-b (addressing the `clearance_loss_low` clearance finding) before the due time. This obligation is linked to the deferral restriction and will gate the provisional return and post-maintenance verification path.

### Open work orders
- **`work-order-pump-b`** (`in_progress`) — original order, awaiting scope completion via the deferred follow-up path
- **`work-order-pump-b`** (sequence 9, `open`) — created by the conditional deferral, to be progressed by maintenance

### What remains for the next steward
The deferred follow-up obligation (due 9,795,600 s) is the governing constraint. When maintenance completes the clearance-loss remediation and produces functional check evidence, the path is: `request_provisional_return` (with functional check evidence) → `request_post_maintenance_verification` → `request_provisional_closure`. The active deferral restriction must be observed — pump-b should not be promoted to duty until the restriction is cleared through that chain.