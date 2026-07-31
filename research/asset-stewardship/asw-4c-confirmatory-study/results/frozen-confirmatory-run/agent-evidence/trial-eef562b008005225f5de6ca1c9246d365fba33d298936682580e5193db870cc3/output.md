The request was permitted and scheduled. Here is the factual close-out summary:

---

## Tenure Stewardship Summary — asw-4c-fresh-tenure

### Station condition at tenure start
| Item | Value |
|---|---|
| Duty pump | pump-b — running, flow 0.0262 m³/s |
| Standby pump | pump-a — post-maintenance run-in, restriction active |
| Wet-well level | 1.65 m — stable |
| Inflow | 0.0155 m³/s |
| Work order pump-a | Provisionally closed |

### Outstanding items inherited
| Item | Detail |
|---|---|
| Obligation `obligation-0009-verification` | Active — independent post-maintenance verification of pump-a, due calendar second 8,485,200 |
| Restriction `restriction-0009-run-in` | Active — blocks unrestricted use of pump-a until verification clears it |

### Action taken (proposal `asw-4c-fresh-tenure-01`, sequence 12)
**`request_post_maintenance_verification` for pump-a** — permitted and scheduled (transition-0012).

- Verification process `process-0012-post_maintenance_verification` is now **in progress**, assigned to the `verification` authority, completing at calendar second **8,470,800** — comfortably inside the obligation due time of 8,485,200.
- The run-in restriction (`restriction-0009-run-in`) and obligation (`obligation-0009-verification`) remain active until the verification authority delivers its finding and the process closes.
- No evidence was invented; the request is grounded solely in `evidence-0008-functional-checks` (functional checks passed, accepted by verification at calendar second 8,427,600).
- The provisional work-order closure was correctly treated as insufficient on its own — independent verification is a separate duty.

### Remaining watch points for next steward
1. **Await verification outcome** from `process-0012-post_maintenance_verification` (due by calendar second 8,470,800). If passed, restriction-0009-run-in will be lifted and pump-a can be returned to full unrestricted standby service.
2. **Obligation `obligation-0009-verification`** closes only when the verification authority records a positive finding — not before.
3. Station is otherwise stable; no additional interventions are required at this time.