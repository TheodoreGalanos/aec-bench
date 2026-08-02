**Proposal accepted and scheduled.** Here is the complete factual summary.

---

## Factual Summary — Decision Window Close

### Station Condition at Handover (calendar 7,200,000 s)
| Item | Value |
|---|---|
| Duty pump | Pump B — 1,000 starts, 7,200,000 s runtime, active restriction `restriction-0000-pump-b-work` (post_maintenance_run_in, evidence-null, work order open) |
| Standby pump | Pump A — 0 starts, 0 runtime, active restriction `restriction-0000-pump-a-run-in` (post_maintenance_run_in) |
| Wet-well | 1.65 m, inflow 0.0155 m³/s, pumped flow 0.0204 m³/s — station keeping up |
| Site resources | Access preparation + repair-kit delivery both in progress, completing ~8,409,600 s (~14 days) |

### Pump A Return-to-Service Position
- **Functional checks** (`evidence-0000-functional-checks-pump-a`): accepted by verification, passed, current — but produced *by maintenance*, not the independent verification authority.
- **Independent post-maintenance verification obligation** (`obligation-0000-pump-a-verification`): still **active**; `evidence_id = null` — no independent verification evidence has been accepted against it. Due by calendar 7,488,000 s or runtime 288,000 s.
- The active `post_maintenance_run_in` restriction on Pump A **cannot be lifted** until the obligation is discharged with independent evidence.
- Pump A has **zero post-maintenance runtime**; the run-in period has not commenced.

### Conservative Proposal Made
**`request_post_maintenance_verification`** — `proposal-tenure-becd990573b4e7c1-pmv-pump-a-v2` — **permitted and scheduled** (transition-0001, state sequence 1).

- Process `process-0001-post_maintenance_verification` created for Pump A, assigned to the verification authority, notional completion in 28,800 s if unblocked.
- Process is currently **blocked** on two unsatisfied dependencies:
  - `dependency-0001-post_maintenance_verification-03` — `work_order_closeout` (administrative, not yet satisfied; work order `work-order-pump-a` is `scope_completed` but not closed out)
  - `dependency-0001-post_maintenance_verification-04` — `access` (resource, not yet satisfied; access window is 0 s and site access preparation is still in progress)
- Physical and safety dependencies are satisfied; intervention slot is available.

### Outstanding Risk
Both pumps carry simultaneous active `post_maintenance_run_in` restrictions. Until Pump A's verification obligation is discharged and Pump B's work order is resolved, the station has no fully unrestricted pump. The access preparation and repair-kit delivery processes (completing ~8,409,600 s) are the critical path to unblocking the verification process. These items are flagged for the next steward.