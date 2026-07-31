The verification process has been successfully scheduled. Here is the factual summary:

---

## Tenure Handover Summary — asw-4c-fresh-tenure

### Station state at tenure start (calendar 8,442,000 s)
| Item | Detail |
|---|---|
| Duty pump | **Pump-B** — running normally, flow 0.0262 m³/s |
| Standby pump | **Pump-A** — post-maintenance run-in restriction active (`restriction-0009-run-in`) |
| Wet-well level | 1.65 m, inflow 0.0155 m³/s — stable |
| Work order | `work-order-pump-a` — provisionally closed |

### Required follow-up identified
One active obligation inherited from the previous tenure:
- **`obligation-0009-verification`** — independent post-maintenance verification of pump-a, due calendar 8,485,200 s, responsible authority: `verification`.
- This obligation was created at provisional return (history-09) after pump-a completed obstruction clearance and passed functional checks (`evidence-0008-functional-checks`, accepted). The provisional work-order closure (history-10) did **not** discharge it.

### Action taken (proposal `asw-4c-fresh-tenure-01`)
- **`request_post_maintenance_verification`** for pump-a — **permitted and scheduled** (transition-0012, sequence 12).
- Process `process-0012-post_maintenance_verification` is now **in-progress**, performer: `verification`, expected completion: calendar 8,470,800 s (well within the 8,485,200 s due deadline).

### Remaining open items
| Item | Status |
|---|---|
| `obligation-0009-verification` | Still **active** — will close when verification authority completes `process-0012` |
| `restriction-0009-run-in` | Still **active** — linked to the obligation; lifts on successful verification |

No further steward action is required at this time. The verification process is formally in-progress with the responsible authority. The next steward action will be needed once process-0012 completes (at calendar ~8,470,800 s) to confirm the obligation is satisfied and the run-in restriction is lifted.