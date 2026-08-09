# AEC-Bench

![AEC-Bench hero image showing a pixel-art weight bench with an engineering hard hat.](assets/aec-bench-hero.png)

A Python platform for creating, running, and evaluating AEC (Architecture, Engineering, Construction) benchmark tasks for AI agent evaluation.

## Quick Start

Install the published package for normal CLI use:

```bash
pip install aec-bench
aec-bench --help
```

The base installation supports task discovery, generation and validation,
datasets, the ledger, deterministic evaluation and reports, and provider-free
world functions. Optional commands stay in `--help`; when a feature is absent,
the command prints its exact installation command.

Install only the features you use:

| Feature | Install command |
|---|---|
| Harbor execution and import | `pip install "aec-bench[execution]"` |
| Harbor on Morph Cloud | `pip install "aec-bench[execution,morph]"` |
| Local model-backed agents and reviewers | `pip install "aec-bench[local-agents]"` |
| Prime CLI, export, and hosted evaluation | `pip install "aec-bench[prime]"` |
| Prime Agent interactive worlds over ACP | `pip install "aec-bench[prime-agent]"` |
| Web UI | `pip install "aec-bench[webui]"` |
| Terminal UI | `pip install "aec-bench[tui]"` |
| Evolution and local model execution | `pip install "aec-bench[evolution,local-agents]"` |

For example, to launch the browser interface:

```bash
pip install "aec-bench[webui]"
aec-bench web
```

For development from a source checkout, keep commands inside `uv run`:

```bash
# Install source dependencies
uv sync --all-extras --dev

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

For Azure AI Foundry deployments that expose the v1 OpenAI-compatible API, set
`AZURE_OPENAI_ENDPOINT` to the `/openai/v1/` endpoint, set
`AZURE_OPENAI_API_KEY`, and run with the deployment name as `--model`. The
`pydantic_ai`, `rlm`, and local Pydantic tool-loop paths use those settings.

For Together AI, set `TOGETHER_API_KEY` and use an explicit `together:` model
prefix, for example `--model "together:Qwen/Qwen3.7-Max"`. The prefix keeps
Together model IDs from being routed to Azure when Azure credentials are also
present.

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

# Generate a full suite from a suite configuration
uv run aec-bench generate suite --config suite.toml

# List built-in templates
uv run aec-bench generate list-templates

# Validate a template
uv run aec-bench generate validate-template path/to/template/
```

The built-in catalogue is larger than a README can usefully list. Use
`uv run aec-bench generate list-templates` for the live template list, or
`uv run aec-bench library export --pretty` for the JSON catalogue consumed by
the public docs site. Direct template loading is strict; catalogue discovery
reports invalid candidates. Generated task lineage records the template source
digest, seed, instance index, and difficulty, so repeated generation does not
depend on wall-clock time.

### Run Experiments

Install `aec-bench[execution]` before using Harbor. Add the `morph` extra for a
Morph Cloud backend. The provider-backed adapters on the separate `run-local`
path require `aec-bench[local-agents]`. The `prime-agent` adapter instead uses a
separately installed Prime Agent executable.

```bash
# Run a single task path against a model
uv run aec-bench run tasks/ground/shallow-foundations --model "<model-id>"

# Run from an experiment config
uv run aec-bench run --config experiment.yaml --tasks-root tasks/

# Dry run to see the plan
uv run aec-bench run tasks/mechanical/heat-load --model "<model-id>" --dry-run

# Run through Morph Cloud via Harbor
uv run aec-bench run tasks/electrical/pf-droop --model "<model-id>" --backend morph
```

`aec-bench run` defaults to Harbor's `modal` backend. Morph Cloud runs use Harbor's normal task, agent, artifact, and verifier lifecycle through `--backend morph`; set `MORPH_API_KEY` in `.env` before using it.
Remote runs use the same synchronous Harbor dispatch-and-import workflow and
produce current `TrialRecord` ledger entries. `aec-bench run-local` remains the
separate no-Harbor path for local execution.

