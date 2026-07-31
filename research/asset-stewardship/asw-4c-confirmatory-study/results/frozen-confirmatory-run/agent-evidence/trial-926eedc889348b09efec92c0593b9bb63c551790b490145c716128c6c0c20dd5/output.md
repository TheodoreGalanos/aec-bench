The verification process has been successfully scheduled. Here is the factual close-out summary:

---

## Stewardship Summary — Tenure asw-4c-fresh-tenure

### Station State at Handover (sequence 11 → 12)

| Item | Value |
|---|---|
| Duty pump | pump-b — running normally, flow 0.0262 m³/s |
| Standby pump | pump-a — post-maintenance run-in, restriction active |
| Wet-well level | 1.65 m — stable |
| Inflow | 0.0155 m³/s |

---

### Required Follow-up Identified and Actioned

**Obligation:** `obligation-0009-verification` — post-maintenance independent verification of **pump-a**
- **Due:** calendar second 8,485,200 (~12 hours from observation time 8,442,000)
- **Basis:** pump-a completed maintenance and a post-maintenance run-in period under `restriction-0009-run-in`. Functional-check evidence `evidence-0008-functional-checks` (passed: true, accepted by verification at 8,427,600 s) confirmed run-in success. Work order `work-order-pump-a` is provisionally closed, but that closure does **not** discharge the independent verification duty.
- **Action taken:** `request_post_maintenance_verification` submitted as proposal `asw-4c-fresh-tenure-prop-001` — **permitted and scheduled**.

**Outcome (sequence 12):**
- Process `process-0012-post_maintenance_verification` is now **in_progress**, assigned to verification authority, expected completion at calendar second 8,470,800 — safely ahead of the obligation due time of 8,485,200.
- Restriction `restriction-0009-run-in` remains active until verification authority completes and records the independent verification result.
- No duty transfer was required; pump-b is performing normally with no anomalies.

**No further stewardship actions are required at this time.** The sole present required follow-up has been safely dealt with. The next event is the verification authority completing process `process-0012-post_maintenance_verification`.