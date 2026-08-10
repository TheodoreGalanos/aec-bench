---
name: aec-actor-ledger
description: Invoke AECBench world actions with exact local recording and bounded actor-visible results.
---

# AEC actor ledger

This optional capability keeps exact actor bookkeeping without putting the full
world view into the conversation. It uses the existing `aec_world` interface.
It does not choose actions or add world access.

Use it from IPython:

```python
import aec_actor_ledger

current = await aec_actor_ledger.observe()
matches = aec_actor_ledger.search("pump-a")
backlog = aec_actor_ledger.window("view.ranked_backlog", start=0, limit=5)
outcome = await aec_actor_ledger.invoke(
    action_name,
    arguments,
    expected_result=expected_actor_visible_result,
)
```

`observe()`, `latest()`, `invoke()`, and `entries()` always return compact
results. The complete current observation stays in
`.aec-actor-ledger/state.json`. Exact action attempts stay in
`.aec-actor-ledger/actions.jsonl`.

Use `search(query, path="view", limit=8)` to find actor-visible JSON paths.
Use `window(path, start=0, limit=5)` to inspect a small part of a saved object or
array. Limits are enforced. Nested objects and arrays are described first; call
`window()` again on the more specific path when you need detail.

`invoke()` uses the decision ID from the last recorded observation unless you
supply one. It records applied, rejected, and failed attempts. It also saves the
returned next observation.

You must still:

- choose each action and argument from actor-visible evidence;
- state the expected actor-visible result;
- call `observe()` at the start of each fresh Prime session;
- treat rejections as evidence;
- use bounded `search()` and `window()` calls instead of printing saved files;
- use the raw `aec_world` interface only when this capability cannot express a
  valid need.

Do not infer hidden state, host controls, verifier rules, rewards, or a task
solution from this capability.
