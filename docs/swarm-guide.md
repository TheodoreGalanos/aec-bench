# Multi-Agent QD Swarm: Practitioner's Guide

A step-by-step guide to running multi-agent evolution experiments with `aec-bench swarm`.

## What This Is

The swarm mode runs N evolution agents in parallel, coordinated through a shared QD (Quality-Diversity) archive. Each agent independently mutates a harness — its system prompt and domain-knowledge skills — while sharing discoveries and learning from each other's failures.

Where single-agent evolution follows one path through the search space, the swarm explores multiple paths simultaneously. The QD archive acts as a coordination mechanism: agents can see which behavioural regions are well-covered and which are unexplored, directing their search toward diversity rather than all converging on the same local optimum.

### How It Relates to Single-Agent Evolution

The swarm builds on top of the existing evolution engine. Each swarm agent runs the same 6-phase cycle (CLASSIFY → ANALYSE → EVOLVE → GATE → VERSION) independently. The difference is what happens between cycles:

| | Single-Agent (`evolve run`) | Multi-Agent (`swarm run`) |
|---|---|---|
| **Agents** | 1 | N (default 4, configurable) |
| **Archive** | Per-workspace, one strategy | Shared across all agents |
| **Failures** | Local graveyard | Shared, BD-indexed graveyard |
| **Lineage** | Git tags only | Structured provenance + cross-agent tracking |
| **Budget** | Cycle count | USD cost ceiling with graceful wind-down |
| **Stagnation** | Engine-level plateau detection | Per-agent pivot heartbeat |

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **QD archive as coordination** | Agents see coverage gaps and target underexplored BD regions — directed diversity, not emergent-only |
| **Shared graveyard indexed by BD region** | Failures near your current exploration region are most relevant — region-filtered queries reduce noise |
| **Archive context as separate message** | Injected after conversation history — system prompt and earlier turns remain cache-eligible |
| **Event-sourced persistence** | JSONL event log enables resume, post-mortem analysis, and dashboard replay without coupling to the run process |
| **Per-eval state saves** | Archive, graveyard, lineage written after every eval — kill-safe, no data loss |
| **Shared budget pool** | Agents draw from one pool, so a fast agent can do more work. Graceful wind-down at 80%/95%/100% thresholds |
| **Pivot heartbeat** | After N consecutive non-improving evals, agent gets explicit "try something different" instruction — prevents wasted budget on plateaus |
| **Mixed models** | Different LLMs explore differently — Opus reasons deeper, Haiku iterates faster. Another diversity axis beyond BD targeting |

### Inspiration

