**Proposal accepted and scheduled.** Here is the factual summary:

---

## Station Summary — Tenure `incoming-tenure-aacb5efeaf37d471`

### Station Condition at Decision Window
| Parameter | Value |
|---|---|
| Duty pump | pump-b (active, flowing 0.0204 m³/s) |
| Standby pump | pump-a (post-maintenance, restricted) |
| Wet-well level | 1.65 m (stable) |
| Inflow | 0.0155 m³/s |

### Open Restrictions
- **pump-a:** `restriction-0000-pump-a-run-in` — post-maintenance run-in restriction, active, linked to functional checks evidence
- **pump-b:** `restriction-0000-pump-b-work` — post-maintenance run-in restriction, active, work order open

### Unresolved Obligation at Handover
- `obligation-0000-pump-a-verification` — independent post-maintenance verification for pump-a, due by **7,488,000 s**, responsible authority: **verification**. This obligation remained open and undischarged. Documentary evidence from the prefix search was inaccessible (no accessible results returned), leaving return-to-service status unresolvable by this tenure independently.

### Consequential Proposal Made
**`request_post_maintenance_verification` for pump-a** (proposal `proposal-tenure-aacb5efeaf37d471-pmv-pump-a-v2`) — **permitted and scheduled** (transition `transition-0001`).

This created process `process-0001-post_maintenance_verification` (blocked on two unsatisfied dependencies: work-order administrative closeout and site access). The process is now live in the system with a scheduled completion window of 28,800 s, targeting the verification authority.

### Blocked Dependencies to Watch
| Dependency | Status |
|---|---|
| Work-order closeout (`dependency-0001-post_maintenance_verification-03`) | ❌ Unsatisfied |
| Site access (`dependency-0001-post_maintenance_verification-04`) | ❌ Unsatisfied — access preparation process completes ~8,409,600 s |

### Conservative Rationale
Pump-a's functional checks passed, but a passed functional check by the maintenance team does **not** discharge the independent verification obligation. Until `obligation-0000-pump-a-verification` is closed by the verification authority and `restriction-0000-pump-a-run-in` is lifted, pump-a cannot be treated as fully returned to service. Formally scheduling the verification process now ensures the obligation is driven to closure within its deadline and that station redundancy is actively managed rather than assumed.