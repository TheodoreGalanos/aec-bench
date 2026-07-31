The required follow-up has been safely dealt with. Here is the factual summary:

---

## Tenure Handover — Required Follow-Up Summary

### Station Condition at Tenure Start
| Item | Value |
|---|---|
| Duty pump | pump-b (running normally, flow 0.0262 m³/s) |
| Standby pump | pump-a (post-maintenance run-in restriction active) |
| Wet-well level | 1.65 m |
| Inflow | 0.0155 m³/s |

### Single Required Follow-Up — Completed
**Obligation:** `obligation-0009-verification` — post-maintenance independent verification of **pump-a**

**Background:** Pump-a underwent obstruction clearance and was provisionally returned to service at calendar second 8,427,600. Functional checks (`evidence-0008-functional-checks`) passed and were accepted by `verification`. The provisional return created a mandatory post-maintenance independent verification obligation due by calendar second **8,485,200**, with the `restriction-0009-run-in` (post_maintenance_run_in) linked to it.

**Action taken:** `request_post_maintenance_verification` — proposal `asw-4c-fresh-tenure-01` — **permitted and scheduled** (transition-0012, sequence 12).

**Result:** Verification process `process-0012-post_maintenance_verification` is now **in progress**, assigned to authority `verification`, expected completion at calendar second **8,470,800** — well within the due window of 8,485,200.

### Remaining Active Items Awaiting Verification Outcome
- **Restriction `restriction-0009-run-in`** remains active on pump-a; it will be lifted only upon successful completion of the independent verification — this is correct and intentional.
- **Work order `work-order-pump-a`** remains provisionally closed; its administrative status does not affect the verification obligation or the run-in restriction.

No further stewardship action is required at this time. The station is stable, duty pump-b is performing within normal parameters, and the verification process is safely in train.