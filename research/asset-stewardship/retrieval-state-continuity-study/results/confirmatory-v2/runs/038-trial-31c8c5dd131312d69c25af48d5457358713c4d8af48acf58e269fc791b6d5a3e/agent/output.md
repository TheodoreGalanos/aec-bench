**Proposal accepted and scheduled.** ✅

---

## Post-Proposal Factual Summary

**Proposal:** `proposal-003-pmv-pump-a-tenure-a1fe4f677c7b3de0` — `request_post_maintenance_verification` for **pump-a**
**Outcome:** Permitted and scheduled (transition-0001, sequence 1)

---

### Station State at Close of Decision Window

| Element | Status |
|---|---|
| **Duty pump** | pump-b — active, flow 0.0204 m³/s, wet-well 1.65 m, stable |
| **Standby pump** | pump-a — 0 runtime starts, post-maintenance run-in restriction still active |
| **PMV process created** | `process-0001-post_maintenance_verification` — status **BLOCKED**, ETA 7,228,800 s (28,800 s duration) |
| **PMV blocking dependencies** | (1) `dependency-0001-post_maintenance_verification-03`: work-order closeout for `work-order-pump-a` — **unsatisfied**; (2) `dependency-0001-post_maintenance_verification-04`: site access — **unsatisfied** (access_window_seconds = 0, repair kit not yet available) |
| **PMV dependencies satisfied** | pump exists ✅ · pump safe for work ✅ · intervention slot available ✅ |
| **Obligation** | `obligation-0000-pump-a-verification` remains active; due calendar 7,488,000 s / runtime 288,000 s |
| **Restriction** | `restriction-0000-pump-a-run-in` remains active (will lift only when PMV evidence is accepted) |
| **pump-b restriction** | `restriction-0000-pump-b-work` active; work-order-pump-b open |
| **Site processes** | access_preparation + repair_kit_delivery running; both ETA 8,409,600 s |

### Why this was the conservative, correct choice

Pump-A's maintenance-produced functional-checks evidence (`evidence-0000-functional-checks-pump-a`) is accepted, but **independent post-maintenance verification** — a distinct, separately-required obligation by the verification authority — had no evidence and no scheduled process at handover. A positive sensor reading does not discharge a mandatory independent verification. Requesting PMV now formally schedules the process, surfaces its two blocking dependencies (work-order closeout, site access), and puts the obligation on a tracked path to resolution well before the due window at calendar 7,488,000 s. Pump-a remains correctly in restricted standby until verification evidence is accepted.