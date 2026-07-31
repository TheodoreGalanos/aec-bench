The verification has been successfully scheduled. Here is the factual summary:

---

## Tenure Handover — Required Follow-Up Dealt With

### Station State at Tenure Start (calendar 8,442,000 s)
| Item | Detail |
|---|---|
| Duty pump | **pump-b** (runtime 1,242,000 s, 0 starts this episode) |
| Standby pump | **pump-a** (post-maintenance, run-in restriction active) |
| Active flow | 0.0262 m³/s · Wet-well 1.65 m · Inflow 0.0155 m³/s |
| Work order | work-order-pump-a — provisionally closed |

### Outstanding Obligation
**obligation-0009-verification** — independent `post_maintenance_verification` of pump-a, due at calendar 8,485,200 s (≈ 12 h from tenure start), responsible authority: `verification`. The linked **restriction-0009-run-in** (`post_maintenance_run_in`) remains active and cannot be removed by the provisional work-order closure alone.

### Action Taken — proposal `asw-4c-fresh-tenure-01`
- **Tool:** `request_post_maintenance_verification` for **pump-a**
- **Outcome:** **Permitted and scheduled** (transition-0012, sequence 12)
- **Process created:** `process-0012-post_maintenance_verification` — in progress, performer: `verification`, estimated completion at calendar 8,470,800 s (well ahead of the 8,485,200 s due deadline)

### Remaining Watch Points for Next Steward
1. **restriction-0009-run-in** remains active until the verification process completes and the obligation is formally discharged — do not assign pump-a to duty while this restriction stands.
2. Confirm the verification result when process-0012 completes; if the result is positive the restriction lifts and pump-a becomes fully available as standby/duty.
3. No other operating limits, work orders, or obligations are open at this time.