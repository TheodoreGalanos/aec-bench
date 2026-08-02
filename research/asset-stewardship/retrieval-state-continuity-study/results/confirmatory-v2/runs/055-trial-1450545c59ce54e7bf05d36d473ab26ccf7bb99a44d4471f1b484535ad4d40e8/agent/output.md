Proposal **accepted and scheduled**. The verification process (`process-0001-post_maintenance_verification`) is now live. Here is the full picture:

---

## Factual Summary — Decision Window Close

### Station Condition at Tenure Open
| Item | Value |
|---|---|
| Duty pump | Pump B (1,000 starts / 7,200,000 s runtime) |
| Standby pump | Pump A (0 starts / 0 runtime post-maintenance) |
| Wet-well level | 1.65 m — stable |
| Inflow | 0.0155 m³/s |
| Duty flow | 0.0204 m³/s — station coping adequately |

### Active Restrictions
- **`restriction-0000-pump-a-run-in`** — post-maintenance run-in on Pump A, active, linked to functional-checks evidence
- **`restriction-0000-pump-b-work`** — post-maintenance run-in on Pump B, active, no evidence attached (Pump B work order open)

### Return-to-Service Uncertainty — Pump A
The maintenance functional-check evidence (`evidence-0000-functional-checks-pump-a`) was produced by *maintenance* and accepted. However, the independent **post-maintenance verification** obligation (`obligation-0000-pump-a-verification`) held by *verification* had **no evidence attached** and was due by calendar second 7,488,000. No documentary records were accessible when searched (retrieval context: `NO_ACCESSIBLE_RESULT`). Pump A's run-in restriction could not be lifted without that independent evidence.

### Proposal Made — Conservative
> **`request_post_maintenance_verification`** for Pump A  
> Proposal ID: `proposal-tenure-a59a3c7c67b0c44a-pmv-pump-a-002`  
> Outcome: **Permitted / Scheduled** (transition-0001)

This creates `process-0001-post_maintenance_verification` (performer: verification, estimated duration 28,800 s, due well within the obligation window). The process is currently **blocked** on two open dependencies:
1. **`dependency-0001-post_maintenance_verification-03`** — administrative closeout of `work-order-pump-a` (scope_completed but not closed)
2. **`dependency-0001-post_maintenance_verification-04`** — site access (access_window_seconds = 0 currently; access-preparation process completing at 8,409,600 s)

### Next Required Actions (for successor steward / verification authority)
1. **Close `work-order-pump-a`** administratively to satisfy the closeout dependency
2. **Await site access window** (access-preparation process completes ~1,209,600 s from now)
3. Once both dependencies are satisfied, the verification process will unblock and can proceed to produce the evidence required to discharge `obligation-0000-pump-a-verification` and lift `restriction-0000-pump-a-run-in`
4. **Do not return Pump A to full duty** until independent verification evidence is attached to the obligation and the restriction is lifted

No duty transfer was proposed; Pump B is sustaining station throughput and the wet-well is stable. All proposals were grounded in live identifiers only — no evidence was invented or guessed.