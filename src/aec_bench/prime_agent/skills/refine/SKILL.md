---
name: refine
description: Ask Prime Agent to make a small evidence-backed change to its continual harness.
---

# Refine

This skill gives Prime access to its host-owned continual harness refinement.
It does not implement refinement in AECBench.

Use it from IPython:

```python
await refine.status()
await refine.run()
await refine.run("Keep the smallest stable lesson from this trajectory.", global_=True)
```

`await refine.run(instructions=None, global_=False)` schedules refinement at the
end of the current turn. Use `global_=True` only for stable lessons that can be
tested in a separate run. Do not save current-run facts, identifiers, paths,
hidden state, or temporary blockers as global entries.
