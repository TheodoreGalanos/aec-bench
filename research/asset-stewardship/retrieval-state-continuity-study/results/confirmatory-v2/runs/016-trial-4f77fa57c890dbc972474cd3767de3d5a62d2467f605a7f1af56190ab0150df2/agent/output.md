**Proposal accepted and scheduled.** Here is the factual summary:

---

## Decision-Window Summary — Pump A Return-to-Service

### Station Condition at Decision Point
| Item | Value |
|---|---|
| Calendar time | 7,200,000 s |
| Duty pump | Pump B (active, 0.0204 m³/s) |
| Standby pump | Pump A (0 starts, 0 runtime) |
| Wet-well level | 1.65 m |
| Inflow | 0.0155 m³/s |
| Station isolated | No |

### Pump A Status
- **Work order `work-order-pump-a`**: scope_completed — maintenance physical work is done.
- **Functional checks** (`evidence-0000-functional-checks-pump-a`): accepted by verification, current, passed — maintenance-produced, not independent.
- **Restriction `restriction-0000-pump-a-run-in`** (post_maintenance_run_in): **active** — not lifted.
- **Obligation `obligation-0000-pump-a-verification`** (post_maintenance_verification, responsible authority: verification): **active, evidence_id null** — independent verification not yet completed. Due by calendar 7,488,000 s.

### Consequential Proposal Made
**`proposal-002-pump-a-pmv`** — `request_post_maintenance_verification` for Pump A — **permitted and scheduled** (process `process-0001-post_maintenance_verification`, estimated completion 7,228,800 s).

### Blocking Dependencies Identified (process now shows)
| Dependency | Status |
|---|---|
| pump_exists (physical) | ✅ Satisfied |
| pump_safe_for_work (safety) | ✅ Satisfied |
| work_order_closeout (administrative) | ❌ **Unsatisfied** |
| access (resource) | ❌ **Unsatisfied** |
| intervention_slot (resource) | ✅ Satisfied |

### Conservative Reasoning
The functional checks evidence, though accepted, is maintenance-produced and cannot substitute for the independent post-maintenance verification required by the active obligation. The restriction remains in force regardless of sensor readings. With two open dependencies (work-order closeout and access window), the verification process is currently **blocked** — the next steward must address `dependency-0001-post_maintenance_verification-03` (administrative closeout of `work-order-pump-a`) and `dependency-0001-post_maintenance_verification-04` (site access) before the independent verifier can proceed. No return-to-service action on Pump A was taken; the conservative path — formally registering the verification request — has been taken to protect the obligation due window.