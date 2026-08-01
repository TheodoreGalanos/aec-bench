# ASW-5I architecture

```text
direct Python ─┐
installed JSON ├─> task-neutral actor envelope ─> pump-station action schema
local Harbor ──┘                                  └─> durable proposal path

host process ─────> separate control envelope ───> create/open/resume/progress/
                                                   snapshot/verify
```

The shared actor envelope knows identity, binding, action name, JSON arguments,
receipt, and next observation. It does not know a pump-station action field.
The pump-station action adapter validates the task fields and creates the
existing typed proposal. The existing repository remains the only durable
transition path.

The host controller is a different object with a different capability
catalogue and authority check. It returns public run references and verifier
results. It has no raw state setter. The actor never receives this object or
its operation names.

Later stages add only the real controls that they implement. ASW-6A evidence
treatments, ASW-6A-R review cases, ASW-7A branches, and ASW-7B physical
treatments are absent in ASW-5I and fail as unavailable capabilities.
