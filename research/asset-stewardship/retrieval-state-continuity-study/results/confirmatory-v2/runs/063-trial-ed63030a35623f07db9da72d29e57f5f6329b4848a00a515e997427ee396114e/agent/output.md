**Proposal accepted and scheduled** (`transition-0001`). The post-maintenance verification process (`process-0001-post_maintenance_verification`) has been created and is now **blocked** pending two unsatisfied dependencies. Here is the full factual summary.

---

## Factual Summary — Decision Window Close

### Station Condition at Tenure Start
- **Duty:** Pump B (0 transfers; 1,000 starts; 7,200,000 s runtime). Active flow 0.0204 m³/s vs. inflow 0.0155 m³/s — wet-well level stable at 1.65 m. Station is not isolated.
- **Standby:** Pump A — 0 runtime, 0 starts this cycle.
- **Both pumps** carry active `post_maintenance_run_in` restrictions.
- Two site-resource processes (access preparation, repair-kit delivery) are active with ~14-day completion horizon.

### Pump A Return-to-Service State
| Item | Status |
|---|---|
| Work order `work-order-pump-a` | `scope_completed` |
| Functional checks `evidence-0000-functional-checks-pump-a` | Accepted ✓, passed ✓, current ✓ |
| Restriction `restriction-0000-pump-a-run-in` | **Active** — not yet cleared |
| Obligation `obligation-0000-pump-a-verification` | **Active** — due calendar second 7,488,000 (288,000 s window) |

The functional checks are a necessary but **not sufficient** condition. The independent post-maintenance verification (owned by `verification` authority) must complete before the run-in restriction can be lifted and Pump A declared returned to unrestricted service.

### Consequential Proposal Made
**`proposal-003-pump-a-pmv` — `request_post_maintenance_verification` for `pump-a`** — **Scheduled** ✓

- New process `process-0001-post_maintenance_verification` created; performer: `verification`; projected duration: 28,800 s.
- Process is currently **blocked** on two unsatisfied dependencies:
  - `dependency-0001-post_maintenance_verification-03` — **administrative closeout** (`work_order_closeout`) — not satisfied.
  - `dependency-0001-post_maintenance_verification-04` — **resource: access** — not satisfied (access window = 0 s; access preparation process still running until second 8,409,600).
- Three dependencies are already satisfied: pump exists, pump safe for work, intervention slot available.

### What Remains for Next Steward
1. **Unblock the verification process** once the access preparation process completes (~14 days) and work-order closeout is confirmed.
2. **Monitor obligation-0000-pump-a-verification** — due second 7,488,000; the verification process must complete within that window.
3. **Pump B restriction** (`restriction-0000-pump-b-work`) has no linked evidence yet; `work-order-pump-b` is open — this path is not yet progressed.
4. **Repair-kit delivery** is still in progress; no repair kit is currently available on-site.
5. No duty transfer has been made; Pump B remains duty with zero anomalies recorded at this tenure start.