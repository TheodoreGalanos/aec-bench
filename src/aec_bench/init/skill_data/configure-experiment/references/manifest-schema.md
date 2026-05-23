# ExperimentManifest Schema Reference

The experiment config YAML maps directly to the `ExperimentManifest` Pydantic contract. The contract uses strict mode (`extra="forbid"`) — only the fields listed here are allowed. Any typo or extra key causes a validation error.

## Top-Level Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `experiment_id` | string | Yes | — | Unique identifier. Used as the ledger directory name. |
| `name` | string | Yes | — | Human-readable name shown in reports and TUI. |
| `description` | string | No | null | Optional longer description of the experiment's purpose. |
| `repetitions` | positive int | No | 1 | How many times each task-agent combination runs. |

## tasks (TaskSelector)

Controls which tasks are included in the experiment.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `include_patterns` | list[string] | No | [] | Glob patterns matching task paths (e.g., `electrical/*`, `ground/terzaghi-*`). |
| `exclude_patterns` | list[string] | No | [] | Inverse patterns — tasks matching these are removed. |
| `domains` | list[string] | No | [] | Discipline filter. Values come from the task directory structure (e.g., `civil`, `electrical`, `ground`, `mechanical`, `structural`). Empty means all domains. |
| `difficulties` | list[string] | No | [] | Difficulty filter: `easy`, `medium`, `hard`. Empty means all difficulties. |

**Note:** The contract also has a `lifecycle_filter` field, but it is not currently consumed by the scheduler. Do not include it in generated YAML.

## agents (list of AgentConfig)

At least one agent is required. Each agent specifies how to run tasks.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | Yes | — | Identifier for this agent in results (e.g., `tool_loop-sonnet`). |
| `adapter` | string | Yes | — | Agent type: `tool_loop`, `pydantic_ai`, `direct`. |
| `model` | string | Yes | — | Full model name (e.g., `claude-sonnet-4-20250514`, `gpt-4o`). |
| `client` | object | No | null | Provider override. Has `kind` (string) and `settings` (dict). |
| `parameters` | dict | No | {} | Agent-specific config (e.g., `max_turns: 20`, `command_timeout: 180`). |
| `system_prompt_file` | string | No | null | Path to custom system prompt file, relative to the config file's directory. |

### Client Config

Only needed when the default provider inference is wrong (e.g., using OpenAI directly instead of Azure):

```yaml
client:
  kind: openai_chat
  settings:
    api_base: https://api.openai.com/v1
```

## compute (ComputeConfig)

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `backend` | string | Yes | — | Execution backend. `modal` = serverless via Modal, `docker` = local Docker. The value is passed as `environment.type` in the Harbor config. |
| `resource_limits` | dict | No | {} | Backend-specific limits. Common key: `n_concurrent_trials` (int). |
| `timeout_override` | positive int | No | null | Global per-trial timeout in seconds. Overrides the task's own timeout. |
