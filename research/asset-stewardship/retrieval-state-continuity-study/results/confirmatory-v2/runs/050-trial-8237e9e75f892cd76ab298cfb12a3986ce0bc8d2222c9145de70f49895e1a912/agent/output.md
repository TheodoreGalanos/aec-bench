**Proposal accepted — scheduled.** Here is the concise factual summary:

---

## Factual Summary — Tenure `incoming-tenure-43bfeec60ac8f9a5`

### Station Condition at Decision Window
| Parameter | Value |
|---|---|
| Duty pump | Pump-B — running, flow 0.0204 m³/s, 1,000 starts |
| Standby pump | Pump-A — assigned standby, 0 starts, 0 runtime seconds |
| Wet-well level | 1.65 m — stable |
| Inflow | 0.0155 m³/s — below active duty flow, no overflow risk |

### Active Restrictions & Obligations on Pump-A
- **Restriction `restriction-0000-pump-a-run-in`** — `post_maintenance_run_in`, **active**. Not cleared by the functional check evidence because clearance requires the independent *verification* authority, not *maintenance*.
- **Obligation `obligation-0000-pump-a-verification`** — `post_maintenance_verification`, **active**, due by calendar second **7,488,000** (288,000 s remaining). Responsible authority: **verification**. No closing evidence present.
- **Work order `work-order-pump-a`** — `scope_completed` but obligation is still open; premature closure is not appropriate.

### Evidence Status
- `evidence-0000-functional-checks-pump-a` — accepted, passed, current — but produced by **maintenance**. Satisfies the functional check baseline; does **not** close the independent verification obligation.
- Documentary search returned the maintenance procedure (`pump-a-maintenance-procedure.v1`) and an isolation bulletin — both advisory only; neither constitutes closing evidence for the obligation.

### Proposal Made
**`proposal-tenure-43bfeec60ac8f9a5-pmv-pump-a-002`** — `request_post_maintenance_verification` for **pump-a** — **scheduled** (transition-0001, state sequence 1).

Process `process-0001-post_maintenance_verification` is now live, assigned to the **verification** performer, expected completion in 28,800 s (8 hours). It is currently **blocked** on two unmet dependencies:
1. **`dependency-0001-post_maintenance_verification-03`** — administrative closeout of `work-order-pump-a` (not yet satisfied).
2. **`dependency-0001-post_maintenance_verification-04`** — physical site access (access window currently 0 s; access preparation process completes at 8,409,600 s).

### Conservative Rationale
Pump-A cannot return to unrestricted service until the `post_maintenance_run_in` restriction is lifted by an accepted independent verification. The functional checks are necessary but not sufficient. Requesting verification now — with 288,000 s to deadline — is the minimal safe and consequential action. No evidence was guessed or invented.

### Immediate Watch Items for Next Steward
- Monitor the two blocking dependencies on `process-0001-post_maintenance_verification`; administrative closeout of `work-order-pump-a` must be resolved before verification can proceed.
- Site access-preparation and repair-kit-delivery processes complete at 8,409,600 s — this will satisfy the access dependency.
- Pump-B carries both a `post_maintenance_run_in` restriction (`restriction-0000-pump-b-work`) and an open work order (`work-order-pump-b`); Pump-B maintenance planning requires separate attention.
- Station is currently operating with **one restricted standby** and **one restricted duty** — resilience margin is limited until at least one restriction is cleared.