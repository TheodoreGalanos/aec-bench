# Evolution Engine: Practitioner's Guide

A step-by-step guide to running automated agent improvement experiments with aec-bench.

## What This Is

The evolution engine automatically improves an agent's scaffolding — its system prompt, domain-knowledge skills, and behavioural patterns — by running tasks, analysing failures, and proposing targeted mutations. It does not change the underlying LLM; it optimises what the LLM is told to do.

The engine combines ideas from three research directions:

- **Quality-Diversity (MAP-Elites)** — optionally maintains a diverse archive of harnesses indexed by behavioural descriptors, not just the single best. Different tasks may need different agent strategies.
- **Hill-Climbing** — the default mode: always mutate from the best-so-far workspace. Simple, fast, and effective for single-task-type evolution.
- **LLM-as-Optimiser (Meta-Harness, AlphaEvolve)** — uses an LLM agent as the mutation operator, browsing execution traces and prior results to propose evidence-based changes.
- **Agentic Bonds** — classifies agent behaviour into Exploration, Deliberation, Execution, and Verification patterns to assess process quality alongside task reward.

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Two strategy modes** (hill_climb / qd) | Hill-climb is fast and simple for single-task-type evolution; QD archives diverse strategies for multi-discipline experiments |
| **Two-phase evolver** (investigate → propose) | Separating diagnosis from action prevents the LLM from burning tool-call budget without proposing |
| **Externalised policy** (`program.md`) | Evolution strategy is a readable document, not embedded in code — customisable per workspace |
| **Failure taxonomy** | 11 structured categories guide the evolver's diagnosis — from `task_misunderstanding` to `overfitting` |
| **Masked feedback** | Error directions ("too high", "too low") shown to evolver, not exact values — prevents overfitting to test answers |
| **Graduated scope** | SKIP/MINIMAL/TARGETED/COMPREHENSIVE constrains mutation aggressiveness based on current performance |
| **Enriched graveyard** | Rejected mutations store field failures, detected patterns, mutation actions, and investigation summary — the evolver queries these via `read_graveyard()` to learn from past failures |
| **Performance as diversity** (QD mode) | Reward is a BD axis, not just the quality metric — the archive keeps "promising but unfinished" strategies alive |
| **Per-workspace archive** (QD mode) | Each workspace has its own archive; different runs accumulate diversity |

### References

- Mouret & Clune (2015). "Illuminating search spaces by mapping elites." [MAP-Elites]
- Lee et al. (2026). "Meta-Harness: End-to-End Optimization of Model Harnesses." [Meta-Harness]
- Lehman et al. (2022). "Evolution through Large Models." [ELM]
- Cully (2021). "Multi-Emitter MAP-Elites." [pyribs]
- kevinrgu (2026). "AutoAgent." [program.md pattern, failure taxonomy, overfitting test]

---

## Quick Start (5 minutes)

### 1. Initialise a workspace

```bash
aec-bench evolve init workspaces/my-experiment \
  --name "My Evolution Experiment" \
  --adapter tool_loop
```

This creates:
```
workspaces/my-experiment/
├── manifest.yaml          # workspace metadata
├── prompts/
│   └── system.md          # agent's system prompt (you edit this)
└── skills/                # domain-knowledge skills (empty to start)
```

### 2. Write your system prompt

Edit `workspaces/my-experiment/prompts/system.md` with domain-specific instructions for your agent. This is the starting point the evolver will improve.

### 2b. (Optional) Customise the evolution policy

Copy and edit the default program to add domain-specific rules:

```bash
cp src/aec_bench/evolution/default_program.md workspaces/my-experiment/program.md
# Edit to add domain-specific diagnosis rules, mutation constraints, etc.
```

If you skip this step, the default program is used automatically.

### 3. Create an evolution config

Create `workspaces/my-experiment/evolution.yaml`:

