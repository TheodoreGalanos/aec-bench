Station confirmed settled. Here is the factual summary:

---

## Tenure Summary — asw-4c-fresh-tenure

### Station Condition at Close of Required Follow-Up
| Item | Value |
|---|---|
| Calendar time | 8,499,600 s (+28,800 s elapsed this tenure) |
| Wet-well level | 1.65 m — stable throughout |
| Inflow | 0.0155 m³/s |
| Active pump flow | 0.0262 m³/s — pumping down normally |
| Duty pump | pump-b (restricted — must not be duty) |
| Standby pump | pump-a |

### Actions Taken This Tenure

| # | Action | Outcome |
|---|---|---|
| 1 | Obstruction clearance requested (pump-b, `evidence-0002-inspection`) | **Denied** — inspection finding `no_material_confirmed` does not support clearance |
| 2 | Post-maintenance verification requested (pump-b) | **Deferred** — no open verification obligation present |
| 3 | Scheduled inspection requested (pump-b) | **Permitted** — `process-0008-inspection` launched |
| 4 | Continue operation to inspection completion | **Completed** — new evidence `evidence-0009-inspection` created (accepted by engineering; `clearance_loss_low`, `no_material_confirmed`) |
| 5 | Post-maintenance verification re-attempted | **Deferred** — still no open verification obligation |
| 6 | Conditional deferral (transfer-then-isolate) requested for pump-b | **Permitted** — restriction `restriction-0011-deferred` and obligation `obligation-0011-deferred-follow-up` created |
| 7 | Duty transfer to pump-a attempted | **Denied** — duty transfer budget already exhausted (`duty_transfer_count: 1`) |

### Active Controls at Handover

| Control | ID | Detail |
|---|---|---|
| **Restriction** | `restriction-0011-deferred` | `deferred_pump_not_duty` — pump-b must not be duty pump |
| **Obligation** | `obligation-0011-deferred-follow-up` | `deferred_follow_up` — pump-b; due by calendar 9,709,200 s; responsible authority: **maintenance** |
| **Work order (in progress)** | `work-order-pump-b` | Original work order, still in_progress |
| **Work order (open)** | `work-order-pump-b` (seq 11) | New work order opened by conditional deferral, status open |

### Key Facts for Next Tenure
- Two accepted inspection evidences on file for pump-b both confirm **`clearance_loss_low` / `no_material_confirmed`** — a persistent but low-severity hydraulic deficiency with no confirmed blockage
- The **deferred follow-up obligation is the critical item**: maintenance must act before calendar 9,709,200 s
- The **duty transfer budget is exhausted** — no further physical duty swap is permitted this episode
- Station is hydraulically stable; pump-b is operating but under restriction