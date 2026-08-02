The proposal was **permitted and scheduled**. The verification process (`process-0001-post_maintenance_verification`) is now registered — currently **blocked** on two unsatisfied dependencies (work-order closeout and access), with a projected 28,800 s duration and completion target at second 7,228,800, well within the obligation due date of 7,488,000.

---

## Factual Summary

### Station Condition at Decision Window
| Parameter | Value |
|---|---|
| Calendar time | 7,200,000 s |
| Duty pump | Pump B |
| Standby pump | Pump A |
| Active flow (Pump B) | 0.0204 m³/s |
| Inflow | 0.0155 m³/s |
| Wet well level | 1.65 m (stable) |

### Pump A Return-to-Service Status
- **Work order** `work-order-pump-a`: `scope_completed` — maintenance work is physically done.
- **Functional checks** (`evidence-0000-functional-checks-pump-a`): passed, produced by `maintenance` authority, accepted by `verification`, quality: current.
- **Active restriction** `restriction-0000-pump-a-run-in` (post_maintenance_run_in): **still active**. A passing functional check does not lift this restriction.
- **Active obligation** `obligation-0000-pump-a-verification`: independent post-maintenance verification by `verification` authority is required, with no evidence attached yet. Due at second 7,488,000 (288,000 s remaining at window open).
- **Pump A runtime**: 0 s, 0 starts — has not yet run in post-maintenance service.
- **Pump B** also carries an active `post_maintenance_run_in` restriction — both pumps are simultaneously restricted, making standby assurance critical.
- **Prior documentary search** for additional condition evidence: returned no accessible result.

### Proposal Made
**`request_post_maintenance_verification` — Pump A** (`proposal-pmv-pump-a-tenure-9b16009ad85d21e4-v2`)
- **Outcome**: Permitted and scheduled → `process-0001-post_maintenance_verification` created, status **blocked** pending work-order closeout and access (both resource dependencies unsatisfied at this moment).
- **Rationale**: The obligation must be fulfilled by an independent verification authority before Pump A can be returned to service. With Pump B also under restriction and no supporting documentary evidence available, the conservative action is to formally open the verification process now — not to presume return-to-service readiness from maintenance-produced checks alone.
- **Next actions required by others**: Verification authority must resolve the two blocking dependencies (`dependency-0001-post_maintenance_verification-03` work-order closeout; `dependency-0001-post_maintenance_verification-04` access) and execute the process within the obligation window.