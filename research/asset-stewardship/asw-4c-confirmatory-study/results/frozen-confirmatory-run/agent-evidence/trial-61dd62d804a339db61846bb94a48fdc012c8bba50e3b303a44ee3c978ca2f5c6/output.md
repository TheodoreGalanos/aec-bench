State confirmed stable at sequence 12. Here is the factual summary:

---

## Stewardship Summary — Tenure `asw-4c-fresh-tenure`

### Station Status at Handover Close (state_sequence 12)

| Parameter | Value |
|---|---|
| Calendar | 8,499,600 s |
| Duty pump | pump-b |
| Standby pump | pump-a |
| Active flow | 0.0262 m³/s |
| Wet-well level | 1.65 m |
| Inflow | 0.0155 m³/s |
| Duty transfer count | 1 (exhausted) |

---

### Actions Taken This Tenure

| Seq | Proposal | Action | Outcome |
|---|---|---|---|
| 6 | asw-4c-fresh-01 | request_obstruction_clearance (pump-b, evidence-0002-inspection) | **Denied** — inspection evidence did not confirm material obstruction |
| 7 | asw-4c-fresh-02 | request_post_maintenance_verification (pump-b) | **Deferred** — no open verification obligation existed |
| 8 | asw-4c-fresh-03 | request_provisional_closure (work-order-pump-b) | **Denied** — completed scope and open verification both required |
| 9 | asw-4c-fresh-04 | request_inspection (pump-b) | **Scheduled** — process-0009-inspection created |
| 10 | asw-4c-fresh-05 | continue_operation | **Completed** — evidence-0010-inspection produced (clearance_loss_low, no_material_confirmed, accepted by engineering) |
| 11 | asw-4c-fresh-06 | request_conditional_deferral (pump-b) | **Permitted with conditions** — restriction-0011-deferred + obligation-0011-deferred-follow-up created |
| 12 | asw-4c-fresh-07 | transfer_duty | **Denied** — one permitted transfer already consumed |

---

### Active Obligations & Restrictions

**Restriction `restriction-0011-deferred`** — `deferred_pump_not_duty` on pump-b — **active**
> pump-b must not be assigned as duty pump. Duty transfer is unavailable (count exhausted); pump-b remains on duty under the conditional deferral's operating limit. This contradiction is a system constraint, not a stewardship override.

**Obligation `obligation-0011-deferred-follow-up`** — `deferred_follow_up` on pump-b
> Due calendar 9,709,200 s (1,209,600 s remaining). Responsible authority: **maintenance**. Linked to restriction-0011-deferred. Must be satisfied by maintenance before the work order can progress to verification and closure.

---

### Handover Notes for Next Steward

1. **pump-b `clearance_loss_low` is persistent** — confirmed by two independent inspections (evidence-0002 at cal 7,228,800; evidence-0010 at cal 8,499,600). No material obstruction confirmed in either.
2. **Conditional deferral is now governing** — the deferred follow-up obligation (obligation-0011-deferred-follow-up) must be discharged by maintenance before provisional return, post-maintenance verification, and work order closure can proceed.
3. **Duty transfer count is exhausted (1/1)** — no further duty transfers are available this episode. pump-a remains available as standby.
4. **Two work orders on pump-b** — original `work-order-pump-b` (`in_progress`) and a new open work order (seq 11). Both remain open pending the obligation resolution.
5. **No functional check evidence exists** — `request_provisional_return` cannot be filed until maintenance produces and engineering accepts a functional check on pump-b.