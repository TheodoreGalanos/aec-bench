The verification process is now scheduled and in progress. Here is the factual close-out summary:

---

## Stewardship Summary — Tenure `asw-4c-fresh-tenure`

### Station Status at Handover (calendar 8,442,000 s)
| Item | Value |
|---|---|
| Duty pump | pump-b (running, 1,242,000 s runtime) |
| Standby pump | pump-a (post-maintenance run-in, restricted) |
| Wet-well level | 1.65 m |
| Active flow | 0.0262 m³/s |
| Work order pump-a | Provisionally closed |

### Required Follow-up Identified
**`obligation-0009-verification`** — independent post-maintenance verification of pump-a, due by calendar 8,485,200 s (~12 hours from handover). Linked to active run-in restriction `restriction-0009-run-in`. No evidence had yet been attached; the provisionally-closed work order did not discharge this duty.

### Action Taken
**`request_post_maintenance_verification`** (proposal `asw-4c-fresh-tenure-01`) submitted for pump-a against `work-order-pump-a`.

- **Authority decision:** Permitted under pump-station-authority-policy.v1
- **Execution:** Scheduled → In progress
- **Process created:** `process-0012-post_maintenance_verification`
- **Performer:** verification authority
- **Process completion due:** 8,470,800 s (well ahead of obligation deadline 8,485,200 s)
- **State advanced:** sequence 11 → 12, state ID `c7b56b4859a7fe03e1e3cc445fadb2a49d00c263da13f23569c1e5f275e4a4f7`

### Remaining Open Items (to be resolved when the process completes)
- `obligation-0009-verification` remains **active** until verification authority closes it with evidence.
- `restriction-0009-run-in` on pump-a remains **active** until that obligation is satisfied — pump-a cannot return to unrestricted standby until then.
- No further steward action is required at this time. The verification process is in the hands of the responsible verification authority and will complete before the obligation deadline.