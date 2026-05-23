# AEC-Bench

![AEC-Bench hero image showing a pixel-art weight bench with an engineering hard hat.](docs/assets/aec-bench-hero.png)

A Python platform for creating, running, and evaluating AEC (Architecture, Engineering, Construction) benchmark tasks for AI agent evaluation.

## Quick Start

Install the published package for normal CLI use:

```bash
pip install aec-bench
aec-bench --help
```

Install the optional Web UI runtime when you want the browser interface:

```bash
pip install "aec-bench[webui]"
aec-bench web
```

For development from a source checkout, keep commands inside `uv run`:

```bash
# Install source dependencies
uv sync --extra webui --dev

# List available templates
uv run aec-bench generate list-templates

# Generate 3 task instances from a template
uv run aec-bench generate task terzaghi-bearing-capacity --instances 3

# Run tests
uv run pytest tests/ -q
```

### Credentials

AEC-Bench loads `.env` from the project root when the CLI starts. Start from
`.env.example` and fill only the providers you use; the example file contains
placeholder names only and no real credentials.

## What This Does

AEC-Bench lets you:

1. **Create** benchmark tasks that test AI agents on real engineering calculations
2. **Generate** parameterised task instances from reusable templates
3. **Run** agents against tasks via Harbor execution
4. **Evaluate** results with scoring, trace analysis, and reporting
5. **Review** agent performance with structured human feedback

## CLI Reference

### Generate Tasks

```bash
# Generate instances from a built-in template
uv run aec-bench generate task <template-name> --instances 5 --seed 42

# Generate from a local template directory
uv run aec-bench generate task --template path/to/template/ --instances 3

# Preview without writing files
uv run aec-bench generate task terzaghi-bearing-capacity --dry-run

# Generate a full dataset from a suite configuration
uv run aec-bench generate dataset --config suite.toml

# List built-in templates
uv run aec-bench generate list-templates

# Validate a template
uv run aec-bench generate validate-template path/to/template/
```

The built-in catalogue is larger than a README can usefully list. Use
`uv run aec-bench generate list-templates` for the live template list, or
`uv run aec-bench library export --pretty` for the JSON catalogue consumed by
the public docs site.

### Run Experiments

```bash
# Run a single task path against a model
uv run aec-bench run tasks/ground/shallow-foundations --model claude-sonnet-4-20250514

# Run from an experiment config
uv run aec-bench run --config experiment.yaml --tasks-root tasks/

# Dry run to see the plan
uv run aec-bench run tasks/mechanical/heat-load --model claude-sonnet-4-20250514 --dry-run
```

### Prime Lab Export

AEC-Bench can export tasks as Prime Lab environments for local and hosted evals.
The integration maps deterministic tasks to `SingleTurnEnv`, workspace tasks to
stateful workspace tools, and RLM/lambda-RLM tasks to policy-aware stateful
exports. See [docs/prime-lab-guide.md](docs/prime-lab-guide.md).

```bash
uv run aec-bench prime smoke \
  --name aec-rlm-test \
  --task electrical/rlm-test
```

Run a hosted Prime eval against an existing Hub environment:

```bash
uv run aec-bench prime eval \
  --remote-env gabriel-syme/aec_prime_50_suite \
  --hosted \
  --model "Qwen/Qwen3.5-4B" \
  --split eval \
  --difficulty medium \
  --harness stateful \
  --env-num-examples 10 \
  --seed 20260509 \
  --num-examples 5 \
  --rollouts-per-example 3 \
  --max-tokens 4096 \
  --eval-name aec-prime-50-base-medium-stateful
```

Evaluate a Hosted Training adapter with the same command by passing the adapter
id separately. AEC-Bench composes the Prime inference model as
`<base-model>:<adapter-id>` and forwards the task-selection values through
Prime's `--env-args`.

```bash
uv run aec-bench prime eval \
  --remote-env gabriel-syme/aec_prime_50_suite \
  --hosted \
  --model "Qwen/Qwen3.5-4B" \
  --adapter-id uv124zgh7ttg3in94f7jzmv2 \
  --split eval \
  --difficulty medium \
  --harness stateful \
  --env-num-examples 10 \
  --seed 20260509 \
  --num-examples 5 \
  --rollouts-per-example 3 \
  --max-tokens 4096 \
  --eval-name aec-prime-50-adapter-medium-stateful
```

