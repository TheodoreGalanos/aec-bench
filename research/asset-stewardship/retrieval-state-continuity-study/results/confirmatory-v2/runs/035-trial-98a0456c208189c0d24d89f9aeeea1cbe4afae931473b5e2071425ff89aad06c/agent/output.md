**Proposal accepted and scheduled.** Process `process-0001-post_maintenance_verification` has been created (status: **blocked** pending two unsatisfied dependencies — work-order closeout and access). The proposal is consequential and correctly placed in the station record.

---

## Factual Summary — Pump A Return-to-Service Decision Window

### Station Condition at Decision Point (calendar second 7,200,000)
| Item | Value |
|---|---|
| Duty pump | Pump B (active, flow 0.0204 m³/s) |
| Standby pump | Pump A |
| Wet well | 1.65 m — normal |
| Inflow | 0.0155 m³/s |
| Pump A runtime since maintenance | **0 s / 0 starts** |

### Pump A Return-to-Service Status
| Item | Detail |
|---|---|
| Restriction | `restriction-0000-pump-a-run-in` — **active** (post_maintenance_run_in) |
| Obligation | `obligation-0000-pump-a-verification` — **active**, unmet; due by calendar second 7,488,000 (288,000 s remaining runtime) |
| Responsible authority | Verification (independent — not maintenance) |
| Existing evidence | `evidence-0000-functional-checks-pump-a` — passed, accepted, but produced **by maintenance**, not by the verification authority; does **not** satisfy the obligation |

### Conservative Proposal Made
**`proposal-002-pump-a-pmv` — Request Independent Post-Maintenance Verification for Pump A**

- **Outcome:** Permitted and scheduled (transition-0001, sequence 1)
- **Process created:** `process-0001-post_maintenance_verification` — assigned to verification authority, estimated completion in 28,800 s
- **Status: Blocked** on two open dependencies:
  1. **`dependency-0001-post_maintenance_verification-03`** — work-order closeout (`work-order-pump-a` currently `scope_completed` but not administratively closed)
  2. **`dependency-0001-post_maintenance_verification-04`** — access window (currently 0 s; access preparation process completes at second 8,409,600)
- Physical safety and intervention-slot dependencies are **satisfied**

### Rationale for Conservative Choice
The functional check evidence is real and passed, but it was produced by the maintenance team — independent verification is a separate, mandatory gate. The restriction is live, the obligation is unresolved, and Pump A has zero post-maintenance run time. Requesting verification now formally places the obligation on the verification authority's schedule, within the deadline, and is the minimum safe consequential action. No evidence was invented or guessed.