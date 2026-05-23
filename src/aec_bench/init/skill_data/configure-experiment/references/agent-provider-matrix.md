# Agent-Provider Compatibility Matrix

## Agent Types

| Agent Type | Providers | Model Patterns | Tool Support | Multimodal |
|------------|-----------|---------------|--------------|------------|
| `tool_loop` | anthropic, azure_openai | `claude-*`, `gpt-*`, `o1-*`, `o3-*`, `o4-*` | Yes (bash + declared tools) | No |
| `pydantic_ai` | anthropic, openai, azure_openai, bedrock, gemini | All above + `gemini-*` | Yes (bash + declared tools + image return) | Yes |
| `direct` | anthropic, azure_openai | Same as tool_loop | No | No |

## Provider Inference from Model Name

The provider is automatically inferred from the model name:

- `claude-*` → anthropic (uses `ANTHROPIC_API_KEY`)
- `gpt-*`, `o1-*`, `o3-*`, `o4-*` → azure_openai (uses `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT`)
- `gemini-*` → gemini (pydantic_ai only)

Override with `client.kind` if the default inference is wrong (e.g., using OpenAI directly instead of Azure).

## When to Use Each Agent

### tool_loop (default choice)

Multi-turn agent with tool use. The agent gets a bash tool (always) plus any tools declared in the task's `[[environment.tools]]`. Each turn: call the LLM, execute tool calls, feed results back. Proven across 500+ trials.

**Use when:** most benchmark tasks. This is the workhorse.

### pydantic_ai

Uses the PydanticAI framework for the agent loop. Supports all providers (not just Anthropic and Azure OpenAI). Native multimodal support via `ToolReturn` + `BinaryContent` for image-returning tools.

**Use when:** tasks have image-returning tools (`returns_image = true`), or you need providers beyond Anthropic/Azure OpenAI (e.g., Gemini, Bedrock).

**Important:** `pydantic_ai` is not in the default Harbor dispatch table. You must provide a `harbor_import_path` in the agent parameters pointing to your PydanticAI agent class:

```yaml
agents:
  - name: pydantic-sonnet
    adapter: pydantic_ai
    model: claude-sonnet-4-20250514
    parameters:
      harbor_import_path: "agents.pydantic_ai_anthropic:PydanticAIAnthropicAgent"
```

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

### Google (pydantic_ai only)
- `gemini-2.5-pro` — multimodal, strong reasoning
