# DeepSeek AEC plugins

This internal Cordis plugin registers `aec_commit_output` only for an AEC-Bench trial that requires explicit output commitment.

The tool has no arguments. It sends the Harness session, tool-call, and current model-turn identity to the authenticated Unix socket that AEC-Bench owns. It calls `concludeTurn()` only after the AEC authority accepts the exact artifact bytes.

The `tools` plugin registers only the AEC-owned native tool manifest for one run. It forwards calls to an
authenticated Unix socket. The AEC host keeps all tool state and effects. The plugin does not expose shell access,
host controls, verification, or reward.

Neither plugin evaluates or scores the task.

Build and test:

```text
npm ci
npm run build
npm test
```
