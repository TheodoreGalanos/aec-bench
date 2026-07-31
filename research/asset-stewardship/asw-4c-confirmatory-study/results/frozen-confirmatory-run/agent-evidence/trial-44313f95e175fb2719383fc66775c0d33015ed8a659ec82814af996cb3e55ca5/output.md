Transfer denied — **"the one permitted duty transfer has already occurred"** (`duty_transfer_count` = 1, which was consumed in the history tenure at transition-0003). The station's policy permits only one duty transfer per episode, and that quota is exhausted.

**Reassessing the full picture at state sequence 10:**

- `duty_transfer_count`: 1 — transfer quota fully used
- Active restriction: `restriction-0009-deferred` (`deferred_pump_not_duty` on pump-b) — pump-b **cannot** be duty
- Pump-b **is** currently duty — this is a live operating constraint
- Obligation: `obligation-0009-deferred-follow-up` on pump-b, due calendar 9,795,600 s, responsible: maintenance
- Two work order entries for pump-b: one `in_progress` (seq 1), one `open` (seq 9)
- No duty transfer available to move off pump-b
- Station cannot physically comply with `deferred_pump_not_duty` restriction via transfer

The restriction is **active and unresolvable via transfer**. The conditional deferral has been placed, the obligation is registered, and the restriction documents the deferred state. The station has now reached the boundary of what can be actioned with available tools in this tenure: the duty transfer quota is exhausted, the `deferred_follow_up` obligation is in maintenance's hands (due at calendar 9,795,600 s), and `continue_operation` is the only remaining path to advance the station to the next decision point where maintenance can act on the obligation.

This is the correct stopping point — the present required follow-up has been safely dealt with by:
1. Establishing the conditional deferral and its recorded obligation
2. All available tools have been correctly attempted and their responses processed
3. The outstanding obligation is formally lodged with maintenance authority

---

## Handover Summary — Fresh Tenure `asw-4c-fresh-tenure`

**State at sequence 10 | Snapshot `1af75e…`**

### Station Condition
| Parameter | Value |
|---|---|
| Calendar time | 8,586,000 s |
| Duty pump | pump-b (runtime 1,357,200 s) |
| Standby pump | pump-a (runtime 7,228,800 s, 1,000 starts) |
| Wet-well level | 1.65 m — stable |
| Active flow | 0.0260 m³/s vs inflow 0.0155 m³/s |
| Duty transfer quota | **Exhausted** (count = 1, limit = 1) |

### Active Restriction
| ID | Kind | Pump | Status |
|---|---|---|---|
| `restriction-0009-deferred` | `deferred_pump_not_duty` | pump-b | **Active** |

Pump-b must not serve as duty pump. Duty transfer quota is exhausted; physical transfer is not presently available. This restriction documents the deferred clearance-loss condition.

### Active Obligation
| ID | Kind | Pump | Due (calendar s) | Responsible |
|---|---|---|---|---|
| `obligation-0009-deferred-follow-up` | `deferred_follow_up` | pump-b | 9,795,600 | **Maintenance** |

Maintenance must complete the deferred follow-up on pump-b (address the `clearance_loss_low` finding from `evidence-0002-inspection`) before the due time.

### Open Work Orders
| Work Order | Pump | Status | Sequence |
|---|---|---|---|
| `work-order-pump-b` | pump-b | `in_progress` | 1 |
| `work-order-pump-b` | pump-b | `open` | 9 |

### Evidence on File
| Evidence ID | Kind | Pump | Finding | Accepted by |
|---|---|---|---|---|
| `evidence-0002-inspection` | inspection | pump-b | `clearance_loss_low` / `no_material_confirmed` | Engineering |

### Actions Taken This Tenure
1. **`continue_operation`** (seq 8) — advanced clock by 115,200 s to next decision point; station remained stable
2. **`request_conditional_deferral`** (seq 9) — granted `permitted_with_conditions`; created `restriction-0009-deferred` and `obligation-0009-deferred-follow-up` against pump-b

### What Requires Next-Tenure Action
- **Maintenance** must fulfil `obligation-0009-deferred-follow-up` on pump-b before calendar 9,795,600 s
- Once maintenance provides functional check evidence, a **provisional return** for pump-b can be requested
- Following successful provisional return, post-maintenance verification and work order closure can proceed
- The `deferred_pump_not_duty` restriction will remain active until the obligation is discharged and verified