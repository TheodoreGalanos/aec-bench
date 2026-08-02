**Proposal accepted and scheduled.** Here is the factual summary:

---

## Station Decision-Window Summary — Tenure `incoming-tenure-9d6cfed8b412ec24`

### Live Station Condition at Decision Point (calendar s 7,200,000)
| Item | Value |
|---|---|
| Duty pump | Pump B (1,000 starts · 7,200,000 s runtime) |
| Standby pump | Pump A (0 starts · 0 s runtime post-maintenance) |
| Wet-well level | 1.65 m |
| Inflow | 0.0155 m³/s · Active flow 0.0204 m³/s |
| Station isolated | No |

### Open Restrictions
- **`restriction-0000-pump-a-run-in`** — post_maintenance_run_in, active, linked to obligation below.
- **`restriction-0000-pump-b-work`** — post_maintenance_run_in, active (no evidence attached; Pump B work order open).

### Open Obligation
- **`obligation-0000-pump-a-verification`** — post_maintenance_verification, responsible authority: *verification*, due calendar s 7,488,000 / runtime 288,000 s. Evidence ID field **empty** — not yet discharged.

### Functional-Check Evidence
- `evidence-0000-functional-checks-pump-a` — accepted, current, passed, produced by *maintenance* authority. This satisfies the bench check but **does not discharge** the independent verification obligation, which requires the *verification* authority.

### Consequential Proposal Made
**`proposal-002-pump-a-pmv`** — `request_post_maintenance_verification` for Pump A — **scheduled** (transition-0001, state sequence 1).

**Why this and not a provisional return:** No independent verification evidence exists in the register or in documentary search. The functional check was produced by maintenance, not the verification authority. The obligation evidence_id remains null. Pump A has zero post-maintenance runtime. Attempting a provisional return without satisfied verification would bypass the linked restriction and outstanding obligation. Requesting independent post-maintenance verification is the minimum conservative action that advances Pump A toward unrestricted standby service through the correct authority chain, before the obligation deadline.

### Post-Proposal Process State
Process `process-0001-post_maintenance_verification` is now **blocked** on two open dependencies:
1. `dependency-0001-post_maintenance_verification-03` — work-order closeout (unsatisfied)
2. `dependency-0001-post_maintenance_verification-04` — site access (unsatisfied; access-preparation process completes ~s 8,409,600)

These dependencies must be resolved before verification can run. The obligation deadline (s 7,488,000) is tighter than the current access-preparation completion estimate — this gap should be escalated to work management as the priority risk for the next decision window.