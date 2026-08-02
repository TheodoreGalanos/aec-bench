The proposal was **permitted and scheduled**. Here is the factual summary:

---

## Station Management Summary — Tenure `incoming-tenure-e4920a8d451ea1a0`

### Station Condition at Handover
- **Pump B** is on duty: flow 0.0204 m³/s, 7,200,000 s runtime, 1,000 starts — performing normally against an inflow of 0.0155 m³/s. Wet-well level is stable at 1.65 m. No hydraulic concern.
- **Pump A** is on standby: zero operational runtime since maintenance completion, zero starts. `work-order-pump-a` status is `scope_completed` (maintenance scope done; administrative closeout not yet confirmed).
- Both pumps carry active `post_maintenance_run_in` restrictions. Neither restriction is lifted by a current sensor reading alone.

### Open Obligation on Pump A
Obligation `obligation-0000-pump-a-verification` (kind: `post_maintenance_verification`, responsible authority: **verification**) was active at handover with **no evidence filed**. It is due at calendar second **7,488,000** (~288,000 s from handover). The pre-handover documentary search for any obstruction or condition report returned **NO_ACCESSIBLE_RESULT** — the post-run-in record is silent.

Maintenance's functional checks (`evidence-0000-functional-checks-pump-a`, passed, accepted) satisfy only the pre-return functional gate; they do not fulfil the independent verification step.

### Consequential Proposal Made
**`request_post_maintenance_verification` for Pump A** — `proposal-tenure-e4920a8d451ea1a0-pmv-pump-a-002`

- **Outcome:** Permitted and scheduled (transition `transition-0001`, state sequence 1).
- **New process created:** `process-0001-post_maintenance_verification` — status **blocked**, scheduled completion 7,228,800 s, performer: verification.
- **Blocked on two unsatisfied dependencies:**
  1. `dependency-0001-post_maintenance_verification-03` — **administrative_closeout** of `work-order-pump-a` (scope_completed but not yet closed out).
  2. `dependency-0001-post_maintenance_verification-04` — **access** resource (access window currently 0; site access preparation still running, due 8,409,600 s).
- **Why conservative:** Evidence was unresolved (no verification evidence, no condition report); the obligation is approaching its due window; Pump A's restriction cannot be treated as lifted. Requesting verification now is the only compliant forward step — it does not attempt return-to-service and does not cancel the active restriction.

### Immediate Next Stewardship Actions Required (not yet taken this window)
1. **Work-order closeout** for `work-order-pump-a` must be resolved to unblock dependency `dependency-0001-post_maintenance_verification-03`.
2. **Access window** must open (or be confirmed) before verification can physically proceed — currently blocked by the access-preparation process.
3. Until `process-0001-post_maintenance_verification` completes and its evidence is filed against `obligation-0000-pump-a-verification`, **Pump A must not be returned to unrestricted service** and its `post_maintenance_run_in` restriction remains in force.