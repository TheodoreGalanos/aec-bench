The proposal was **accepted and scheduled**. Here is the factual summary.

---

## Tenure Decision Summary — episode-cb21683d67b4812b

### Station Condition at Handover
| Item | Value |
|---|---|
| Calendar seconds | 7,200,000 |
| Duty pump | Pump B — 0.0204 m³/s flow, 7,200,000 s runtime, 1,000 starts |
| Standby pump | Pump A — 0 s runtime, 0 starts |
| Inflow | 0.0155 m³/s |
| Wet-well level | 1.65 m (stable) |

### Active Restrictions (both pumps)
- **`restriction-0000-pump-a-run-in`** — post_maintenance_run_in on Pump A; linked to functional check evidence; **still active**
- **`restriction-0000-pump-b-work`** — post_maintenance_run_in on Pump B; no linked evidence; **still active**

### Pump A Return-to-Service Uncertainty
Pump A's work order (`work-order-pump-a`) is `scope_completed` and a passed, accepted functional check (`evidence-0000-functional-checks-pump-a`) exists. However:
- The post_maintenance_run_in **restriction remains active** — a functional check does not lift it.
- **Obligation `obligation-0000-pump-a-verification`** (post_maintenance_verification) is active, due by second 7,488,000 (288,000 s remaining), with `evidence_id = null` — no verification evidence has been lodged.
- Pump A has accumulated **zero run-in runtime**.
- The prefix search found no delayed inspection record; the maintenance procedure confirms the original verification interval applies and isolation must hold until records are accepted.

### Consequential Proposal Made
**`request_post_maintenance_verification` — `proposal-tenure-cb21683d67b4812b-pmv-pump-a-002`**
- **Outcome:** Permitted and scheduled (`process-0001-post_maintenance_verification`, status: `blocked`)
- **Estimated completion:** second 7,228,800 (28,800 s process duration)
- **Blocked on two open dependencies:** administrative closeout (`dependency-0001-post_maintenance_verification-03`, `work_order_closeout` unsatisfied) and access resource (`dependency-0001-post_maintenance_verification-04`, `access` unsatisfied)
- **Rationale:** With the obligation window closing, verification evidence absent, the run-in restriction still active, and no documentary path to resolve the uncertainty without independent verification, the conservative and procedurally required action was to formally schedule post-maintenance verification now. This preserves the obligation deadline, keeps Pump A correctly restricted, and hands the next tenure a live, unblocked verification process to progress rather than an overdue obligation.