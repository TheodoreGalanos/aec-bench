---
name: hydraulic-review
description: Review the active stormwater hydraulic checkpoint through its scoped lifecycle interface.
---

# Hydraulic review lifecycle

Use only the scoped `hydraulic_review` interface for lifecycle evidence and operations.

```python
import hydraulic_review

capabilities = await hydraulic_review.capabilities()
checkpoint = await hydraulic_review.observe()
files = await hydraulic_review.list_files(".")
instruction = await hydraulic_review.read_file("instruction.md")
result = await hydraulic_review.execute_operation(
    "hydrology.design-10yr",
    "Calculate the declared design hydrology.",
)
```

The available calls are exactly:

- `await hydraulic_review.capabilities()`
- `await hydraulic_review.observe()`
- `await hydraulic_review.list_files(path=".")`
- `await hydraulic_review.read_file(path)`
- `await hydraulic_review.execute_operation(operation_id, reason)`
- `await hydraulic_review.offer_submission(submission)`

Read the active instruction and operation catalogue before you act. The host binds the current source and checkpoint. Read each
returned relative artifact before you make a decision. Prior submissions are evidence and are not editable.

`offer_submission` proposes the current checkpoint result. It does not advance the lifecycle. End the Prime turn
after the endpoint accepts the complete proposal. The host validates and submits it only after the Prime process
closes cleanly.

Build the complete checkpoint-specific submission before you call `offer_submission`. The host supplies the checkpoint ID.
Use readable source revisions and analysis checkpoint names for evidence choices; do not supply hashes or run IDs.

Do not search for package paths, run paths, hidden evidence, host controls, verifier data, or evaluation data.
