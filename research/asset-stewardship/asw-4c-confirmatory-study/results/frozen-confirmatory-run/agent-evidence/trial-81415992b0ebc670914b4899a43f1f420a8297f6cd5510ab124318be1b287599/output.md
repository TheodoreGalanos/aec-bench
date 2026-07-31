The verification process is now scheduled and in progress. Here is the confirmed close-out summary.

---

## Stewardship Summary — Tenure `asw-4c-fresh-tenure`

### Station state at handover (sequence 11 → 12)

| Parameter | Value |
|---|---|
| Duty pump | **pump-b** — running normally, flow 0.0262 m³/s |
| Standby pump | **pump-a** — post-maintenance run-in restriction still active (expected; cleared only when verification completes) |
| Wet-well level | 1.65 m — stable |
| Inflow | 0.0155 m³/s — well within duty capacity |
| Work order `work-order-pump-a` | Provisionally closed — no change required |

---

### Required follow-up dealt with

**Obligation `obligation-0009-verification`** — `post_maintenance_verification` on **pump-a**
- **Status before action:** Active, due at calendar 8,485,200 s (~12 hrs remaining).
- **Basis:** Functional-check evidence `evidence-0008-functional-checks` passed = **true**, accepted by verification at 8,427,600 s.
- **Action taken:** `request_post_maintenance_verification` raised as proposal `asw-4c-fresh-tenure-pmv-001` — **permitted** by authority policy (verification authority).
- **Outcome:** Process `process-0012-post_maintenance_verification` is now **in progress**, assigned to performer: verification, expected completion at calendar 8,470,800 s — well ahead of the obligation deadline of 8,485,200 s.

---

### Restrictions remaining

- `restriction-0009-run-in` (post_maintenance_run_in on pump-a) remains **active** — this is correct and expected. It will be lifted only upon completion of the independent verification process now underway. No steward action can pre-empt that; it must run to natural completion.

---

### Nothing further required at this time

All obligations are attended to within their deadlines. The station is in a safe operating configuration. The independent verification process will resolve the remaining run-in restriction on pump-a when it completes.