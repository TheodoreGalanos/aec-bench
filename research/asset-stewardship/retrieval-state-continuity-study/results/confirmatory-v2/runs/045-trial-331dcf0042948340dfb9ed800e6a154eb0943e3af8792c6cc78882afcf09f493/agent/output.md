Proposal accepted and scheduled. Here is the factual post-proposal summary.

---

## Post-Proposal Factual Summary

### Proposal Made
**`request_post_maintenance_verification` for Pump A**
Proposal ID: `proposal-tenure-2c8045781317ceef-pmv-pump-a-002`
Outcome: **Permitted and scheduled** (transition-0001, state sequence 1)

---

### Station Condition at Decision Point

| Item | Status |
|---|---|
| Duty pump | Pump B — active, 1,000 starts, 7,200,000 s runtime |
| Standby pump | Pump A — post-maintenance, 0 starts, 0 runtime |
| Wet-well level | 1.65 m, stable |
| Inflow | 0.0155 m³/s |
| Active flow | 0.0204 m³/s |
| Station isolated | No |

---

### Pump A Return-to-Service Position

| Item | Detail |
|---|---|
| Work order `work-order-pump-a` | `scope_completed` — maintenance work done |
| Functional checks evidence | `evidence-0000-functional-checks-pump-a` — passed, accepted by verification, current |
| Run-in restriction `restriction-0000-pump-a-run-in` | **Active** — not lifted |
| Verification obligation `obligation-0000-pump-a-verification` | **Active, evidence_id: null** — independent verification not yet performed; due at calendar 7,488,000 (288,000 s window) |

---

### What the Proposal Did

A new process `process-0001-post_maintenance_verification` (performer: **verification**, duration: 28,800 s, completion target: 7,228,800 s) has been formally scheduled. It is currently **blocked** on two unsatisfied dependencies:

| Dependency | Detail | Satisfied |
|---|---|---|
| `dependency-0001-post_maintenance_verification-03` | Work-order administrative closeout | **No** |
| `dependency-0001-post_maintenance_verification-04` | Access window | **No** |

The physical and safety dependencies are satisfied; one intervention slot is available.

---

### Why This Was the Conservative Correct Choice

- Independent verification evidence is absent from the record; the obligation cannot be deemed satisfied by the functional checks alone (different authority, different standard).
- No provisional return could be requested without `functional_check_evidence_id` accepted under the verification authority for the post-run-in regime.
- Formally scheduling the verification process activates its dependency tracking, surfaces the two blocking gaps (closeout and access), and keeps the obligation satisfied within its due window — the safest compliant forward step given unresolved evidence.

**Next actions for the incoming steward:** resolve work-order closeout dependency (`dependency-0001-post_maintenance_verification-03`) and confirm access window availability (`dependency-0001-post_maintenance_verification-04`) to unblock the verification process and advance Pump A toward full return to service before the obligation deadline.