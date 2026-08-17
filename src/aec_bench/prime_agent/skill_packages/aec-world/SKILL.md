---
name: aec-world
description: Use the scoped AECBench actor interface for the current interactive world episode.
---

# AEC world actor

The task objective and completion rules are in the initial prompt. Use only this interface to act in the current world.

```python
import aec_world

catalogue = await aec_world.capabilities()
observation = await aec_world.observe()
result = await aec_world.invoke(
    "inspect_asset",
    {"asset_id": "asset-1"},
    decision_id=observation["decision_id"],
)
```

The available interface is exactly:

- `await aec_world.capabilities()`
- `await aec_world.observe()`
- `await aec_world.invoke(action_name, arguments, decision_id=..., request_id=...)`

The same operations are available as JSON commands when a shell call is more
appropriate:

- `python -m aec_world capabilities`
- `python -m aec_world observe`
- `python -m aec_world invoke --action <name> --decision-id <id> --arguments-json '<json>'`

Call `capabilities()` before choosing an unfamiliar action. Use the newest
`decision_id` from `observe()` or an action result. After a stale-decision
error, observe again. The `decision_id` is opaque. Do not invent, edit, or
reuse an older value.

The root process and all child agents share one actor principal, one action
budget, one request-ID namespace, one action order, and one terminal state.
Choose globally unique request IDs when you supply them. Reusing the same
`request_id` with the exact same call is an idempotent retry. Never reuse it
for different content.

An error outcome of `unknown` means that the host can have completed the
action even though its response was lost. Do not issue the action under a new
request ID. If you must resolve it, retry the exact same call and request ID or
observe the current world. The client does not automatically retry actions.
Treat all rejected actions as evidence.

An ended Prime turn does not mean the world is complete. Inspect each action
result's `terminated`, `truncated`, and `reason` fields. After a terminal result,
stop world actions. The shared authority rejects later actions.

You may maintain a concise actor-owned `state.json` in the current workspace when it helps after compaction. Do not search for host state, verifier files, hidden world data, or another control path.
