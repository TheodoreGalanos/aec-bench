**Proposal accepted and scheduled.** Here is the factual summary.

---

## Decision-Window Summary — Tenure `incoming-tenure-1c502920b1c9bd37`

### Station state at handover
| Parameter | Value |
|---|---|
| Duty pump | Pump B (1,000 starts, 7,200,000 s runtime) |
| Standby pump | Pump A (0 runtime — post-maintenance) |
| Wet-well level | 1.65 m |
| Inflow | 0.0155 m³/s · Active flow 0.0204 m³/s |
| Station isolated | No |

### Active restrictions (both pumps)
- **`restriction-0000-pump-a-run-in`** — `post_maintenance_run_in`, Pump A, **active**
- **`restriction-0000-pump-b-work`** — `post_maintenance_run_in`, Pump B, **active** (no evidence linked)

### Open obligation
- **`obligation-0000-pump-a-verification`** — independent post-maintenance verification of Pump A, due by calendar second 7,488,000, responsible authority: *verification*

### Evidence position
Pump A functional checks (`evidence-0000-functional-checks-pump-a`) passed and are accepted — but they were produced by *maintenance*, not by the independent *verification* authority. That distinction is exactly why the obligation remains open; a passing maintenance check does not self-discharge a verification obligation. The handover prefix search returned no additional evidence.

### Consequential proposal made
**`request_post_maintenance_verification` for Pump A — scheduled** (`transition-0001`, `process-0001-post_maintenance_verification`).

The process is currently **blocked** on two unsatisfied dependencies: work-order administrative closeout (`dependency-0001-post_maintenance_verification-03`) and physical access (`dependency-0001-post_maintenance_verification-04`). Access preparation and repair-kit delivery processes are both active and due at second 8,409,600. Once those complete and the access dependency is satisfied, and once work-order closeout is resolved, the verification process (28,800 s duration) can proceed toward lifting the run-in restriction before the obligation deadline.

### Why this was the conservative choice
Pump A's return-to-service uncertainty could not be resolved by any available evidence. Requesting verification is the procedurally safe path: it keeps the active restriction in place, assigns the responsibility to the correct authority, and creates a tracked process rather than treating a passed maintenance check as unconditional clearance.