Use repeated `--difficulty` values for mixed slices, and use
`--env-arg KEY=VALUE` for additional `load_environment()` arguments that are not
first-class CLI options yet.

### Datasets

Datasets are versioned, immutable benchmark snapshots — the formal "this IS the benchmark" artifact. They sit between template generation and experiment execution.

```bash
# Create a dataset from electrical tasks only
uv run aec-bench dataset create --name "electrical-v1" --version 1.0.0 --domain electrical

# Create from all tasks
uv run aec-bench dataset create --name "full-bench" --version 1.0.0

# Create from a suite.toml (records provenance)
uv run aec-bench dataset create --name "generated-bench" --version 1.0.0 --config suite.toml

# List datasets
uv run aec-bench dataset list

# Show dataset details and integrity status
uv run aec-bench dataset info electrical-v1

# Generate an experiment config from a dataset
uv run aec-bench dataset config electrical-v1 --model gpt-41-mini -o experiment.yaml

# Verify integrity (for CI — exits 0 if clean, 1 if drifted)
uv run aec-bench dataset validate electrical-v1@1.0.0

# Export for sharing
uv run aec-bench dataset export electrical-v1 -o electrical-v1.tar.gz

# Import a shared dataset
uv run aec-bench dataset import electrical-v1.tar.gz
```

The typical workflow:

```bash
# 1. Create a dataset
uv run aec-bench dataset create --name electrical-v1 --version 1.0.0 --domain electrical

# 2. Generate experiment config
uv run aec-bench dataset config electrical-v1 --model gpt-41-mini -o experiment.yaml

# 3. Run it
uv run aec-bench run --config experiment.yaml
```

Reference a dataset in an experiment config manually:

```yaml
tasks:
  dataset: "electrical-v1@1.0.0"
  difficulties: ["medium", "hard"]  # optional filter on top
```

### Import Harbor Jobs

```bash
# Import a completed Harbor job into the ledger
uv run aec-bench import jobs/2026-03-04__17-57-43
```

### Evaluate

```bash
# Evaluate an experiment (table output)
uv run aec-bench evaluate -e experiment-001

# JSON output
uv run aec-bench evaluate -e experiment-001 -o json

# Generate an HTML report
uv run aec-bench evaluate -e experiment-001 --report report.html

# Filter by model or adapter
uv run aec-bench evaluate -e experiment-001 --model claude-sonnet-4-20250514
```

### Reports

```bash
# Experiment summary
uv run aec-bench report summary -e experiment-001

# Cross-experiment leaderboard
uv run aec-bench report leaderboard

# Export trace summaries
uv run aec-bench report traces -e experiment-001

# Behavioral analysis
uv run aec-bench report behavioral -e experiment-001
```

### Ledger

```bash
# List trial records
uv run aec-bench ledger list

# Export to JSONL
uv run aec-bench ledger export -o trials.jsonl
```

### Interactive TUI

```bash
# Launch the terminal UI
uv run aec-bench tui

# Jump to a specific experiment
uv run aec-bench tui -e experiment-001

# Enable review mode
uv run aec-bench tui -e experiment-001 -r reviewer-001
```

**Primary keys**:

| Key | Screen | Purpose |
|-----|--------|---------|
| `d` | Dashboard | Home screen with live stats and experiment summaries |
| `e` | Explore | Browse the task library, datasets, and leaderboard surfaces |
| `r` | Review | Filterable trial triage and annotation flows |
| `a` | Analyse | Adapter x task evaluation and comparison surfaces |
| `Ctrl+P` | Command palette | Jump to screens, experiments, trials, and quick actions |
| `Enter` | Drill in | Open the highlighted trial, dataset, model, or matrix cell where supported |

### Web UI

The Web UI is optional in packaged installs:

```bash
pip install "aec-bench[webui]"
aec-bench web
```

When building a release from source, build the Svelte app before `uv build` so
the wheel and sdist include the compiled SPA:

```bash
cd src/aec_bench/web/frontend
npm install
npm run build
cd -
uv build
```