```yaml
workspace_path: workspaces/my-experiment

models:
  classifier: env:AWS_HAIKU_MODEL_ID      # behavioural classifier
  evolver: env:AWS_SONNET_MODEL_ID        # mutation proposer

solver:
  name: my-solver
  adapter: tool_loop                       # or rlm
  model: env:AWS_HAIKU_MODEL_ID           # the agent being evolved
  client:
    kind: bedrock

generate:
  template: "voltage-drop"                 # template to generate tasks from
  count: 6
  seed: 42
  difficulties: ["easy", "medium", "hard"]

tasks:
  domains: [electrical]

strategy: hill_climb                       # or "qd" for MAP-Elites diversity
backend: local
batch_size: 3
max_cycles: 10
improvement_threshold: 0.01
stagnation_window: 5
```

### 4. Run the evolution

```bash
aec-bench evolve run \
  -c workspaces/my-experiment/evolution.yaml \
  --tasks-root tasks/
```

Add `-v` for verbose logging.

### 5. Inspect results

```bash
# View evolution timeline
aec-bench evolve history workspaces/my-experiment

# View the HTML report
open workspaces/my-experiment/evolution-report.html

# Start Web UI for archive visualisation.
# Packaged installs need: pip install "aec-bench[webui]"
aec-bench web --workspaces-root workspaces/
# Navigate to /evolution
```

---

## Anatomy of an Evolution Cycle

Each cycle runs through this pipeline. Steps 0-5 are identical regardless of strategy mode. Steps 6-7 are strategy-dependent.

```
┌──────────────────────────────────────────────────────────┐
│  0. APPLY PARENT (if strategy selected one last cycle)   │
│     Restore workspace to the selected parent's state     │
├──────────────────────────────────────────────────────────┤
│  1. SOLVE                                                │
│     Run batch_size tasks against the current workspace   │
├──────────────────────────────────────────────────────────┤
│  2. CLASSIFY                                             │
│     Label each agent turn as E/V/D/X (bond type)        │
│     Extract tool calls, errors, reasoning from traces    │
├──────────────────────────────────────────────────────────┤
│  3. ANALYSE                                              │
│     Compute scores, detect anti-patterns, set scope      │
├──────────────────────────────────────────────────────────┤
│  4. EVOLVE (two-phase)                                   │
│     Phase A: Investigate — agent browses traces, skills, │
│              history, and graveyard with tools            │
│              (read_trace, field_detail, read_graveyard,   │
│              read_skill, read_prompt, list_history, etc.) │
│     Phase B: Propose — structured mutations from findings│
├──────────────────────────────────────────────────────────┤
│  5. GATE                                                 │
│     Accept (score improved), Reject (stagnated),         │
│     or Skip (already excellent)                          │
│     Rejected mutations → enriched graveyard              │
├──────────────────────────────────────────────────────────┤
│  6. RECORD (strategy-dependent)                          │
│     hill_climb: Track best-so-far version and score      │
│     qd: Extract BDs, insert into MAP-Elites archive,    │
│         update UCB1 bandits                              │
├──────────────────────────────────────────────────────────┤
│  7. SELECT (strategy-dependent)                          │
│     hill_climb: Always pick best-so-far as parent        │
│     qd: UCB1 shortlist → Archive explorer agent → Parent │
└──────────────────────────────────────────────────────────┘
```

---

## Choosing a Strategy

| Scenario | Strategy | Why |
|----------|----------|-----|
| Single task type (e.g., voltage-drop only) | `hill_climb` | Archive stays at 1 cell anyway; no overhead |
| Quick iteration during development | `hill_climb` | Faster (no archive explorer LLM call per cycle) |
| Multi-discipline experiments | `qd` | Archive captures diverse strategies per discipline |
| Exploring different solving approaches | `qd` | MAP-Elites preserves promising alternatives |
| First time running evolution | `hill_climb` | Simpler to debug and understand |

**hill_climb** (default) — always mutates from the best-scoring workspace. No archive, no BD extraction, no explorer agent. One fewer LLM call per cycle. Best for focused, single-task-type improvement.

**qd** — MAP-Elites archive with UCB1 cell selection, strategy bandit, and archive explorer agent. Maintains diverse workspace variants indexed by 6 behavioural dimensions. Best for multi-discipline experiments where different tasks benefit from different strategies.

Both modes use the same engine (classify → analyse → evolve → gate), the same program.md, the same graveyard, and the same evolver toolset.

