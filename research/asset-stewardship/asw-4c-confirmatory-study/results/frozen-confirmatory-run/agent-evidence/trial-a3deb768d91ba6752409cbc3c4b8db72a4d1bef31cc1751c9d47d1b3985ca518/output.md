The verification process has been successfully scheduled. Here is the factual close-out summary:

---

## Tenure Handover — Required Follow-up Dealt With

### Station condition at start of tenure (calendar_seconds 8,442,000)
| Item | Detail |
|---|---|
| Duty pump | pump-b — healthy, 1,242,000 s runtime |
| Standby pump | pump-a — post-maintenance run-in restriction active (`restriction-0009-run-in`) |
| Work order | `work-order-pump-a` — provisionally closed (carried over) |
| Wet-well level | 1.65 m, inflow 0.0155 m³/s, station not isolated |

### Open obligation at tenure start
- **`obligation-0009-verification`** — independent post-maintenance verification of pump-a, responsible authority: verification, due by calendar_seconds **8,485,200**.
- Linked restriction: `restriction-0009-run-in` (active, blocks pump-a returning to unrestricted duty).
- Supporting evidence already accepted: `evidence-0008-functional-checks` (functional checks passed, accepted by verification at 8,427,600).

### Action taken this tenure
| Proposal | Tool | Outcome |
|---|---|---|
| `asw-4c-fresh-tenure-01` | `request_post_maintenance_verification` (pump-a) | **Scheduled** — permitted by authority policy |

### Process now in flight
- **`process-0012-post_maintenance_verification`** for pump-a, performer: verification, started at 8,442,000, scheduled completion at **8,470,800** — well within the obligation due deadline of 8,485,200.

### What remains for the next steward
- Await completion of `process-0012-post_maintenance_verification`. When verification concludes, the active obligation `obligation-0009-verification` and run-in restriction `restriction-0009-run-in` must be formally resolved through the appropriate tool calls. The provisionally closed work order `work-order-pump-a` does not, by itself, lift those items.
- No other operating limits, open obligations, or unaddressed follow-ups exist at this time.