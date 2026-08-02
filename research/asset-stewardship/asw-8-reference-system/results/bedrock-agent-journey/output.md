**Action permitted and applied.** Here is the factual summary:

---

## Station Summary — 2026-01-01 06:00 AEDT

### Pump States
| Pump | Mode | Run-eligible | Assured | Runtime |
|---|---|---|---|---|
| Pump-A | Run-in-service | ✅ | ❌ (restriction active) | 1 hr |
| Pump-B | Isolated for work | ❌ | ❌ | 0 hr |
| Pump-C | Service-available | ✅ | ✅ | 0 hr |

### Service Demand
- **Now → 18:00:** 1 SCU required — met by Pump-C alone (surplus = 0)
- **18:00 → 02:00 Jan 2:** 2 SCU required — **gap of 1 SCU** unless a second pump is assured
- **02:00 Jan 2 onward:** 1 SCU required

### Backlog (both P1, due ~18:00)
| Item | Pump | Work type | Status |
|---|---|---|---|
| `backlog-a-verification-001` | Pump-A | Post-maintenance verification | **In progress** (process created) |
| `backlog-b-clearance-001` | Pump-B | Obstruction clearance | Planned |

### Action Taken
**Post-maintenance verification requested for Pump-A** (`backlog-a-verification-001`). The verification engineer, diagnostic test set, and field-access slot are now reserved. This is the shortest path to lifting Pump-A's run-in restriction and assuring it for outage planning before the 2-SCU demand window opens at 18:00 today. All required authorities accepted the request; the process (`process-post_maintenance_verification-pump-a-1`) is now active.