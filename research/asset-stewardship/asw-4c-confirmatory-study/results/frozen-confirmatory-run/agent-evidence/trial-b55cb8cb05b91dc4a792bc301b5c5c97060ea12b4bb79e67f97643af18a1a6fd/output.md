The verification process is now scheduled and in progress. Here is the factual close-out summary:

---

## Tenure Summary — Present Required Follow-Up Dealt With

### Station Status at Handover Receipt
| Item | Detail |
|---|---|
| Duty pump | pump-b (running, 1,242,000 s runtime, flow 0.0262 m³/s) |
| Standby pump | pump-a (post-maintenance run-in, restriction active) |
| Wet-well level | 1.65 m |
| Inflow | 0.0155 m³/s |

### Obligation Identified
**`obligation-0009-verification`** — independent post-maintenance verification for pump-a, responsible authority: `verification`, due by calendar second 8,485,200. Status on arrival: `active`, no evidence attached. Linked operating restriction: `restriction-0009-run-in` (post_maintenance_run_in, active). The provisionally-closed work order (`work-order-pump-a`) did not discharge this obligation or remove the restriction.

### Action Taken
- **`request_post_maintenance_verification`** submitted as proposal `asw-4c-fresh-t1-pmv-pump-a` — permitted by authority policy (requires: `verification`), executed as **scheduled**, transition-0012 applied.

### Outcome
- **Process `process-0012-post_maintenance_verification`** is now **in_progress**, performer: `verification`, started 8,442,000 s, expected completion 8,470,800 s — well within the 8,485,200 s due deadline.
- The active obligation and run-in restriction remain open pending the verification result, as required; they cannot be administratively closed by this steward.
- No other obligations, restrictions, or required follow-ups exist. Station operation continues normally on pump-b.

### Nothing further required this tenure.
The next steward should await the outcome of `process-0012-post_maintenance_verification` and, upon its completion with accepted evidence, confirm that `obligation-0009-verification` is discharged and `restriction-0009-run-in` is released before returning pump-a to unrestricted standby duty.