For Web UI development with Vite hot reload:

```bash
uv sync --extra webui --dev
cd src/aec_bench/web/frontend
npm install
cd -
uv run aec-bench web --dev
```

### Configuration

```bash
# View current config
uv run aec-bench config view

# Set a value
uv run aec-bench config set tasks_root tasks
```

## Agent Skills

Agent skills are portable workflow contracts. They can be implemented as native
skills, slash commands, prompts, or task recipes in Claude Code, Codex, Copilot,
or another agent environment.

| Skill | Command | Purpose |
|-------|---------|---------|
| **Add Task** | `/add-task` | Interview-driven seed creation from expert description |
| **Create Template** | `/create-template <seed-path>` | Build a generation template from a seed file |
| **Hardening Pass** | `/hardening-pass <path>` | Quality-gate a template or task instance before benchmarking |
| **Domain Check** | `/domain-check` | Verify architectural invariants before publishing or committing |

**Typical flow:** `/add-task` interviews an expert and produces a seed file. If the task is parameterisable, it hands off to `/create-template` which builds the template and generates instances. Then `/hardening-pass` reviews the template for correctness before use in real benchmarks.

## Writing Agents

Default agents live at `agents/` and subclass Harbor's `BaseAgent` directly, composing aec-bench utility functions:

```python
from harbor import BaseAgent
from aec_bench.agents.scripts import build_anthropic_tool_loop_script
from aec_bench.agents.env import build_provider_env
from aec_bench.agents.tools import discover_tools

class MyToolAgent(BaseAgent):
    def get_script(self, task) -> str:
        tools = discover_tools(task)
        return build_anthropic_tool_loop_script(tools=tools)

    def get_env(self, task) -> dict[str, str]:
        return build_provider_env("anthropic")
```

Ready-to-use agents in `agents/`:
- `script_anthropic.py`, `script_azure_openai.py` — single-turn
- `tool_loop_anthropic.py`, `tool_loop_azure_openai.py` — multi-turn with tools
- `pydantic_ai_agent.py` — multimodal with chart generation support (provider-agnostic)

## Task Disciplines

~240 seed tasks across 5 engineering disciplines:

| Discipline | Examples | Seeds |
|------------|----------|-------|
| **Civil** | Roads, drainage, pavement, hydraulics, earthworks | ~85 |
| **Electrical** | Cable sizing, fault current, lighting, power systems | ~75 |
| **Ground** | Foundations, slopes, retaining walls, soil interpretation | ~5 |
| **Mechanical** | HVAC, fire protection, piping, acoustics, process eng. | ~75 |
| **Structural** | Steel/concrete design, seismic, fatigue, connections | ~38 |

## Project Structure

```
src/aec_bench/          # Library source
tests/                  # Regression test suite
tasks/                  # Benchmark task seeds and instances
seeds/                  # Expert-created seed files (from /add-task)
agents/                 # Ready-to-use default agent implementations
scripts/                # Utility scripts for local maintenance workflows
docs/                   # Architecture, contracts, invariants, domain guides
```

## Architecture

Dependencies flow downward. Nothing imports upward.

```
Contracts (foundation — Pydantic models)
  ├── Tasks, Templates, Adapters, Agents
  ├── Generation (templates → instances)
  └── Harness (orchestration)
        └── Evaluation (scoring, traces)
              ├── Communication (reports, exports)
              └── Feedback (human review)
```

Key design rules:
- `validity > reproducibility > coverage > cost > throughput`
- `StrictModel` at internal boundaries, `LenientModel` for external data
- `@dataclass(frozen=True)` for non-boundary data structures
- Adapters translate protocol only — no task logic, no scoring

## Development

```bash
# Run tests
uv run pytest tests/ -q

# Lint
uv run ruff check src/ tests/

# Type check
uv run mypy src/aec_bench/contracts/

# Format
uv run ruff format src/ tests/
```

## Further Reading

- `docs/ARCHITECTURE.md` — Domain boundaries and dependency rules
- `docs/INVARIANTS.md` — 10 non-negotiable architectural rules
- `docs/CONTRACTS.md` — Data shapes at every boundary
- `docs/AGENTS.md` — Agent guide with conventions and shared utilities
