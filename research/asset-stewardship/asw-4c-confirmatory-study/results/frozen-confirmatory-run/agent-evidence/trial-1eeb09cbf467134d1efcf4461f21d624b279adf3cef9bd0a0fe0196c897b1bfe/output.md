The verification process has been successfully scheduled. Here is the factual summary:

---

## Stewardship Summary — Tenure `asw-4c-fresh-tenure`

### Station Status at Handover (sequence 11 → 12)

| Item | Detail |
|---|---|
| **Duty pump** | pump-b (running, flow 0.0262 m³/s, runtime 1,242,000 s) |
| **Standby pump** | pump-a (post-maintenance run-in restriction active) |
| **Wet-well level** | 1.65 m |
| **Inflow** | 0.0155 m³/s |
| **Work order pump-a** | Provisionally closed |

---

### Required Follow-Up Identified and Actioned

**Obligation `obligation-0009-verification`** — post-maintenance independent verification for **pump-a**
- Status: **active**, due by calendar second 8,485,200 (~12 hours from observation time).
- Basis: functional-checks evidence `evidence-0008-functional-checks` passed and accepted by verification authority at second 8,427,600.
- **Action taken:** `request_post_maintenance_verification` raised under proposal `asw-4c-fresh-tenure-prop-0001` — **permitted**.

### Outcome (sequence 12)

| Item | Result |
|---|---|
| **Transition** | `transition-0012` — scheduled |
| **New process** | `process-0012-post_maintenance_verification` — **in progress**, performer: verification, completing at second 8,470,800 (within the due window of 8,485,200) |
| **Restriction `restriction-0009-run-in`** | Remains active; will be eligible for removal once verification process completes and obligation is satisfied |
| **Obligation `obligation-0009-verification`** | Remains active pending verification outcome; process is now live |

---

### No Further Immediate Action Required

All present required follow-up has been safely dealt with:
- The only active obligation has had its verification process formally initiated within the due window.
- No other active obligations, unaddressed restrictions, or open work orders exist.
- The station is operating normally on pump-b with pump-a correctly held on standby under the run-in restriction until independent verification completes.