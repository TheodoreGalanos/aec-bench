# ASW-7 task-local contract register

| Boundary | Producer and consumer | Authority | Persistence | Visibility | Compatibility | Evidence | State |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Rollout group request, child receipt, status, and lineage | Host rollout control and rollout repository | Pump-station task template | Host-private immutable files, with status derived from files | Host-private | Version 1; exact retry; unknown and conflicting content fails closed | Direct, recovery, installed JSON, Harbor | Repository contract, task-local |
| Physical treatment schedule and activation receipts | Host rollout control and rollout repository | Pump-station task template | Host-private immutable files | Host-private | Version 1; closed classes and policies; exact retry | Direct, clock, privacy, installed JSON, Harbor | Repository contract, task-local |
| Physical treatment activation request | Rollout control and durable child world run | Pump-station task template | Existing immutable world-run control-request collection | Host-private | Existing evidence-treatment requests still reload; discriminator selects the stored type | Replay, retry, existing evidence-control regressions | Repository contract, task-local |
| Rollout installed interface request and result | Installed CLI and rollout control | Pump-station task template | Transient transport over durable task records | Host-only | Version 1; strict shapes and closed operations | Installed JSON E2E | Boundary candidate |
| Governed physical change kind | Physical treatment transition and receipt verifier | Pump-station task template | Existing transition receipt | Host-private receipt; actor sees normal consequences only | Additive enum value; no historical value changes | Replay and physical treatment tests | Asset-local |

No type is promoted to the platform `contracts` package. No shared extraction,
new `TrialRecord` field, global registry, or new world-state version is created.
