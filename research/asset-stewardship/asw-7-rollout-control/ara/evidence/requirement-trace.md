# ASW-7 requirement trace

## ASW-7A

| Requirement | Implementation and evidence |
| --- | --- |
| Validate an immutable origin | `PumpStationRolloutControl.validate_origin` accepts only the current parent snapshot and requires full replay verification. |
| Create one child and a group | `create_child` and `create_group` use the exact complete parent state and parent record versions. |
| Keep future conditions fixed | The request and every receipt bind the fixed-condition policy, future-condition identity and seed, event-schedule identity and the complete parent-profile schedule hash. |
| Bind lineage | Child receipts bind parent and child snapshots, package, model, record versions, information boundary, agent condition and seed, and split group. |
| Preserve split groups | One immutable lineage stores all declared children and one split-group identity. |
| Keep origin selection host-owned | Only the current verified parent snapshot is eligible. Actors receive no origin-selection record. |
| Report status | `group_status` reports requested and created children as `preparing` or `ready`, including after interruption. |
| Recover exactly | The group request and child receipts are immutable. Retry loads an existing exact child or creates only a missing child. |
| Isolate actors | `open_actor_session` opens one child repository. Public view tests reject group, sibling, split, treatment and schedule labels. |
| Direct, local and Harbor paths | Focused E2Es use direct Python, the installed JSON command, and a local Harbor export and runner. |

## ASW-7B

| Requirement | Implementation and evidence |
| --- | --- |
| Closed treatment catalogue | Six classes cover continuation, recurrence, restoration shortfall, maintenance-induced clearance loss, common-cause obstruction, and a clearance-repair alternative. |
| Governed schedule and recovery | `schedule_treatment`, `inspect_treatment`, and `recover_treatment` publish private schedule, activation request, and activation receipt files. |
| Exact treatment binding | Requests bind child snapshot and sequence, parent state, class and version, affected pumps, activation clock, severity band, random stream and seed, visibility, decision right, and idempotent identity. |
| Reject direct latent assignment | The public request has no latent condition value. Only a closed severity band enters the task-owned deterministic mechanism. |
| Bound scope | The control rejects unknown pumps, invalid common-cause sets, old or out-of-envelope clocks, negative seeds, and unsupported policy values. |
| Affected and unaffected sets | Both sets are explicit in schedule and activation receipts. |
| Diverge only at boundary | Control and treated children share one state identity at origin. Only the activation transition changes the treated physical state. |
| No double application | The activation request is stored before child mutation. Retry reloads the same selected world-run transition and receipt. |
| Replay without leakage | The existing independent verifier dispatches the private activation request by stored type. Actor projections contain only normal observations and records. |

The provider-free ASW-7 gate is complete. The separate Bedrock attempt failed
before inference because host credentials were expired. It does not change the
mechanism result.
