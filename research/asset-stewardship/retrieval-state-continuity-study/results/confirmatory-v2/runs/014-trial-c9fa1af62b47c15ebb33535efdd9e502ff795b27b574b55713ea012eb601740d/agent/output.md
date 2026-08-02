**Proposal accepted and scheduled.** Here is the factual summary:

---

## Station Decision Window — Factual Summary

### Station Condition at Handover (calendar second 7,200,000)
| Parameter | Value |
|---|---|
| Duty pump | Pump B (active, 7,200,000 s runtime, 1,000 starts) |
| Standby pump | Pump A (0 s runtime, 0 starts — post-maintenance) |
| Active flow | 0.0204 m³/s |
| Inflow | 0.0155 m³/s |
| Wet-well level | 1.65 m |
| Station isolated | No |

### Restrictions in Force
- **Pump A** — `restriction-0000-pump-a-run-in`: active `post_maintenance_run_in`. Linked to functional-checks evidence (`evidence-0000-functional-checks-pump-a`, passed, accepted by verification). **Does not self-clear** — requires the separate verification obligation to be discharged.
- **Pump B** — `restriction-0000-pump-b-work`: active `post_maintenance_run_in` (no evidence attached). Pump B work order is open.

### Active Obligation
- `obligation-0000-pump-a-verification`: `post_maintenance_verification` for Pump A, due at calendar second **7,488,000** (288,000 s runtime). Evidence field is **null** — obligation unsatisfied. Responsible authority: **verification**.

### Key Finding — Return-to-Service Uncertainty
The passed functional-checks evidence confirms bench-level checks were completed but **does not discharge the independent post-maintenance verification obligation**. Pump A has accumulated zero runtime in standby; no run-in hours have elapsed. With both pumps under active run-in restrictions, Pump A's unrestricted return to full standby readiness depends entirely on timely completion of the outstanding verification.

### Proposal Made
**`proposal-002-pump-a-pmv`** — `request_post_maintenance_verification` for **Pump A** — **permitted and scheduled** (transition `transition-0001`, process `process-0001-post_maintenance_verification`).

### Process Status After Proposal
The verification process is **blocked** on two unsatisfied dependencies:
1. `dependency-0001-post_maintenance_verification-03` — **work-order closeout** (`work-order-pump-a` is `scope_completed` but not closed)
2. `dependency-0001-post_maintenance_verification-04` — **access** (access window is 0 s; access-preparation process completes at second 8,409,600)

Both blocking dependencies must be resolved by work management before the verification authority can proceed. The verification process has a 28,800 s (8-hour) duration and must complete before the obligation due date. The conservative proposal — requesting verification now — is correct: it places the process in the queue, makes the dependencies visible, and ensures no time is lost once access and closeout are ready.