Inspired by [CORAL](https://github.com/Human-Agent-Society/CORAL) (arXiv:2604.01658) — multi-agent evolution via shared filesystem state and heartbeat-driven interrupts. We borrow the shared state and heartbeat patterns but replace CORAL's emergent coordination with QD archive-directed exploration.

---

## Quick Start

### 1. You need an existing evolution workspace

If you don't have one yet:

```bash
aec-bench evolve init workspaces/my-swarm \
  --name "My Swarm Experiment" \
  --adapter rlm
```

Edit `workspaces/my-swarm/prompts/system.md` with your starting prompt.

### 2. Create a swarm config

Create `swarm.yaml`:

```yaml
task:
  workspace: ./workspaces/my-swarm
  task_path: tasks/electrical/voltage-drop    # or any task directory

agents:
  count: 4                                     # number of parallel agents
  default_model: au.anthropic.claude-sonnet-4-6

budget:
  max_cost_usd: 20.0                          # total exploration budget
  eval_budget_usd: 5.0                        # separate eval budget
  wind_down_threshold: 0.8                    # notify at 80%
  final_threshold: 0.95                       # stop new evals at 95%

evaluation:
  timeout: 300                                # seconds per task execution
  backend: local

evolution:
  batch_size: 1                               # tasks per eval cycle
  improvement_threshold: 0.01

heartbeat:
  pivot_after: 5                              # pivot after 5 non-improving evals
```

### 3. Run the swarm

```bash
aec-bench swarm run swarm.yaml
```

You'll see live output:

```
Swarm starting: 4 agents
  Budget: $20.00
  Model: au.anthropic.claude-sonnet-4-6
  Tasks: 3 task instances
  [02:45] agent-1 new archive entry: 0.85 (evo-1)
  evals: 1 | archive: 0% (1/512) | best: 0.85 | budget: 1% | agent-1 → 0.85
  evals: 2 | archive: 0% (1/512) | best: 0.85 | budget: 3% | agent-0 → 0.72
  [05:30] agent-0 new archive entry: 0.72 (evo-1)
  evals: 3 | archive: 0% (2/512) | best: 0.85 | budget: 4% | agent-0 → 0.72
  ...
  [18:20] agent-2 PIVOTING — 5 non-improving evals
  evals: 15 | archive: 1% (7/512) | best: 0.91 | budget: 42% | agent-2 → 0.65
```

### 4. Inspect results

```bash
# List past swarm runs
aec-bench swarm history --state-dir workspaces/my-swarm/_swarm_runs

# Check status of a run (from event log)
aec-bench swarm status <run-id> --state-dir workspaces/my-swarm/_swarm_runs
```

Results are saved in `workspaces/my-swarm/_swarm_runs/`:

```
_swarm_runs/
├── events.jsonl              # full event log (event-sourced state)
├── archive.json              # QD archive snapshot
├── graveyard.json            # shared failure archive
└── lineage.json              # evolutionary provenance records
```

---

## Configuration Reference

### `task`

| Field | Type | Description |
|-------|------|-------------|
| `workspace` | path | Evolution workspace directory (must contain `manifest.yaml` + `prompts/system.md`) |
| `task_path` | path | Task directory — all subdirs containing `instruction.md` are used |

### `agents`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `count` | int | 4 | Number of parallel agents |
| `default_model` | string | required | Model for all agents (Bedrock or Anthropic format) |
| `models` | list | [] | Per-agent model overrides. Index 0 → agent-0, etc. Falls back to `default_model` |
| `specialisation` | string | "homogeneous" | `"homogeneous"` or `"nudged"` (nudged is fast-follow) |
| `nudges` | list | [] | BD region hints per agent (fast-follow) |
| `max_restarts` | int | 3 | Consecutive failures before retiring an agent |

### `budget`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_cost_usd` | float | required | Total exploration budget (shared pool) |
| `eval_budget_usd` | float | required | Separate budget for evaluations |
| `wind_down_threshold` | float | 0.8 | Fraction at which agents get "budget running low" context |
| `final_threshold` | float | 0.95 | Fraction at which no new evals start |
| `pool` | string | "shared" | `"shared"` (all agents draw from one pool) |

### `heartbeat`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `reflect_every` | int | 1 | (fast-follow) Evals between reflection pauses |
| `consolidate_every` | int | 10 | (fast-follow) Global evals between analyst synthesis |
| `pivot_after` | int | 5 | Consecutive non-improving evals before pivot fires |

### `archive`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `n_centroids` | int | 512 | CVT-MAP-Elites archive size (more = finer BD granularity) |

### `evaluation`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `parallel` | bool | true | Run agent evals concurrently |
| `timeout` | int | 300 | Seconds per task execution |
| `backend` | string | "local" | `"local"`, `"modal"`, or `"e2b"` |

### `evolution`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `batch_size` | int | 1 | Tasks per evolution cycle |
| `improvement_threshold` | float | 0.01 | Minimum score improvement to accept a mutation |
| `structural_weight` | float | 0.3 | Weight for structural score in gate decision |

---

## How the Swarm Works

```
                    ┌─────────────────────────┐
                    │     SwarmManager         │
                    │  budget · events · state │
                    └────────┬────────────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
         ┌─────────┐   ┌─────────┐   ┌─────────┐
         │ Agent-0  │   │ Agent-1  │   │ Agent-2  │
         │ (async)  │   │ (async)  │   │ (async)  │
         │ Sonnet   │   │ Opus     │   │ Haiku    │
         └────┬─────┘   └────┬─────┘   └────┬─────┘
              │              │              │
         own workspace  own workspace  own workspace
         own engine     own engine     own engine
         own solver     own solver     own solver
              │              │              │
              └──────────────┼──────────────┘
                             ▼
                    ┌─────────────────────────┐
                    │    Shared State          │
                    │  QD Archive (pyribs)     │
                    │  Shared Graveyard (BD)   │
                    │  Lineage Tracker         │
                    │  Event Log (JSONL)       │
                    └─────────────────────────┘
```

### Per-Agent Loop

Each agent runs independently as an async task:

1. **Solve** — Run the task against the current harness (system prompt + skills)
2. **Classify** — Label agent turns as E/V/D/X bonds, extract trace digest
3. **Analyse** — Compute score, detect anti-patterns, determine mutation scope
4. **Evolve** — LLM proposes mutations based on traces, failures, and history
5. **Gate** — Accept (score improved) or reject (rollback to best-so-far)
6. **Report** — Score + BD + cost sent to manager → archive, graveyard, events, lineage

### Archive-Directed Coordination

Before each cycle, agents receive an **archive context message** — a markdown summary of:

- **Coverage** — which BD regions are occupied, which are empty
- **Top performers** — best entries from any agent
- **Your performance** — recent scores and personal best
- **Relevant failures** — from the shared graveyard, filtered by the agent's current BD focus
- **Pivot instruction** — (when triggered) explicit directive to try fundamentally different approaches

This message is appended as a separate user message after the conversation history, so the system prompt and earlier turns remain cache-eligible.

### Behaviour Descriptors (6D)

The QD archive indexes harnesses by a 6-dimensional behaviour vector:

| Dimension | Range | What it captures |
|-----------|-------|-----------------|
| `token_cost` | 0–500K | Total tokens consumed (efficiency) |
| `verification_depth` | 0–1 | Fraction of turns spent on verification |
| `tool_density` | 0–2 | Tool calls per turn |
| `exploration_ratio` | 0–1 | Fraction of turns spent exploring |
| `deliberation_ratio` | 0–1 | Fraction of turns spent reasoning |
| `reward` | 0–1 | Task score |

Two harnesses with the same reward but different behavioural profiles occupy different archive cells. This preserves diverse strategies that might generalise differently to new tasks.

---

## Budget and Cost

Costs are estimated from Bedrock token usage (Sonnet pricing: ~$3/MTok input, ~$15/MTok output). Each evolution cycle involves:

- **Solver cost** — running the agent against the task (~$0.50–2.00 per eval depending on task complexity and adapter)
- **Evolver cost** — the mutation LLM analysing traces and proposing changes (~$0.10–0.50)

A reasonable starting budget:

| Scenario | Agents | Budget | Expected Evals |
|----------|--------|--------|----------------|
| Quick test | 2 | $5 | ~5–10 |
| Moderate exploration | 4 | $20 | ~20–40 |
| Full diversity search | 4 | $50 | ~50–100 |

### Wind-Down Phases

| Phase | Trigger | Behaviour |
|-------|---------|-----------|
| **Exploring** | 0–80% spent | Normal operation |
| **Winding down** | 80–95% spent | Agents notified to make remaining evals count |
| **Final** | 95–100% spent | No new evals started |
| **Exhausted** | 100% spent | All agents stopped |

---

## Mixed Model Strategies

Different LLMs have different strengths in evolution:

```yaml
agents:
  count: 4
  default_model: au.anthropic.claude-sonnet-4-6
  models:
    - au.anthropic.claude-sonnet-4-6     # balanced
    - au.anthropic.claude-sonnet-4-6     # balanced
    - au.anthropic.claude-opus-4-6       # deeper reasoning, finds subtle patterns
    - au.anthropic.claude-haiku-4-5      # fast iteration, explores more per dollar
```

Opus agents spend more budget per eval but may find insights that faster models miss. Haiku agents iterate quickly, covering more of the BD space per dollar. The shared budget pool handles the cost difference naturally — Opus burns budget faster.

---

## Pivot Heartbeat

When an agent has `pivot_after` (default 5) consecutive evaluations without improving its personal best score, the manager injects a pivot directive into the archive context:

```markdown
### PIVOT — You Are Stuck

You have had 5 consecutive evaluations without improvement.
Your current approach is not working. You MUST try something fundamentally different:

- Study what other agents achieved in different archive regions
- Try a mutation strategy you haven't used before
- Target a completely different BD region
- Consider combining approaches from multiple archive entries

Do NOT continue with small variations of your current approach.
```

After pivoting, there's a 3-eval cooldown before another pivot can fire — the agent gets time to explore the new direction.

---

## Event Log

All state changes are recorded in `events.jsonl` (one JSON object per line):

```jsonl
{"event_type":"swarm_started","timestamp":"...","agent_id":null,"payload":{"run_id":"sw-abc","agent_count":4,"max_cost_usd":20.0},"sequence_number":0}
{"event_type":"agent_spawned","timestamp":"...","agent_id":"agent-0","payload":{"model":"au.anthropic.claude-sonnet-4-6"},"sequence_number":1}
{"event_type":"eval_completed","timestamp":"...","agent_id":"agent-0","payload":{"score":0.85,"cost_usd":1.10,"version":"evo-1","inserted":true},"sequence_number":2}
{"event_type":"archive_updated","timestamp":"...","agent_id":"agent-0","payload":{"version":"evo-1","score":0.85},"sequence_number":3}
{"event_type":"agent_pivoting","timestamp":"...","agent_id":"agent-2","payload":{"consecutive_non_improving":5},"sequence_number":15}
{"event_type":"agent_retired","timestamp":"...","agent_id":"agent-0","payload":{"reason":"budget_exhausted"},"sequence_number":42}
{"event_type":"swarm_completed","timestamp":"...","agent_id":null,"payload":{"total_evals":42,"best_score":0.91,"elapsed_seconds":1200.0},"sequence_number":43}
```

The event log is the source of truth. The archive, graveyard, and lineage JSON files are snapshots that can be reconstructed from the log via `rebuild_state()`.

### Resuming a Run

If a run is interrupted (Ctrl-C, machine restart), the event log preserves all progress:

```bash
aec-bench swarm resume <run-id> --state-dir workspaces/my-swarm/_swarm_runs
```

---

## Lineage Tracking

Every archive insertion creates a `LineageRecord` with:

- **entry_version** — workspace version tag
- **source_agent_id** — which agent produced this
- **parent_version** — what it descended from (if any)
- **cross_agent** — whether it built on another agent's work
- **mutation_type** — what kind of change (skill_add, prompt_edit, etc.)
- **surprise** — flagged when the BD distance between parent and child exceeds a threshold

Lineage data is saved to `lineage.json` and enables post-run analysis of how solutions evolved and spread across agents.

---

## Tips

- **Start with a small budget** ($5) to validate your config and task setup before committing to a longer run.
- **Use harder tasks** for interesting results — tasks where agents score <0.8 show more diversity in the archive. If all agents score 1.0 immediately (like voltage-drop), there's nothing to evolve.
- **Check the event log** if something looks wrong — it captures every state change with timestamps.
- **Budget should account for concurrent agents** — with 4 agents at ~$1/eval, the first round of evals costs ~$4 before any budget check fires.
- **The RLM adapter is expensive** — consider `tool_loop` or `lambda_rlm` adapters for faster, cheaper iteration during development.
- **Mixed models are free diversity** — even without changing anything else, running Opus + Haiku together explores differently than 4x Sonnet.