---

## Configuration Reference

### Config Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `workspace_path` | string | required | Path to the evolution workspace |
| `models.classifier` | string | required | Model for behavioural classification |
| `models.evolver` | string | required | Model for mutation proposals |
| `solver.adapter` | string | `"rlm"` | Agent adapter: `tool_loop` or `rlm` |
| `solver.model` | string | required | Model the agent under evolution uses |
| `solver.client.kind` | string | `"bedrock"` | API provider for the solver |
| `generate.template` | string | — | Template name for task generation |
| `generate.count` | int | 5 | Number of task instances to generate |
| `generate.seed` | int | 42 | Random seed for reproducibility |
| `generate.difficulties` | list | `["easy","medium"]` | Difficulty levels to include |
| `tasks.domains` | list | required | Engineering disciplines to filter tasks |
| `strategy` | string | `"hill_climb"` | Selection mode: `"hill_climb"` or `"qd"` |
| `backend` | string | `"local"` | Execution backend |
| `batch_size` | int | 10 | Tasks per cycle |
| `max_cycles` | int | 20 | Maximum evolution iterations |
| `improvement_threshold` | float | 0.02 | Minimum improvement to accept a mutation |
| `stagnation_window` | int | 5 | Flat cycles before declaring convergence |
| `structural_weight` | float | 0.3 | Weight of behavioural quality vs reward (0 = reward only) |
| `timeout` | int | 1800 | Seconds per task before timeout |

### Environment Variables

Model IDs support `env:VAR_NAME` syntax. Common variables:

```bash
export AWS_HAIKU_MODEL_ID="au.anthropic.claude-haiku-4-5-20251001-v1:0"
export AWS_SONNET_MODEL_ID="au.anthropic.claude-sonnet-4-6"
export AWS_REGION="ap-southeast-2"
```

---

## Workspace Structure

```
workspaces/my-experiment/
├── manifest.yaml              # name, adapter, evolvable layers, skill budget
├── evolution.yaml             # evolution config (you create this)
├── program.md                 # evolution policy (optional — overrides default)
├── prompts/
│   └── system.md              # the agent's system prompt (evolved)
├── skills/                    # domain-knowledge skills (evolved)
│   ├── verify-units/
│   │   └── SKILL.md
│   └── check-formula/
│       └── SKILL.md
├── evolution-report.html      # generated after each run
├── archive.json               # MAP-Elites archive (QD mode only)
├── graveyard.json             # failed mutations with diagnostic data
└── .git/                      # version history (evo-YYYYMMDD-HHMM-N tags)
```

### Skill Format

Skills use YAML frontmatter + markdown body:

```markdown
---
name: verify-units
description: Check that all intermediate values include correct SI units
discipline: electrical
---
## Unit Verification Checklist

Before submitting your answer, verify:
- Current in Amperes (A)
- Voltage drop in Volts (V)
- Cable resistance in mV/A/m
- Length in metres (m), one-way route length
```

---

## The Evolution Program (`program.md`)

The evolution policy — how the evolver investigates, diagnoses, and proposes mutations — is defined in a standalone markdown document. This makes the strategy transparent, tweakable, and customisable per workspace.

**Default program:** Bundled at `src/aec_bench/evolution/default_program.md`. Contains the investigation protocol, failure taxonomy, mutation constraints, selection protocol, and anti-pattern reference.

**Custom program:** Place a `program.md` in your workspace root to override. The investigator agent loads it as its system prompt. This lets you:
- Add domain-specific diagnosis rules ("for voltage-drop tasks, always check Vc_r table lookup")
- Change mutation constraints ("prefer adding tools over modifying prompts")
- Adjust the investigation budget ("use up to 12 tool calls")
- Add custom failure categories specific to your task domain

### Failure Taxonomy

The program includes 11 structured failure categories. During investigation, the evolver classifies each failure to guide its mutation strategy:

