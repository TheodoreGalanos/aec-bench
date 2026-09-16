# DeepSeek AEC plugins

This internal Cordis plugin registers `aec_commit_output` only for an AEC-Bench trial that requires explicit output commitment.

The tool has no arguments. It sends the Harness session, tool-call, and current model-turn identity to the authenticated Unix socket that AEC-Bench owns. It calls `concludeTurn()` only after the AEC authority accepts the exact artifact bytes.

The `tools` plugin registers only the AEC-owned native tool manifest for one run. It forwards calls to an
authenticated Unix socket. The AEC host keeps all tool state and effects. The plugin does not expose shell access,
host controls, verification, or reward.

The `subagent-trace` plugin is loaded only when `subagents_enabled` is true.
It uses the public `tools/execute` and `session/created` hooks to append
`aec/subagent-spawn` to the parent session. Async-local call context keeps
concurrent children linked to their own spawning calls. Native DeepSeek
plugins own child execution, depth limits, tool filters, and cancellation.

These plugins do not evaluate or score the task, or modify the installed SDK.

Build and test:

```text
npm ci
npm run build
npm test
```
