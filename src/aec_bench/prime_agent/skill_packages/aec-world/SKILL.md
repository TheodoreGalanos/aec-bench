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
)
```

The available interface is exactly:

- `await aec_world.capabilities()`
- `await aec_world.observe()`
- `await aec_world.invoke(action_name, arguments)`

The same operations are available as JSON commands when a shell call is more
appropriate:

- `python -m aec_world capabilities`
- `python -m aec_world observe`
- `python -m aec_world invoke --action <name> --arguments-json '<json>'`

Call `capabilities()` before choosing an unfamiliar action. The host binds each
call to the current decision. The client generates request IDs. You do not need
to copy decision IDs, generate request IDs, or maintain action counts.

The root process and all child agents share one actor principal, one action
budget, one action order, and one terminal state. The harness records action
attempts and outcomes.

An error outcome of `unknown` means that the host can have completed the
action even though its response was lost. Observe the current world before
making another decision. Do not repeat the action as if it had failed. The
client does not automatically retry actions. Treat rejected actions as evidence.

Programmatic integrations can explicitly pin `decision_id` (CLI `--decision-id`)
for a stale-decision check, or supply `request_id` (CLI `--request-id`) for an exact
retry. Reuse a request ID only with the same call. These are optional transport
controls, not task submission requirements.

An ended Prime turn does not mean the world is complete. Inspect each action
result's `terminated`, `truncated`, and `reason` fields. After a terminal result,
stop world actions. The shared authority rejects later actions.

You may maintain a concise actor-owned `state.json` in the current workspace when it helps after compaction. Do not search for host state, verifier files, hidden world data, or another control path.
