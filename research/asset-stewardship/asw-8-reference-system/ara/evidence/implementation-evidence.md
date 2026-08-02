# ABOUTME: Records focused implementation evidence for the ASW-8 reference system.
# ABOUTME: Separates provider-free mechanism proof from the one bounded model journey.

# ASW-8 implementation evidence

Date: 2026-08-02

## Result

The provider-free ASW-8 gate passes. The implementation now supports the
declared three-pump reference system, shared work resources, durable generated
work, temporal evidence, replay, direct and Harbor execution, evaluation, and
ASW-7 child isolation.

The separately approved real-model journey also passes as a bounded behaviour
and usability check. It does not change the provider-free result.

## Certified station data

The promoted package is `AU-NSW-LH-SYN-SPS-v2`.

| Record | Content identity |
| --- | --- |
| Package | `79eac8f916a15fe7463eba5faf44edeb8776ce79dc3fe7bd8b2cb1574988b1c1` |
| Physical member | `e3ef3a2f391635d0f97710b6d988acdf05ece22503c0e82d83afc8522f7d9a94` |
| Generation | `afac5355a2866f20215846ea0140f08f6581a80312b72c464329ba7b6e7dc840` |
| Independent certification receipt | `60f65bf7c0baed2db54b4b8116f27c224da6dd221197398a0580250b4a422a91` |

The independent certifier accepted the exact promoted candidate. A direct
directory comparison between the generated candidate and promoted package had
no difference.

## Reference-system binding

The registered RS1 descriptor binds these records:

| Boundary | Bound value |
| --- | --- |
| Descriptor | `pump-station-reference-system.asw-8-rs1.v1` |
| Station-data profile | `AU-NSW-LH-SYN-SPS-v2` |
| Opening-state specification | `pump-station-asw-8-rs1-initial-state.v1` |
| Opening-state SHA-256 | `1c3f82766c0dc03f31048aa5e12388f7e173bf907606c21f5b150914f874066a` |
| Event schedule | `pump-station-asw-8-rs1-event-schedule.v1` |
| Event-schedule SHA-256 | `3188afedbb8da98ad2a042dacb2a4094f2218cfd6482ae7cf98e16e74457af71` |
| Temporal template | `pump-station-asw-8-rs1-temporal-template.v1` |
| Temporal-template SHA-256 | `daadc4183abd93b82f478c8af839a0590ed7ddd8dd941d5cce25a879582acd2d` |
| State, snapshot, and receipt | v4 |
| Actor interface and projection | interface v2, projection v5 |
| World manifest | v2 |
| Evaluation and verification | evaluation v2, verification report v2 |

The loader rejects missing, changed, cross-profile, and caller-overridden
records before a run starts.

## Focused verification

The ASW-8-only gate ran all files named `test_asw_8_*.py` under the pump-station
test folder.

```text
58 passed in 71.03s
```

The gate contains unit, integration, and end-to-end cases. It includes the
complete Day 0 to Day 2 journey, installed JSON execution, local Harbor,
TrialRecord import, evaluation, temporal evidence, rollout control, and replay.

Six narrow historical checks then verified the affected older contracts:

```text
6 passed in 0.97s
```

These checks cover v1 and v2 state bytes, v3 state and actor-view bytes, ASW-5
migration and recovery, and ASW-7 parent and child isolation.

After the version-selected decoder change, three affected v4 persistence and
transport checks were repeated:

```text
3 passed in 32.74s
```

They cover repository resume, the installed reference journey, and strict
local Harbor TrialRecord import. The full repository suite was not run.

Scoped source checks also passed for the complete ASW-8 implementation surface:

```text
Ruff format: 46 files already formatted
Ruff lint: passed
MyPy: no issues in 65 source files
```

## Exit-gate evidence

| Exit statement | Direct evidence |
| --- | --- |
| The v2 station package is independently promoted and v1 stays stable | Package, generator, certifier, promotion, strict loader, v1 byte tests |
| One or two pumps serve declared demand with separate exposure | Coupled-physics and reference-journey tests |
| Outage admission uses assured capacity and visible schedules | Work-system and operational-boundary tests, including actor-equivalent latent states |
| Shared people, equipment, access, and stock cannot be over-allocated | Resource-pool, window, suspension, cancellation, and same-time withdrawal tests |
| Generated work has one durable source and identity | WG-01 to WG-09 and changed-content rejection tests |
| Work and liabilities continue through time and branches | Persistence, crash-recovery, handover, suspension, resume, cancellation, and rollout tests |
| Replay reconstructs state and the actor boundary | Repository replay, installed interface, direct and Harbor verification tests |
| Direct, Harbor, evaluation, and TrialRecord import agree | Semantic-outcome parity and strict import tests |
| Historical package, state, view, and replay bytes stay unchanged | Six focused v1-v3, ASW-5, and ASW-7 compatibility checks |
| Duty, resources, work, and liabilities balance | Four conservation sections, mismatch injection, and complete-journey tests |

## Architecture result

`PumpStationStewardshipState` remains the one durable state-envelope class. Its
generic record types select the legacy physical, resource, process, and
reservation records for v1-v3, and the coupled records for v4. The decoder
selects those concrete types from the record profile before it decodes fields.

This keeps old source types and bytes stable. It also prevents v4 unions from
entering legacy code. ASW-8 keeps task-owned coupled records and uses the
existing durable repository boundary. It does not add shared extraction or
broad phase-name cleanup.

Every world-changing actor action now stores its typed proposal with the exact
decision-time view and information-set binding. Evaluation reports actor
proposal integrity separately from host-control integrity.

## Bounded model evidence

The approved Bedrock run completed in three of four turns. It used 14,154 input
tokens, 1,464 output tokens, 7,362 cache-read tokens, and 6,787 cache-write
tokens. The model used the named projection-v5 pump records and submitted one
valid, natural-language, view-bound Pump A verification request. Replay,
actor-proposal integrity, host-control integrity, and all conservation sections
passed. See `agent-journey-evidence.md` for the bounded interpretation.
