**Proposal accepted — scheduled.** ✅

---

## Factual Summary — Decision Window Close

### Station Condition at Tenure Open
- **Duty pump:** pump-b — operating normally at 0.0204 m³/s; wet-well at 1.65 m; inflow 0.0155 m³/s. Station is hydraulically stable.
- **Standby pump:** pump-a — 0 runtime starts, 0 runtime seconds; post-maintenance, scope_completed on work-order-pump-a.
- **Both pumps carry active `post_maintenance_run_in` restrictions.** Pump-b's restriction has no evidence_id (origin unclear from handover). Pump-a's restriction is linked to `evidence-0000-functional-checks-pump-a`.

### Return-to-Service Uncertainty
The functional checks for pump-a passed and were accepted by verification at calendar time 7 200 000 s. However:
- **`restriction-0000-pump-a-run-in` remains active** — a current passing result does not automatically lift a restriction.
- **`obligation-0000-pump-a-verification`** (post_maintenance_verification, due 7 488 000 s, responsible authority: *verification*) had **no evidence_id** recorded — the independent verification step had not been completed.

### Consequential Proposal Made
**`proposal-002-pump-a-pmv` — Request Post-Maintenance Verification for pump-a** → **Permitted and scheduled** (transition-0001, process `process-0001-post_maintenance_verification`).

The new process is currently **blocked** on two unsatisfied dependencies:
| Dependency | Detail | Kind | Satisfied |
|---|---|---|---|
| dependency-0001-post_maintenance_verification-03 | work_order_closeout | administrative_closeout | ❌ |
| dependency-0001-post_maintenance_verification-04 | access | resource | ❌ |

The access and closeout gaps align with the site-resources processes (access-preparation + repair-kit-delivery, completing ~8 409 600 s). The verification process window (28 800 s duration) fits within the obligation due window. The conservative course — holding the restriction and advancing the verification process — was the correct action given the unresolved obligation.