| Category | Description | Typical Fix |
|----------|-------------|-------------|
| `task_misunderstanding` | Agent misinterprets the task | Improve task parsing in prompt |
| `missing_domain_knowledge` | Lacks formulas or standards | Add/improve a domain skill |
| `missing_tool_use` | Tool available but not used | Add explicit instruction to use it |
| `wrong_tool_use` | Tool used with wrong arguments | Add usage examples to skill |
| `weak_information_gathering` | Acts before reading context | Add exploration step to prompt |
| `bad_execution_strategy` | Fundamentally wrong approach | Restructure the prompt workflow |
| `missing_verification` | No self-checking | Add verification bond to prompt |
| `arithmetic_error` | Steps correct, numbers wrong | Add "show your working" requirement |
| `environment_issue` | Infra problem (not fixable) | Flag for task author |
| `silent_failure` | Wrong values, no diagnosis | Add intermediate logging |
| `overfitting` | Helps one task, not general | Revert. Apply the overfitting test. |

The **overfitting test**: before proposing any change, the evolver asks *"If the failing task disappeared from the benchmark, would this change still be worthwhile?"* If no, the change is task-specific and should be rejected in favour of a more general fix.

---

## The QD Archive (QD mode only)

When `strategy: qd` is set, the archive maintains diverse high-performing workspaces indexed by 6 behavioural dimensions. In hill-climb mode, no archive is created.

| Dimension | Source | Range | What it captures |
|-----------|--------|-------|-----------------|
| Token cost | CostRecord | 0 – 500K | Cheap vs expensive agents |
| Verification depth | Bond sequence (V/total) | 0 – 1 | How much the agent self-checks |
| Tool density | Calls / turns | 0 – 2 | Tool-heavy vs reasoning-heavy |
| Exploration ratio | Bond sequence (X/total) | 0 – 1 | How much the agent explores first |
| Deliberation ratio | Bond sequence (D/total) | 0 – 1 | How much the agent plans/reasons |
| Reward | Evaluation | 0 – 1 | Performance (as a diversity axis) |

Treating reward as a behaviour dimension (not just the quality metric) keeps "promising but unfinished" strategies alive for cross-pollination.

The archive uses **CVT-MAP-Elites** with 200 Voronoi centroids in this 6D space. Each cell holds the best workspace snapshot for its behavioural region.

### Viewing the Archive

```bash
# Web UI
# Packaged installs need: pip install "aec-bench[webui]"
aec-bench web --workspaces-root workspaces/
# Navigate to /evolution/{workspace}/archive

# API
curl http://localhost:8000/api/evolution/my-experiment/archive
```

The API returns a 2D PCA projection of the archive for scatter plot visualisation, plus a summary with coverage, best/mean reward, and the disciplines and task IDs represented.

---

## Selection Pipeline (QD mode only)

In QD mode, when the archive has 2+ entries, an intelligent selection pipeline chooses the parent for the next cycle. In hill-climb mode, the parent is always the best-so-far workspace — no archive or agent selection is needed.

1. **UCB1 Bandit** shortlists 5 candidate cells, balancing cells that produce good offspring (exploit) vs cells rarely tried (explore).

2. **Archive Explorer Agent** browses the shortlist using tools:
   - `browse_archive` — list entries sorted by reward, coverage, or diversity
   - `compare_cells` — diff two harnesses (BDs, prompts, skills)
   - `inspect_cell` — full detail on a single entry
   - `coverage_gaps` — identify under-explored regions
   - `read_graveyard` — browse failed mutations worth retrying

3. **Selection** — the agent chooses a parent, inspiration entries, and a mutation strategy (conservative / exploratory / crossover / graveyard_rescue).

4. **Parent Applied** — at the start of the next cycle, the workspace is restored to the selected parent's state before solving.

---

## The Graveyard

Failed mutations (rejected by the gate) are stored in `graveyard.json` instead of being discarded. Each entry records:

- **What was tried** — mutation description, strategy, specific actions (skills added/modified/removed, prompt changes)
- **Why it failed** — score before/after, failure reason, per-field failure directions ("too_high", "too_low")
- **What went wrong** — detected anti-patterns, investigation summary from the evolver's Phase 1 diagnosis
- **When it happened** — cycle, workspace version

The evolver can query past failures during its investigation phase using the `read_graveyard()` tool. This lets it learn from previous mistakes — avoiding strategies that already failed and understanding which fields are persistently problematic.

