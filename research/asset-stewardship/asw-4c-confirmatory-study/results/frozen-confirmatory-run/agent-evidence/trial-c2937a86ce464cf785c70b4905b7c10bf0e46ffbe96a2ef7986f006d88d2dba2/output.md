State confirmed at sequence 13. Here is the factual handover summary:

---

## Stewardship Summary — Tenure `asw-4c-fresh-tenure`

### Station Status at Close (state_sequence 13, calendar 8,557,200 s)

| Parameter | Value |
|---|---|
| Duty pump | **pump-b** (runtime 1,328,400 s, 0 starts this tenure) |
| Standby pump | **pump-a** (runtime 7,228,800 s, 1,000 starts — high-hours) |
| Active flow | 0.0260 m³/s |
| Wet-well level | 1.65 m — stable |
| Inflow | 0.0155 m³/s |
| Duty transfer count | 1 (limit reached — no further transfers available) |

### Operating Restrictions

| ID | Kind | Pump | Status |
|---|---|---|---|
| `restriction-0012-deferred` | `deferred_pump_not_duty` | pump-b | **Active** |

### Active Obligations

| ID | Kind | Pump | Responsible | Due (calendar s) | Status |
|---|---|---|---|---|---|
| `obligation-0012-deferred-follow-up` | `deferred_follow_up` | pump-b | **maintenance** | 9,766,800 (~14 days) | **Active** |

### Open Work Orders

| ID | Pump | Status |
|---|---|---|
| `work-order-pump-b` (sequence 1) | pump-b | `in_progress` |
| `work-order-pump-b` (sequence 12) | pump-b | `open` |

### Evidence on File

| ID | Kind | Pump | Finding | Accepted by |
|---|---|---|---|---|
| `evidence-0002-inspection` | inspection | pump-b | `clearance_loss_low`, `no_material_confirmed`, `passed: null` | engineering |

---

### Actions Taken This Tenure

1. **Observed & snapshotted** station — confirmed handover state exact match.
2. **Provisional closure** of `work-order-pump-b` attempted → **denied** (completed scope + open verification required).
3. **Post-maintenance verification** for pump-b attempted (×2, across decision points) → **deferred** (no open verification obligation existed).
4. **Continued operation** (×3) to advance through scheduled and quiescent events — no verification obligation was raised organically.
5. **Conditional deferral** (`request_conditional_deferral`) for pump-b → **permitted with conditions** by engineering + operations. This correctly registered `restriction-0012-deferred` and `obligation-0012-deferred-follow-up`.
6. **Duty transfer** to pump-a attempted to comply with the `deferred_pump_not_duty` restriction → **denied** (single permitted transfer already consumed in prior history).

### What the Next Steward Must Do

- **The active restriction (`deferred_pump_not_duty`) and deferred follow-up obligation are the live items.** The one permitted duty transfer is exhausted; pump-b remains on duty under the restriction.
- **Maintenance** is responsible for fulfilling `obligation-0012-deferred-follow-up` before due date **9,766,800 s** (approximately 14 days from current calendar time).
- Once maintenance discharges the obligation, `restriction-0012-deferred` can be lifted and both work orders progressed toward closure and independent verification.
- **Do not attempt further duty transfers** — the limit is reached and all such requests will be denied.