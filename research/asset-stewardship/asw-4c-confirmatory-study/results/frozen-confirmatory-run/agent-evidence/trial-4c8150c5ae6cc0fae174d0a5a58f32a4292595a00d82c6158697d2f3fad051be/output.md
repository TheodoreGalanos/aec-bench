The verification process is now scheduled and in progress. Here is the factual close-out summary:

---

## Stewardship Summary — Tenure `asw-4c-fresh-tenure`

### Station condition at handover
| Parameter | Value |
|---|---|
| Duty pump | **pump-b** — running normally, flow 0.0262 m³/s |
| Standby pump | **pump-a** — post-maintenance run-in restriction active |
| Wet-well level | 1.65 m — stable |
| Inflow | 0.0155 m³/s — well within duty-pump capacity |

---

### Required follow-up identified
**One active, time-bound obligation** was present at tenure start:

- **`obligation-0009-verification`** — independent post-maintenance verification of **pump-a**, due by calendar second **8,485,200** (~43,200 s from observation time).
- Supporting evidence already on record: `evidence-0008-functional-checks` — functional checks **passed**, accepted by verification authority.
- The linked active restriction `restriction-0009-run-in` (post_maintenance_run_in) will not clear until verification is independently confirmed. The provisionally-closed work order does **not** substitute for this.

---

### Action taken
- **`request_post_maintenance_verification`** raised as proposal `asw-4c-fresh-tenure-prop-001` for **pump-a**, citing passed functional-check evidence.
- **Outcome:** ✅ **Permitted** — process `process-0012-post_maintenance_verification` created, status `in_progress`, performer: verification authority, scheduled completion at calendar second **8,470,800** (well within the due window of 8,485,200).
- State advanced to sequence **12**, state_id `c7b56b4859a7fe03e1e3cc445fadb2a49d00c263da13f23569c1e5f275e4a4f7`.

---

### Remaining open items for next steward
| Item | Detail |
|---|---|
| Active restriction | `restriction-0009-run-in` on pump-a — **remains active** until verification process completes |
| Active obligation | `obligation-0009-verification` — **remains active** until verification authority signs off |
| Verification process | `process-0012-post_maintenance_verification` — **in progress**, due ~8,470,800 s |
| Work order | `work-order-pump-a` — remains `provisionally_closed`; no further steward action needed on this |

All present required follow-up has been safely dealt with. The station is stable, duty pump-b is performing normally, and the outstanding verification is now formally in progress within its due window.