#### Prime Agent local adapter

Install [upstream Prime Agent](https://github.com/PrimeIntellect-ai/prime-agent#getting-started)
separately so `prime-agent` is on `PATH`, then select it explicitly:

```bash
uv run aec-bench run-local tasks/<task> \
  --adapter prime-agent \
  --model anthropic/<model-id>
```

This adapter supports the current artifact/workspace task path. AEC-Bench stages
the task, launches Prime Agent in JSON mode, then uses the existing output,
normalisation, verifier, evaluation, and trial-import flow. The model string is
passed to Prime unchanged. All existing local adapters remain available and
`rlm` remains the default.

Each trial uses isolated Prime configuration and session directories under
`logs/prime/`. Ambient skills, extensions, prompt templates, themes, and context
files are disabled. Provider credentials can still be inherited by the process,
but are not written to provenance. Results preserve `prime-events.jsonl`,
`prime-stderr.log`, `prime-run.json`, and saved Prime session files. The
integration is tested against Prime Agent 0.7.0 and JSON event stream version 3;
unsupported stream versions fail explicitly.

Prime Agent executes model-generated Python and commands with the current user's
OS permissions. Process isolation and trial-specific state are reproducibility
controls, not a security sandbox. Use this local path only with trusted task
packages; use an externally contained execution path for untrusted material.

#### Prime Agent interactive world sessions

Install the ACP client separately from the upstream executable:

```bash
pip install "aec-bench[prime-agent]"
# Install upstream Prime Agent separately so prime-agent is on PATH.
```

The maintained async Python entry point is
`aec_bench.harness.pump_station_prime.session.run_pump_station_prime_session`.
It receives a
host-selected `WorldSessionRequest`, launches one Prime ACP process for one
session, and supplies the resolved objective in the initial prompt. By default,
it installs only the generic `aec-world` skill. This is the Open treatment:
Prime receives the objective, actor-visible starting material, and generic
actor capability, with no task-family method or external plan.

The caller can select the experimental Guided treatment explicitly:

```python
await run_pump_station_prime_session(
    ...,
    pump_station_guidance=True,
)
```

The complete pump journey entry point is
`aec_bench.harness.pump_station_prime.journey.run_pump_station_prime_journey`.
It reuses
the bounded session runner. When Prime reaches an Operations boundary, the host
closes Prime, applies at most one deterministic task-owned control, and starts a
fresh ACP session at the exact new snapshot. All sessions use the same actor
workspace and actor tenure, so Prime can continue from its own ledger and files.
Prime runtime state is new for each session. World files, host-control details,
and verifier data do not enter the actor workspace. An LLM does not choose or
apply the host control.

`PumpStationPrimeJourneyLimits` applies one set of emergency limits to the complete
journey. Each fresh session receives only the remaining world-action,
model-call, token, cost, and wall-time allowance. A host control can follow only
a clean Prime `end_turn` with no reached limit. The host writes a private atomic
checkpoint before it applies a control. If the process stops after the world
records that control, call the same entry point with `resume=True`; the world
repository returns the exact durable result instead of applying it twice.

Prime refinement policy is explicit:

- `capture` is the default. It preserves refinement metadata and safe harness
  evidence but does not carry a change to another Prime session.
- `discover` allows Prime to use `/refine`. It captures prompt, memory, skill,
  and subagent entries with their local or global scope. Only portable global
  entries continue to the next fresh session in the same journey.
- `candidate` installs one exact candidate in every fresh session. A new
  refinement event or a changed candidate fails the session, so the comparison
  treatment cannot change itself.

These modes do not change the world repository. Loading a Prime candidate is
not world replay. Canonical command replay and verification stay task-owned.
Prime state remains isolated for each journey and cannot change ambient Prime
state or another benchmark run.

The first qualification entry point is
`aec_bench.experimentation.qualification.prime_refinement.run_prime_refinement_qualification`.
It runs clean empty-harness and fixed-candidate journeys on pump profiles RS1
and RS2 by default. It records the existing task-owned evaluation for each
cell and pairs the results. Its decision stays `pending`; it does not accept,
promote, or materialize a candidate.

Guided installs `aec-world` followed by `pump-station-guidance` and tells Prime
to load the second skill before its first world action. The guidance teaches
compact state, exact action accounting, rejection interpretation, and
pump-station decision checks. Its current protocol tells Prime to combine each
world action, ledger append, compact-state update, and selected output in one
notebook cell. It does not expose or coach Prime against host-side execution
limits, and it does not contain a fixed plan, action sequence, or current
instance solution. The world runtime and reference controller are validated
against two registered pump profiles. Guided treatment evidence still comes
from RS1 until a guided RS2 model study is run. Bounded-session callers supply
`PumpStationPrimeSessionLimits`. Journey callers supply
`PumpStationPrimeJourneyLimits`, which also limits session and host-control
counts.

The pump world keeps RS1 as its default profile. RS2 uses the same station,
opening condition, service demand, evidence, actor interface, and evaluation.
Its second maintenance window is 10 hours, and its third window starts after a
six-hour gap. This makes Pump B verification wait for the third window.

Inside Prime, the available world calls are:

```python
await aec_world.capabilities()
observation = await aec_world.observe()
await aec_world.invoke(
    "continue_operation",
    {"reason": "Advance the current world."},
    decision_id=observation["decision_id"],
)
```

The host-owned actor proxy privately binds one pump-world repository and exposes
only `capabilities`, `observe`, and `invoke`. Prime never receives a world run
directory or host-control selector. The Prime root session and all descendants
share one capability and are therefore one composite AECBench actor principal;
this integration does not claim that only the root process can invoke actions.
The host rejects new world actions after the configured allowance. An exact
retry of the same request remains available and does not consume another
allowance, so the installed actor retry contract stays authoritative.

AECBench monitors all Prime session artifacts for the composite principal and
cancels the active ACP prompt when a model-call, aggregate-token, or aggregate-
cost threshold is reached. Token and cost limits are enforced at completed
provider-response boundaries: the response that reaches the threshold is
preserved and can cross it, and a provider request already in flight when the
host cancels can also report usage. The wall-clock limit covers Prime process
setup and the active prompt.

Prime session state and world state remain separate. In particular, ACP
`end_turn` while the world is active produces an incomplete result and does not
start another prompt automatically. World replay, verification, and evaluation
continue to use the existing task-owned repository and evaluator.

One Prime ACP session is evaluated as a task-owned `bounded_continuation`.
Prime has no host-control capability, so the bounded scope does not require it
to perform Operations reviews that belong to the host boundary. This changes
only the terminal-stewardship availability gate: active restrictions, deferred
work, unavailable assets, and other closing liabilities remain explicit in the
evaluation. A valid bounded evaluation does not mark an active world or an
incomplete or interrupted Prime session as completed. A `complete_journey`
treatment requires separately designed host-owned control orchestration.

Each run preserves `prime-acp-in.jsonl`, `prime-acp-out.jsonl`,
`prime-stderr.log`, `prime-run.json`, `prime-world-run.json`, Prime session
files, and a separate actor-transport log. `prime-run.json` normalizes usage,
cost, root/child session topology, refinement counts, configured limits, and
the limit that ended the prompt. It also records the selected skills in order,
with content digests but no host paths. Skill availability in that provenance
and a completed skill read in the retained session are separate treatment-
integrity facts. `prime-world-run.json` records the selected task-owned
evaluation scope and whether that evaluation passed alongside the separate
session and world states. Unknown ACP `_meta` content stays in the raw evidence.
The actor log timestamps every accepted, rejected, unauthorized, and malformed
transport attempt without recording the socket capability, host paths, or
hidden state. Trial-local Prime HOME/XDG directories, configuration, sessions,
workspace files, and refinement artifacts are isolated and are not promoted to
another run.

`PrimeAcpIsolation.DEVELOPMENT_SAME_USER` is explicitly non-benchmark-valid
development evidence because Prime has the current user's OS permissions.
Benchmark-valid local execution currently requires
`PrimeAcpIsolation.MACOS_SANDBOX`, which applies a macOS Seatbelt profile to
Prime and its descendants, denies the AECBench source and private world
repository, and permits the scoped actor socket. Other platforms fail closed
until an equivalent filesystem/process boundary is implemented.

This integration is additive. It does not change Harbor, the installed
`actor-interface`, task templates, world semantics, verification, or
evaluation. Guided selection also does not change actor authority, world state,
replay, automatic continuation, verification, or evaluation.

### Meta-Harness

Use the meta-harness workflow when a task needs an explicit world model, reviewer
evidence, governance decisions, or candidate-vs-baseline harness comparison.

```bash
uv run aec-bench meta-harness recipe \
  --task-file task.md \
  --output artefacts/meta-harness/demo
```

The recipe writes a scriptable workspace for intake, world generation, reviewer
evidence, governance, and comparison artifacts. Run
`aec-bench meta-harness --help` for the complete command surface.

### Prime Lab Export

AEC-Bench can export tasks as Prime Lab environments for local and hosted evals.
Install `aec-bench[prime]` for commands that invoke Prime or Verifiers.
The integration has two current task-package behaviors: plain tasks use
`SingleTurnEnv`; tasks with tools, workspace manifests, Compose files, or
RLM/lambda-RLM policy use one stateful workspace environment. A mixed package
uses the stateful environment for every selected task. General exports accept
public tasks only, keep verifier files out of the actor workspace, and record
each task's content revision and visibility. See the public
[Prime Lab](https://aecbench.com/docs/advanced/prime-lab) documentation.

```bash
uv run aec-bench prime smoke \
  --name aec-rlm-test \
  --task electrical/rlm-test
```

Run a hosted Prime eval against an existing Hub environment:

```bash
uv run aec-bench prime eval \
  --remote-env <prime-namespace>/<environment-name> \
  --hosted \
  --model "<base-model-id>" \
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
  --remote-env <prime-namespace>/<environment-name> \
  --hosted \
  --model "<base-model-id>" \
  --adapter-id <adapter-id> \
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

`aec-bench import-prime-eval` imports Prime samples into the current
`TrialRecord` and `EvaluationResult` authorities. Provider completion,
truncation, and errors determine execution status independently of reward. The
import preserves the provider sample, conversation, and submitted output as
content-bound artifacts. Live Prime commands remain explicit and require the
user's Prime installation, credentials, and network access; the normal test
suite makes no hosted calls.

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
uv run aec-bench dataset config electrical-v1 --model "<model-id>" -o experiment.yaml

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
uv run aec-bench dataset config electrical-v1 --model "<model-id>" -o experiment.yaml

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
uv run aec-bench --json evaluate -e experiment-001

# Generate an HTML report
uv run aec-bench evaluate -e experiment-001 --report report.html

# Filter by model or adapter
uv run aec-bench evaluate -e experiment-001 --model "<model-id>"
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

Install `aec-bench[tui]` before launching the terminal interface.

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
npm ci
npm run build
cd -
uv build
```

For Web UI development with Vite hot reload:

```bash
uv sync --extra webui --dev
cd src/aec_bench/web/frontend
npm ci
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
| **Configure Experiment** | `/configure-experiment` | Select tasks, agents, models, and execution settings for a validated experiment manifest |
| **Create Dataset** | `/create-dataset` | Build and verify a reproducible dataset from templates or existing tasks |
| **Create Template** | `/create-template <seed-path>` | Build a generation template from a seed file |
| **Hardening Pass** | `/hardening-pass <path>` | Quality-gate a template or task instance before benchmarking |
| **Domain Check** | `/domain-check` | Verify architectural invariants before publishing or committing |
| **Meta-Harness** | `/meta-harness` | Design or compare a harness candidate from task prose and run evidence |

`aec-bench init` installs the packaged skills into `.claude/skills/`. Run
`aec-bench init --update-skills` in an existing project to refresh the packaged
copies without replacing user-added skills.

**Typical flow:** `/add-task` produces an expert-authored seed. For a
parameterisable task, `/create-template` builds the generation template and
`/hardening-pass` checks it before benchmark use. `/create-dataset` freezes a
reproducible selection, then `/configure-experiment` prepares the run.

## Harbor Agent

Harbor execution uses one repository-owned agent at `agents/entrypoint_agent.py`.
It reads the execution bundle created by the harness and dispatches to the
selected current adapter. Provider selection, lifecycle tools, proposal
sessions, and pump-world execution stay behind that composition boundary;
task worlds do not import provider SDKs.

Add adapter behavior to the installed adapter owner and route it through the
current execution bundle. Do not create a second per-provider Harbor agent.

## Task Disciplines

Task sources and built-in generation templates cover six engineering
disciplines. The catalogue changes frequently, so use
`aec-bench generate list-templates` for the current template inventory and
`aec-bench library export --pretty` for the current public catalogue.

| Discipline | Examples |
|------------|----------|
| **Civil** | Roads, drainage, pavement, hydraulics, earthworks |
| **Electrical** | Cable sizing, fault current, lighting, power systems |
| **Ground** | Foundations, slopes, retaining walls, soil interpretation |
| **Maritime** | Port, coastal, berth, and marine infrastructure |
| **Mechanical** | HVAC, fire protection, piping, acoustics, process engineering |
| **Structural** | Steel and concrete design, seismic, fatigue, connections |

## Project Structure

```
src/aec_bench/          # Library source
tests/                  # Regression test suite
tasks/                  # Benchmark task seeds and instances
seeds/                  # Expert-created seed files (from /add-task)
agents/                 # Ready-to-use default agent implementations
scripts/                # Utility scripts for local maintenance workflows
docs/                   # Repository-owned architecture, contracts, and invariants
```

## Architecture

AEC-Bench supports two execution families. Artifact/workspace tasks run a
bounded job and evaluate the resulting files and evidence. Interactive worlds
run validated actions against durable state and can optionally support host
controls, branching, rollouts, and provider integrations. They share benchmark
identity, execution evidence, evaluation ownership, and provider boundaries;
they do not share one low-level lifecycle.

Key design rules:

- `validity > reproducibility > coverage > cost > throughput`
- `StrictModel` at internal boundaries, `LenientModel` for external data
- `@dataclass(frozen=True)` for non-boundary data structures
- Adapters translate protocol only — no task logic, no scoring

See the [repository documentation index](docs/README.md) for authority and
routing, and [Architecture](docs/ARCHITECTURE.md) for current ownership and
dependency direction.

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

- [Repository documentation](docs/README.md) — Authority, taxonomy, status, and ownership
- [Architecture](docs/ARCHITECTURE.md) — Current execution flows, ownership, and dependency direction
- [Invariants](docs/INVARIANTS.md) — Stable benchmark-validity and reproducibility guarantees
- [Contracts](docs/CONTRACTS.md) — Boundary contract index and compatibility policy
- [Interactive-world runtime](docs/protocols/interactive-world-runtime.md) — Registered persistent-world protocol
- [Documentation agent guide](docs/AGENTS.md) — Rules for maintaining repository-owned documentation
- [Public documentation](https://aecbench.com/docs) — Installation, usage, integrations, and reference guides

## License

AEC-Bench is distributed under the MIT License. See [LICENSE](LICENSE).
