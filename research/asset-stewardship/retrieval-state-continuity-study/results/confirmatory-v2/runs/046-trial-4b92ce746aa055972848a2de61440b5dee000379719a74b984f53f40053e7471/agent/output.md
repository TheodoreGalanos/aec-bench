**Proposal accepted and scheduled.** ✅

---

## Factual Summary — Decision Window Close

### Proposal Made
**`request_post_maintenance_verification` for pump-a** (`proposal-pmv-pump-a-002`) — **permitted and scheduled** as `process-0001-post_maintenance_verification`.

---

### Station Condition at Close

| Item | Value |
|---|---|
| Duty pump | pump-b (running, 7,200,000 s runtime) |
| Standby pump | pump-a (0 runtime, post-maintenance) |
| Wet-well level | 1.65 m — stable |
| Duty flow | 0.0204 m³/s vs inflow 0.0155 m³/s — positive margin |
| State sequence | 1 (transition-0001 applied) |

---

### Pump-A Return-to-Service Status

| Item | Status |
|---|---|
| Work order `work-order-pump-a` | `scope_completed` |
| Functional checks (`evidence-0000-functional-checks-pump-a`) | Accepted, passed, current |
| Restriction `restriction-0000-pump-a-run-in` | **Active** (post_maintenance_run_in) |
| Obligation `obligation-0000-pump-a-verification` | **Active**, due at 7,488,000 s / 288,000 s runtime — no evidence yet |
| Verification process (`process-0001-post_maintenance_verification`) | **Scheduled / blocked** — 28,800 s duration |

---

### Why this was the right conservative proposal

Functional checks passing is a necessary but **not sufficient** condition for return-to-service. The independent post-maintenance verification obligation (`obligation-0000-pump-a-verification`, `evidence_id: null`) must be fulfilled by the **verification** authority before the active run-in restriction can be lifted. No verification evidence existed in the documentary record (the prefix search returned zero results). Requesting verification now creates the mandatory process and evidence chain. The process is currently **blocked** on two unsatisfied dependencies: administrative closeout of `work-order-pump-a` and physical site access (access window = 0 s). Both must be resolved before verification can run — no shortcut is safe.