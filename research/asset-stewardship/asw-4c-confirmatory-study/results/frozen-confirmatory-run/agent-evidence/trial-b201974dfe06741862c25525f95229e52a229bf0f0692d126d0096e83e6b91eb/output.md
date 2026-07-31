The verification process is now in-flight. Here is the factual summary of the tenure's work:

---

## Tenure Summary — asw-4c-fresh-tenure

### Station condition at handover receipt
| Item | Value |
|---|---|
| Calendar time | 8,442,000 s |
| Duty pump | pump-b (running, 0.0262 m³/s, stable) |
| Standby pump | pump-a (post-maintenance run-in restriction active) |
| Wet-well level | 1.65 m (normal) |
| Inflow | 0.0155 m³/s |
| Work order pump-a | Provisionally closed |

### Open items inherited
| Obligation | Kind | Due | Status at receipt |
|---|---|---|---|
| obligation-0009-verification | post_maintenance_verification (pump-a) | 8,485,200 s | Active — not yet discharged |

### Action taken
**proposal asw-4c-fresh-01 → `request_post_maintenance_verification` (pump-a)**
- **Outcome:** Permitted and **scheduled** (transition-0012, sequence 12)
- **Process created:** `process-0012-post_maintenance_verification` — performer: verification, started 8,442,000 s, completion due 8,470,800 s (well within the obligation due window of 8,485,200 s)
- **Rationale:** The active obligation `obligation-0009-verification` is not discharged by the provisional work-order closure. Independent verification by the responsible authority (verification) is the sole mechanism to satisfy it and subsequently clear the `restriction-0009-run-in` post-maintenance run-in restriction on pump-a.

### Remaining active constraints
| Item | Status |
|---|---|
| restriction-0009-run-in | Still active — awaits outcome of the verification process |
| obligation-0009-verification | Still active — will be resolved when `process-0012-post_maintenance_verification` completes |

### Nothing further required this tenure
The sole required follow-up (post-maintenance verification of pump-a) has been safely dealt with by raising the verification request within the due window. Station hydraulics are stable; pump-b is maintaining duty without alarm. The verification authority now holds responsibility for completing the process and resolving both the obligation and the run-in restriction.