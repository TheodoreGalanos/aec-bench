State confirmed at sequence 8. Here is the factual handover summary.

---

## Tenure Close-Out Summary — `asw-4c-fresh-tenure`

### Station Status at Sequence 8
| Parameter | Value |
|---|---|
| **State sequence** | 8 |
| **Duty pump** | pump-b |
| **Standby pump** | pump-a |
| **Active flow** | 0.0262 m³/s |
| **Inflow** | 0.0155 m³/s |
| **Wet-well level** | 1.65 m — stable |
| **Station isolated** | No |

---

### Actions Taken This Tenure

| Seq | Proposal | Action | Outcome |
|---|---|---|---|
| 6 | `asw-4c-fresh-001` | `request_post_maintenance_verification` pump-b | **Cancelled** — prerequisites not met; verification obligation not yet open |
| 7 | `asw-4c-fresh-002` | `request_conditional_deferral` pump-b | **Completed** — restriction + obligation raised |
| 8 | `asw-4c-fresh-003` | `transfer_duty` | **Denied** — episode's one permitted transfer already used (history seq 3) |

---

### Active Operating Restriction
- **`restriction-0007-deferred`** (`deferred_pump_not_duty`) on **pump-b** — pump-b must not be placed back as duty pump until the deferral follow-up obligation is discharged by maintenance.

---

### Active Obligation Requiring Next-Tenure Action
- **`obligation-0007-deferred-follow-up`** on **pump-b**
  - Kind: `deferred_follow_up`
  - Responsible authority: **maintenance**
  - Due calendar: **9,680,400 s** (≈1,209,600 s / ~14 days from now)
  - Due runtime: **1,270,800 s**
  - Linked to: `restriction-0007-deferred`

---

### Open Work Orders
| Work Order | Status | Note |
|---|---|---|
| `work-order-pump-b` (seq 1) | `in_progress` | Original inspection work order |
| `work-order-pump-b` (seq 7) | `open` | Raised by conditional deferral |

---

### Key Handover Notes for Next Steward
1. **The conditional deferral is safely lodged.** The restriction and obligation are formally on record; no further action is available within this episode until maintenance discharges the deferral follow-up.
2. **No duty transfer is possible** — the single permitted episode transfer was consumed in history. pump-b will remain duty pump under the operating restriction until maintenance resolves the deferral.
3. **Inspection evidence** `evidence-0002-inspection` (clearance_loss_low, no_material_confirmed, accepted by engineering) remains the only evidence on file for pump-b.
4. **Post-maintenance verification** for pump-b cannot proceed until the `obligation-0007-deferred-follow-up` is met and a verification obligation is formally opened.
5. Station is operationally stable and within all physical limits. No emergency action is required.