The `graveyard_rescue` mutation strategy (QD mode) specifically targets these entries — the evolver reads a failed mutation and attempts a different approach to the same problem.

---

## Tips for Practitioners

### Starting a new experiment

1. **Start with a good prompt.** The evolver improves what you give it — a blank prompt will waste cycles discovering basics. Write the domain knowledge you already have.

2. **Use `tool_loop` adapter** for tasks with computation tools. It gives the agent a bash tool for running scripts. Use `rlm` for open-ended reasoning tasks.

3. **Start with easy+medium tasks** to establish a baseline, then add hard tasks once the agent scores well on the basics.

4. **Use small batch_size (2-3)** for quick iteration during development. Increase to 5-10 for production experiments.

### Debugging poor performance

1. **Check the evolution report** (`evolution-report.html`) — it shows per-cycle score trajectory and what mutations were applied.

2. **Run with `-v`** for detailed logging — see each phase's output.

3. **Check if the evolver is proposing mutations.** If every cycle shows "no changes", the evolver may be hitting the request budget (two-phase evolver logs this). The graduated scope may be SKIP if scores are already high.

4. **Check the graveyard** — if the same type of mutation keeps failing, the task may need a different approach (different adapter, better tools, or manual prompt tuning).

### Version management

Each run creates git tags: `evo-YYYYMMDD-HHMM-0`, `evo-YYYYMMDD-HHMM-1`, etc. To compare runs:

```bash
cd workspaces/my-experiment

# List all tags
git tag -l 'evo-*'

# Diff between two versions
git diff evo-20260402-1700-0 evo-20260402-1700-3

# See what changed in a cycle
git show evo-20260402-1700-2
```

To tag a harness milestone manually:

```bash
git tag "my-experiment/harness-v1" -m "Baseline: reward 0.81"
```

### Using the archive across runs (QD mode)

The archive persists in `archive.json` and accumulates across runs. Different run configurations (easy-only, hard-only, different models) fill different regions of the behaviour space. This is a feature — each run illuminates different parts of the archive.

To reset the archive:
```bash
rm workspaces/my-experiment/archive.json
```

### Using the graveyard

The graveyard persists in `graveyard.json` and carries across runs in both modes. The evolver's `read_graveyard()` tool lets it inspect past failures during investigation. Enriched entries include per-field failure directions, detected anti-patterns, and the original investigation summary — so the evolver can see not just that a mutation failed, but *why*.

To reset the graveyard:
```bash
rm workspaces/my-experiment/graveyard.json
```

---

## Architecture Overview

```
                    ┌─────────────────────────┐
                    │   Evolution Config       │
                    │   (evolution.yaml)       │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   Orchestrator           │
                    │   (outer loop)           │
                    └────────────┬────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                   │
    ┌─────────▼─────────┐ ┌─────▼──────┐ ┌─────────▼─────────┐
    │   Local Solver     │ │  Engine    │ │  Selection         │
    │   (run tasks)      │ │  (6-phase) │ │  Strategy          │
    └───────────────────┘ └─────┬──────┘ └─────────┬─────────┘
                                │                   │
                    ┌───────────┼───────────┐       │
                    │           │           │  ┌────┴─────────────┐
              ┌─────▼──┐ ┌─────▼──┐ ┌──────▼──┐                  │
              │Classify │ │Analyse │ │Evolve   │    ┌─────────────▼──┐
              │(bonds)  │ │(scope) │ │(2-phase)│    │  hill_climb    │
              └────────┘ └────────┘ └─────────┘    │  Best-so-far   │
                                                    │  tracking      │
                                                    └────────────────┘
                                                             or
                                                    ┌────────────────┐
                                                    │  qd            │
                                                    │  QD Archive    │
                                                    │  UCB1 + Bandit │
                                                    │  Explorer Agent│
                                                    └────────────────┘
```

The **SelectionStrategy** protocol decouples parent selection from the core loop. The engine's 6-phase pipeline (classify → analyse → auto-seed → evolve → gate → version) is identical in both modes. Only the parent selection and cycle recording differ.
