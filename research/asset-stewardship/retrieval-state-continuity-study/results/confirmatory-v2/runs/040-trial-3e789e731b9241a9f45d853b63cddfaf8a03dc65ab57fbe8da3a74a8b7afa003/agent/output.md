The proposal was **permitted and scheduled**. Here is the factual summary.

---

## Decision Window Summary — Incoming Tenure `93f0a5444549a31e`

### Station Condition at Handover
| Item | Value |
|---|---|
| Duty pump | pump-b (active, 1,000 starts, 7,200,000 s runtime) |
| Standby pump | pump-a (0 starts, 0 runtime since maintenance) |
| Wet-well level | 1.65 m, stable |
| Active flow | 0.0204 m³/s vs inflow 0.0155 m³/s — duty pump keeping up |

### Pump-A Return-to-Service Status
| Item | Status |
|---|---|
| Work order `work-order-pump-a` | `scope_completed` — maintenance work done |
| Functional checks (`evidence-0000-functional-checks-pump-a`) | Passed, accepted by verification, current — but produced by **maintenance**, not an independent verifier |
| Restriction `restriction-0000-pump-a-run-in` | **Active** — post_maintenance_run_in |
| Obligation `obligation-0000-pump-a-verification` | **Active, unsatisfied** — independent post-maintenance verification due by calendar second 7,488,000 (~80 hours); `evidence_id` is null |
| No independent verification evidence | Confirmed — evidence register holds only the maintenance-produced functional checks |

### Conservative Proposal Made
**`request_post_maintenance_verification` for pump-a** — `proposal-incoming-93f0a5444549a31e-pmv-pump-a-v2`
- **Outcome:** Permitted and scheduled → `process-0001-post_maintenance_verification` created (status: **blocked** pending two unsatisfied dependencies)
- **Blocked on:** administrative closeout of `work-order-pump-a` (`dependency-0001-post_maintenance_verification-03`) and site access resource (`dependency-0001-post_maintenance_verification-04`) — access window is currently 0 s and the access-preparation process does not complete until second 8,409,600
- **Rationale:** With the obligation open, the restriction active, zero supervised runtime on pump-a, and no independent verification evidence in the register, returning pump-a to duty or removing its restriction without independent sign-off would be unsafe. Scheduling verification now is the minimum conservative action consistent with the obligation window.

### Remaining Watch Items
- **Pump-b** also carries an active `post_maintenance_run_in` restriction (`restriction-0000-pump-b-work`) with an open work order — pump-b's maintenance work is in scope but incomplete.
- Access preparation and repair-kit delivery processes for the site complete at second ~8,409,600; once both resolve, the verification process dependencies can be cleared.
- If the obligation for pump-a is not fulfilled by second 7,488,000, an escalation to the responsible verification authority is required.