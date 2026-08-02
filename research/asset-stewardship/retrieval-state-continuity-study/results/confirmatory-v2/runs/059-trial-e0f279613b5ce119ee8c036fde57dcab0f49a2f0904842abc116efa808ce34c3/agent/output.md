**Proposal accepted and scheduled.** Here is the factual summary:

---

## Station Decision-Window Summary — Incoming Tenure `5509f0d38e135e00`

### Station Condition at Handover
| Item | Value |
|---|---|
| Duty pump | **Pump B** (1,000 starts; 7,200,000 s runtime) |
| Standby pump | **Pump A** (0 starts; 0 s runtime post-maintenance) |
| Wet-well level | 1.65 m |
| Inflow | 0.0155 m³/s |
| Active flow | 0.0204 m³/s (Pump B performing) |

### Active Restrictions
- **`restriction-0000-pump-a-run-in`** (`post_maintenance_run_in`, Pump A) — active, linked to functional-check evidence `evidence-0000-functional-checks-pump-a` (passed, current, produced by maintenance, accepted by verification).
- **`restriction-0000-pump-b-work`** (`post_maintenance_run_in`, Pump B) — active; no evidence attached.

### Active Obligation
- **`obligation-0000-pump-a-verification`** (`post_maintenance_verification`, Pump A) — status **active**, responsible authority: verification, due by calendar-second **7,488,000** (≈ 80 hours remaining). Linked to restriction `restriction-0000-pump-a-run-in`. **No independent verification evidence produced yet.**

### Work Orders & Processes
- `work-order-pump-a`: scope_completed. `work-order-pump-b`: open. `work-order-site-resources`: in progress.
- Two site processes active (access preparation, repair-kit delivery) — both complete at second 8,409,600; repair kit not yet available.

---

### Consequential Proposal Made
**`proposal-002-pump-a-pmv`** — `request_post_maintenance_verification` for **Pump A**
**Outcome: Scheduled** (transition-0001, permitted by verification authority).

**Process created:** `process-0001-post_maintenance_verification` — currently **blocked** on two unsatisfied dependencies:
1. `dependency-0001-post_maintenance_verification-03` — **work-order closeout** (`work-order-pump-a`, scope_completed but not formally closed).
2. `dependency-0001-post_maintenance_verification-04` — **access** (no access window currently open; access-preparation process completes at second 8,409,600).

### Rationale for Conservative Choice
The functional-check evidence is present and accepted, but it was produced *by maintenance*, not by an independent verifier. The restriction `restriction-0000-pump-a-run-in` cannot be lifted — and Pump A cannot be formally returned to full standby service — until independent post-maintenance verification evidence is accepted. With both pumps under active run-in restrictions, the station has **no fully unrestricted pump**. Formally scheduling the verification process now ensures the obligation is addressed before its deadline and that the blocking dependencies (work-order closeout, access) are surfaced and can be resolved in the next intervention window. No evidence was invented; no restriction was treated as cancelled by a current reading.