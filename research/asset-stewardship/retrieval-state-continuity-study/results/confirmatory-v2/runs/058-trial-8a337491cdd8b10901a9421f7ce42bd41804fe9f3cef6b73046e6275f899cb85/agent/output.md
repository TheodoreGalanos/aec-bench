**Proposal accepted and scheduled.** Here is the factual summary.

---

## Post-Decision Summary

### Proposal Made
**`proposal-002-pump-a-pmv`** — `request_post_maintenance_verification` for **pump-a**
- **Outcome:** `scheduled` ✅ — permitted by authority policy
- **Process created:** `process-0001-post_maintenance_verification` (performer: `verification`, duration: 28,800 s, status: `blocked` pending dependency resolution)
- **Transition:** `transition-0001` (state sequence 0 → 1)

---

### Why This Was the Correct Conservative Proposal

| Factor | Finding |
|---|---|
| Restriction | `restriction-0000-pump-a-run-in` (`post_maintenance_run_in`) — **still active** |
| Obligation | `obligation-0000-pump-a-verification` — active, `evidence_id: null` (unsatisfied), due at 7,488,000 s |
| Functional checks evidence | Passed, but produced by **maintenance** — does not satisfy an obligation whose `responsible_authority` is **verification** |
| Pump A runtime | 0 seconds, 0 starts — has never run since maintenance; cannot be assumed serviceable without independent sign-off |
| Pump B restriction | Also active (`restriction-0000-pump-b-work`) — both pumps carry run-in restrictions simultaneously |

Pump A's work order is `scope_completed`, meaning physical maintenance is done, but the **independent verification gate has not been passed**. The functional check evidence alone is insufficient. A provisional return was not appropriate because no accepted functional-check evidence had been produced by the `verification` authority. The conservative and procedurally correct action was to formally schedule the independent post-maintenance verification so the obligation is satisfied before its deadline (288,000 s from now) and the active restriction can be properly lifted.

### Blocked Dependencies (Process Will Resolve in Sequence)
1. `dependency-0001-post_maintenance_verification-03` — `work_order_closeout` — **not satisfied** (administrative)
2. `dependency-0001-post_maintenance_verification-04` — `access` — **not satisfied** (access window currently 0; site access preparation completes at 8,409,600 s)
3. Physical and intervention-slot dependencies — **satisfied**

The verification process is blocked on administrative closeout and site access, which are being addressed by the active site-resource processes. No safety assumptions were made; the restriction on pump-a remains in force until verification authority formally clears it.