# Agent-Provider Compatibility Matrix

## Agent Types

| Agent Type | Providers | Model Patterns | Tool Support | Multimodal |
|------------|-----------|---------------|--------------|------------|
| `tool_loop` | anthropic, azure_openai, bedrock, together, PydanticAI auto | `claude-*`, `gpt-*`, `o1-*`, `o3-*`, `o4-*`, Bedrock-prefixed IDs, `together:*`, provider-native names | Yes (bash tool loop) | No |
| `pydantic_ai` | Same as `tool_loop` | Same as `tool_loop` | Yes (compatibility alias for Pydantic-backed tool loop) | No |
| `rlm` | anthropic, azure_openai, bedrock, together, PydanticAI auto | Same as `tool_loop` | RLM REPL/scaffolded reasoning path | No |
| `lambda-rlm` | Same as `rlm` | Same as `rlm` | Template-driven RLM report path | No |
| `lambda_rlm` | Same as `lambda-rlm` | Same as `lambda-rlm` | Compatibility alias for `lambda-rlm` | No |
| `direct` | anthropic, azure_openai, together | `claude-*`, `gpt-*`, `o1-*`, `o3-*`, `o4-*`, `together:*` | No | No |

## Provider Inference from Model Name

The provider is automatically inferred from the model name:

- `claude-*` → anthropic (uses `ANTHROPIC_API_KEY`)
- `gpt-*`, `o1-*`, `o3-*`, `o4-*` → azure_openai (uses `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT`)
- `together:*` → together (uses `TOGETHER_API_KEY`; prefix is stripped before the API request)
- Unknown deployment names route through Azure when `AZURE_OPENAI_ENDPOINT` + `AZURE_OPENAI_API_KEY` are set for PydanticAI-backed agents
- Bedrock-prefixed names such as `us.anthropic.*`, `amazon.*`, `meta.llama*`, `mistral.*`, `cohere.*`, and `ai21.*` route through Bedrock for PydanticAI-backed agents

Override with `client.kind` if the default inference is wrong (e.g., using OpenAI directly instead of Azure).

## When to Use Each Agent

### tool_loop (default choice)

Multi-turn agent with tool use. The agent gets a bash tool (always) plus any tools declared in the task's `[[environment.tools]]`. Each turn: call the LLM, execute tool calls, feed results back. Proven across 500+ trials.

**Use when:** most benchmark tasks. This is the workhorse.

### pydantic_ai

Compatibility alias for the PydanticAI-backed tool loop. It uses the same runtime as `tool_loop`, but keeps older manifests that name `pydantic_ai` working.

**Use when:** older configs use `adapter: pydantic_ai`, or you want the public adapter name to signal the PydanticAI provider-routing path.

Use `adapter: pydantic_ai` directly in manifests:

```yaml
agents:
  - name: pydantic-sonnet
    adapter: pydantic_ai
    model: claude-sonnet-4-20250514
```

### rlm

RLM reasoning adapter for tasks that benefit from scaffolded reasoning, scratchpad state, and optional `rlm.toml` configuration.

**Use when:** a task or experiment is explicitly designed for the RLM adapter.

### lambda-rlm

Template-driven RLM report adapter. Looks for `lambda-rlm.toml`, falling back to `rlm.toml`, plus the configured report template.

**Use when:** the workspace contains a report template and λ-RLM configuration.

### direct

Single-turn agent. Sends the instruction to the LLM once, gets a response, done. No tool use, no multi-turn conversation.

**Use when:** single-turn tasks that don't need tools. Rare in aec-bench since most tasks benefit from tool use.

### script (legacy)

Older single-turn agent variant. Prefer `direct` for new experiments.

## Common Model Names

### Anthropic
- `claude-sonnet-4-20250514` — best balance of capability and cost
- `claude-haiku-4-5-20251001` — faster, cheaper, good for easy tasks
- `claude-opus-4-20250514` — most capable, expensive

### Azure OpenAI / OpenAI
- `gpt-4o` — strong general-purpose
- `gpt-4o-mini` — faster, cheaper
- `o3` — reasoning-focused
- `o4-mini` — compact reasoning

### Together AI
- `together:Qwen/Qwen3.7-Max` — OpenAI-compatible Together model route
