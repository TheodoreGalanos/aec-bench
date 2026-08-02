**Proposal accepted — scheduled.** Process `process-0001-post_maintenance_verification` is now live (blocked pending two dependencies: administrative closeout of `work-order-pump-a` and site access). Here is the factual summary:

---

## Decision-Window Summary — Tenure `incoming-tenure-9898e3a5cf489d2d`

### Station condition at tenure start
| Item | Value |
|---|---|
| Duty pump | **Pump B** (1 000 starts, 7 200 000 s runtime) |
| Standby pump | **Pump A** (0 starts, 0 s runtime post-maintenance) |
| Active flow | 0.0204 m³/s (inflow 0.0155 m³/s — station is keeping up) |
| Wet-well level | 1.65 m — normal |
| Station isolated | No |

### Active restrictions (both remain active — neither cleared this window)
- **`restriction-0000-pump-a-run-in`** — post-maintenance run-in, linked to Pump A, evidence: `evidence-0000-functional-checks-pump-a`
- **`restriction-0000-pump-b-work`** — post-maintenance run-in, linked to Pump B (evidence-less)

### Open obligation
- **`obligation-0000-pump-a-verification`** — independent post-maintenance verification for Pump A, due by calendar second **7 488 000** (≈ 80 hours from now) / runtime ceiling 288 000 s, responsible authority: **verification**, status: active, no evidence yet attached.

### Pump A return-to-service uncertainty
Functional checks (`evidence-0000-functional-checks-pump-a`) were produced by **maintenance**, not an independent verifier. The work order (`work-order-pump-a`) is `scope_completed` but the run-in restriction and the verification obligation are both still open. Pump A has accumulated **no post-maintenance runtime**.

### Conservative proposal made
**`proposal-002-pump-a-pmv`** — `request_post_maintenance_verification` for Pump A — **permitted and scheduled** as `process-0001-post_maintenance_verification` (duration 28 800 s; completion projected at second 7 228 800).

The process is currently **blocked** on two unsatisfied dependencies:
1. **Administrative closeout** (`dependency-0001-post_maintenance_verification-03`) — `work-order-pump-a` must be formally closed out.
2. **Site access** (`dependency-0001-post_maintenance_verification-04`) — access window is currently 0 s; access-preparation process completes at second 8 409 600.

### Consequential status
Pump A **cannot return to unrestricted service** until (a) the work order is closed, (b) site access opens, (c) the independent verification process completes, and (d) the run-in restriction is lifted by the responsible verification authority. No shortcuts were taken; the current live functional-check reading does not substitute for independent post-maintenance verification and does not cancel the active restriction.