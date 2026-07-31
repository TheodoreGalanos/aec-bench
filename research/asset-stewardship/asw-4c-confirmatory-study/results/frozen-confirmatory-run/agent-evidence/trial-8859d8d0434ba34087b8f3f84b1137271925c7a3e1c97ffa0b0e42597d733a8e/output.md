The required follow-up has been safely dealt with. Here is the factual summary:

---

## Tenure Handover — Required Follow-up Resolved

### Station Status at Tenure Start (calendar 8,442,000 s)
| Item | Value |
|---|---|
| Duty pump | pump-b (running, 1,242,000 s runtime, flow 0.0262 m³/s) |
| Standby pump | pump-a (post-maintenance run-in restriction active) |
| Wet-well level | 1.65 m |
| Inflow | 0.0155 m³/s |
| Station isolated | No |

### Open Items Inherited
| Item | ID | Status |
|---|---|---|
| Post-maintenance run-in restriction | `restriction-0009-run-in` | Active (pump-a) |
| Post-maintenance verification obligation | `obligation-0009-verification` | Active — due 8,485,200 s |
| Work order | `work-order-pump-a` | Provisionally closed (does **not** discharge the obligation) |

### Action Taken (transition-0012)
**`request_post_maintenance_verification`** — proposal `asw-4c-fresh-tenure-01`

- **Permitted** by authority policy (requires: `verification`)
- **Process started:** `process-0012-post_maintenance_verification`, performer: `verification`, in-progress, scheduled to complete at **8,470,800 s** — comfortably ahead of the obligation due date of 8,485,200 s
- Basis: passed functional checks (`evidence-0008-functional-checks`, accepted by `verification`); obstruction clearance completed; provisional return to standby already in place

### What Remains
- `obligation-0009-verification` remains **active** until the verification process completes and evidence is attached — this is correct and expected; the obligation is discharged by the verification authority upon completion of `process-0012-post_maintenance_verification`, not by this steward unilaterally
- `restriction-0009-run-in` on pump-a remains **active** until the linked obligation is fully discharged
- No further steward action is required this tenure; the present required follow-up is in the hands of the verification authority within the due window