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

Call `capabilities()` before choosing an unfamiliar action. Use the newest `decision_id` from `observe()` or an action result. After a stale-decision error, observe again. Reusing the same `request_id` with the exact same call is an idempotent retry; never reuse it for different content. Treat rejected actions as evidence and do not silently retry them.

An ended Prime turn does not mean the world is complete. Inspect each action result's `terminated`, `truncated`, and `reason` fields.

You may maintain a concise actor-owned `state.json` in the current workspace when it helps after compaction. Do not search for host state, verifier files, hidden world data, or another control path.
