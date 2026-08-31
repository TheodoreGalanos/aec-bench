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
uv run aec-bench generate task terzaghi-bearing-capacity --instances 3 --lifecycle proposed --visibility public

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
uv run aec-bench generate task <template-name> --instances 5 --seed 42 --lifecycle proposed --visibility public

# Generate from a local template directory
uv run aec-bench generate task --template path/to/template/ --instances 3 --lifecycle proposed --visibility public

# Preview without writing files
uv run aec-bench generate task terzaghi-bearing-capacity --lifecycle proposed --visibility public --dry-run

# Generate a full suite from a suite configuration
uv run aec-bench generate suite --config suite.toml

# Regenerate and compare runtime task files from an optional replay sidecar
uv run aec-bench generate replay tasks/generation-manifest.json

# List built-in templates
uv run aec-bench generate list-templates

# Validate a template
uv run aec-bench generate validate-template path/to/template/
```

Suite configurations must declare `task_lifecycle` and `task_visibility`. These
values are written to every generated task and to the replay manifest; they are
not inferred from difficulty visibility.

The built-in catalogue is larger than a README can usefully list. Use
`uv run aec-bench generate list-templates` for the live template list, or
`uv run aec-bench library export --pretty` for the JSON catalogue consumed by
the public docs site. The command emits deterministic schema 2 content with
templates and seeds only; clients derive counts from those arrays. Direct
template loading is strict; catalogue discovery reports invalid candidates.
Generated `task.toml` files contain runtime semantics only. Optional replay
inputs live once in `generation-manifest.json`. A suite of clean built-in
templates in a Git checkout records one Git revision. Local, modified, or
installed-package templates use one exact source archive. The sidecar contains
no generation time, package version, provider route, transport identity, or
absolute path. Deleting the sidecar does not change task discovery, validation,
execution, or evaluation.

World and lifecycle owner catalogues are generated Python composition files.
Use `uv run aec-bench catalogue build` after an owner change and
`uv run aec-bench catalogue check` in review or CI. The check validates
descriptor shape, identities, versions, capabilities, registration IDs, and
stable order. To save a semantic snapshot for review, pass
`--snapshot path/to/catalogue.json` to `build`; compare it later with
`uv run aec-bench catalogue diff --against path/to/catalogue.json`.
Snapshots compare entities through their IDs, keys, and explicit versions.

### Run Experiments

Install `aec-bench[execution]` before using Harbor. Add the `morph` extra for a
Morph Cloud backend. Add the `deepseek-harness` extra for the DeepSeek Harness
adapter. The provider-backed adapters on the separate `run-local` path require
`aec-bench[local-agents]`. The `prime-agent` adapter instead uses a separately
installed Prime Agent executable.

```bash
# Run a single task path against a model
uv run aec-bench run tasks/electrical/voltage-drop --model "<model-id>"

# Run from an experiment config
uv run aec-bench run --config experiment.yaml --tasks-root tasks/

# Dry run to see the plan
uv run aec-bench run tasks/mechanical/heat-load --model "<model-id>" --dry-run

# Run through Morph Cloud via Harbor
uv run aec-bench run tasks/electrical/pf-droop --model "<model-id>" --backend morph

# Export one already published run package
uv run aec-bench run export <run-id> --output run-package.tar.zst

# Verify and import a portable run package
uv run aec-bench run import run-package.tar.zst

# Inspect a persisted resolved run and its canonical plan
uv run aec-bench run inspect <run-key-or-uuid> --store-root artefacts/runs

# Resolve and persist a requested specification and complete ready plan
uv run aec-bench run plan --config experiment.yaml --tasks-root tasks --store-root artefacts/runs

# Show the full persisted requested specification and plan for an existing run
uv run aec-bench run plan <run-key-or-uuid> --store-root artefacts/runs

# Show semantic field changes between two persisted runs
uv run aec-bench run diff <left-run-key-or-uuid> <right-run-key-or-uuid> --store-root artefacts/runs

# Reconcile explicit typed trial outcomes against a persisted plan
uv run aec-bench run reconcile <run-key-or-uuid> --observations outcomes.json --store-root artefacts/runs

# Show read-only operational progress (both roots are required; no attachments are loaded)
uv run aec-bench run status <run-id> --operational-store artefacts/operational.sqlite3 --plan-root artefacts/runs

# Request idempotent cancellation of queued work and mark active work for reconciliation
uv run aec-bench run cancel <run-id> --operational-store artefacts/operational.sqlite3

# Start or resume a persisted local artifact plan (all roots are explicit)
uv run aec-bench run start <run-id> --tasks-root tasks --operational-store artefacts/operational.sqlite3 --plan-root artefacts/runs
uv run aec-bench run resume <run-id> --tasks-root tasks --operational-store artefacts/operational.sqlite3 --plan-root artefacts/runs
```

`run start` and `run resume` execute only ready artifact plans with the local scheduler. Resume reconciles expired and unknown work before it leases new work.

`run plan --config` currently accepts identity-bearing artifact tasks. It rejects Interactive World and lifecycle
task values until those loaders expose the same identity-bearing task snapshot boundary.

`aec-bench run` defaults to Harbor's `modal` backend. Morph Cloud runs use Harbor's normal task, agent, artifact, and verifier lifecycle through `--backend morph`; set `MORPH_API_KEY` in `.env` before using it.
Remote runs use the same synchronous Harbor dispatch-and-import workflow and
produce current `TrialRecord` ledger entries. `aec-bench run-local` remains the
separate no-Harbor path for local execution.

A published run package is one deterministic `tar.zst` archive. It contains
the plain run plan, exact trial references, and all referenced artifact bytes.
The ledger stores the archive once under one `ArtifactRef`. Export copies those
bytes; import verifies every member, size, and SHA-256 digest before it writes
them to the destination ledger. Use `--ledger-root <path>` when the package is
not in the configured ledger.

Local artifact trials retain the declared primary output, files added or
changed by the actor, and base, final, and deletion manifests. They do not
duplicate unchanged task inputs as output artifacts. The selected-workspace
export remains the explicit option when a protocol requires the complete actor
snapshot. See [Artifact workspace evidence](docs/CONTRACTS.md#artifact-workspace-evidence).

#### DeepSeek Harness adapter (experimental)

The DeepSeek Harness adapter uses the shared Harbor entrypoint and its provider
selection boundary. It does not add a provider-specific Harbor agent or
command. The model uses the existing `provider:model` form. The current
qualified routes are `azure:<deployment>` and `deepseek:<model>`. Azure uses
the Harness generic provider adapter with an OpenAI-compatible route. DeepSeek
uses the Harness `deepseek-official` wire adapter.
Install the execution and adapter extras, set the selected provider values in
`.env`, and select `deepseek_harness` in an ordinary experiment manifest:

```bash
uv sync --extra execution --extra deepseek-harness
```

```dotenv
AZURE_OPENAI_ENDPOINT="https://<resource>.openai.azure.com"
AZURE_OPENAI_API_KEY="<provider-key>"
```

```yaml
experiment_id: deepseek-baseline
name: DeepSeek Harness baseline
tasks:
  include_patterns: ["electrical/voltage-drop"]
agents:
  - name: deepseek-baseline
    adapter: deepseek_harness
    model: "azure:<deployment-name>"
    parameters:
      timeout_sec: 1800
      max_tokens: 8192
compute:
  backend: docker
repetitions: 1
```

Run it with `uv run aec-bench run --config experiment.yaml --tasks-root tasks`.
For local debugging, use the same adapter without Harbor or Docker:

```bash
uv run aec-bench run-local tasks/electrical/voltage-drop \
  --adapter deepseek_harness \
  --model "azure:<deployment-name>" \
  --timeout 600 \
  --max-tokens 8192 \
  --keep-workspace
```

`run-local` executes one candidate by default. Use the built-in best-of-K
recipe to run independent candidates and select the first candidate that
completed with a non-empty primary output. Candidate-index order breaks ties.
The official verifier runs only for the selected candidate.

```bash
uv run aec-bench run-local tasks/electrical/voltage-drop \
  --model "azure:<deployment-name>" \
  --best-of 3 \
  --selector self
```

Local results retain the redacted Harness evidence under
`logs/deepseek-harness/`, including `stderr.log` on failure.
The provider prefix selects one credential route:

| Prefix | Required environment | Endpoint behavior |
| --- | --- | --- |
| `azure:` | `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT` | Accepts an Azure resource root or `/openai/v1` URL and normalizes it to the v1 route |
| `deepseek:` | `DEEPSEEK_API_KEY` | Uses `DEEPSEEK_BASE_URL` when set, or the public DeepSeek API |

The shared entrypoint records the selected provider in the execution bundle,
but does not serialize credentials. It passes only the selected provider's
approved environment values. The worker maps them to the private
`DSH_API_KEY` and `DSH_BASE_URL` names used by Cordis. It installs the qualified
DeepSeek SDK and runtime in the trial environment if they are absent.

The provider prefix selects both the approved host environment and the Harness
LLM route. Azure uses the internal `azure` route and does not send DeepSeek-only
`thinking` or `reasoning_effort` fields. DeepSeek uses `deepseek-official` for
the upstream DeepSeek protocol. Trial evidence records both identities.

The baseline, native-tool, and explicit-commit modes are separate treatments:

| Condition | AEC-authored DeepSeek surface | Completion rule |
| --- | --- | --- |
| Baseline | None | Normal Harness completion and candidate collection |
| Native tools | `@aec-bench/dsh-tools` with the exact AEC-owned tool manifest | The owning lifecycle or world runtime decides completion |
| Explicit commit | `aec_commit_output` only | The task contract accepts and binds the exact output bytes |

Native-tool availability does not create candidate output. The adapter needs a
nonempty declared artifact, a nonempty assistant response, or an accepted and
revalidated output commit. A lifecycle or world can still record its own valid
episode outcome when the adapter remains partial because it has no candidate
output. The native gateway derives request identity from the DeepSeek session
and tool call, keeps that identity out of the model schema, and records an
explicit quiescent or unsettled close result.

Explicit commit is capability-gated. Set `output_completion_commit: true` only
with a matching task-owned `output_completion_contract`. The current supported
contract format is `markdown_final_fenced_json`, and its output path must be
`/workspace/output.md` for Harbor runs. The adapter loads the commit plugin only
for that request. It does not use the plugin as a task verifier.

```yaml
parameters:
  output_completion_commit: true
  output_completion_contract:
    schema_version: aecbench.output-completion-contract.v1
    output_path: /workspace/output.md
    format: markdown_final_fenced_json
    required_top_level_keys: [findings, summary]
    require_single_final_json_block: true
```

The current support boundary is:

- artifact and workspace tasks that use the stock DeepSeek coding tools;
- finite evidence lifecycles and the registered pump-station Harbor world through
  exact AEC-owned native tool gateways;
- an exact whole-trial actor-action budget, whole-process `timeout_sec`, and
  per-model-request `max_tokens` limit;
- raw session evidence, readable treatment evidence, and optional exact-byte
  output commitment;
- no general task-tool translation, arbitrary interactive-world bridge,
  subagents, workflows, or code mode;
- no exact `max_turns`, `max_tool_calls`, or `max_context_tokens` enforcement;
- no network-isolation guarantee from the adapter. Use the selected disposable
  Harbor environment as the external security boundary.

The qualified SDK and runtime version is `0.1.0rc6`. Startup fails if the SDK
and bundled runtime versions differ. The keyless integration suite checks both
provider routes, the protocol, and the cleanup path. It does not establish a
model-quality or cost comparison against direct, tool-loop, or RLM treatments.

Run the registered pump-station world through DeepSeek Harness and Harbor:

```bash
uv run aec-bench task world pump-station run-harbor \
  --task-dir /path/to/exported-pump-task \
  --project-root . \
  --jobs-dir jobs/pump-deepseek \
  --config-path jobs/pump-deepseek.yaml \
  --backend modal \
  --adapter deepseek_harness \
  --model "azure:<deployment-name>" \
  --max-world-actions 90 \
  --max-tokens 8192 \
  --timeout-sec 1800
```

The model sees actor observations and actor actions only. One trial-wide actor
authority owns request replay, action order, the action budget, terminal state,
and semantic actor evidence across all model segments. The task-owned host can
apply its deterministic Operations controls between segments while the action
budget remains open. Harbor independently replays the final world run and owns
reward.

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

Use the public discovery and complete-trial API:

```python
from functools import partial

from aec_bench import worlds
from aec_bench.harness.dam_seepage_trial import run_dam_seepage_trial
from aec_bench.harness.prime_world_actor import run_prime_world_actor_session
from aec_bench.harness.world_trials import run_world_experiment
from aec_bench.trials import plan_trials

task = worlds.task(
    "dam-seepage-monitoring",
    profile="synthetic-rising-seepage",
    instruction="Monitor the dam and respond as conditions evolve.",
)
trials = plan_trials("dam-study", tasks=[task], agents=[prime_agent])
records = await run_world_experiment(
    tasks=[task],
    trials=trials,
    run_trial=partial(run_dam_seepage_trial, actor=run_prime_world_actor_session),
)
```

`WorldTask` contains the objective and exact registered world and profile.
`PlannedTrial` contains the agent, model, compute, limits, and repetition. The
trial function returns one evaluated `TrialRecord`; a world action or Prime
session is not a trial. The shared Prime actor function launches one ACP
process and installs the generic `aec-world` skill by default.
This is the Open treatment: Prime receives the objective, actor-visible
starting material, and generic actor capability, with no task-family method or
external plan.

The pump runner owns its persistent journey and host continuation. The dam task is one
bounded episode. It has no host control, journey, branch, or durable world
repository. After Prime closes, the host replays the accepted typed actions and
runs the existing dam evaluation outside the actor endpoint.

The caller can select the experimental Guided treatment explicitly:

```python
await run_pump_station_prime_session(
    ...,
    pump_station_guidance=True,
)
```

The caller can instead select the experimental Planned treatment:

```python
await run_pump_station_prime_session(
    ...,
    actor_ledger_plan=True,
)
```

Planned keeps exact actor-visible observations and action results in the actor
workspace, but returns only compact Python results. Prime can use bounded search
and window calls to inspect that saved data. Planned also loads Prime's
`agent-message` and bounded, read-only `agent-observe` skills so child sessions
can return compact findings. The root and all children still share one actor
capability and form one composite actor principal.

Open and Planned are available for both maintained world entries. Guided is a
pump-only treatment.

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

Planned installs `aec-world` and `aec-actor-ledger`, followed by the selected
Prime installation's `agent-message` and `agent-observe` skills. AECBench copies
these explicit skills into the isolated actor workspace and records their order
and content digests. Planned does not add observations, world actions, child
authority, host controls, or evaluator information.

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

The provider-neutral `WorldActorEndpoint` exposes only `capabilities`,
`observe`, and `invoke` through local protocol `aec-bench/world-actor/1`. It
connects to one task-owned pump or dam episode host. The pump host privately
binds its world repository; the dam host owns one in-memory episode. Prime never
receives a world run directory or host-control selector.

AECBench stages one standard-library `aec_world` client in the actor workspace.
The Prime `aec-world` skill contains only Prime-specific instructions. The same
client also has a JSON command interface:

```text
python -m aec_world capabilities
python -m aec_world observe
python -m aec_world invoke --action <name> --decision-id <id> --arguments-json '<json>'
```

The Prime root session and all descendants share one capability and are one
composite AECBench actor principal. `ActorInvocationAuthority` owns request
identity, exact retries, action order, the action budget, terminal state, and
semantic actor evidence. An exact retry uses the same request ID and does not
consume another allowance. If the client reports an `unknown` outcome, do not
submit the action under a new request ID. Endpoint or authority close that is
not complete prevents complete trial finalization.

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

The dam entry writes `prime-dam-seepage-run.json` instead of
`prime-world-run.json`. It records exact build and profile identity, the Open or
Planned treatment, accepted actions, Prime and world completion, replay
validity, and the separate task evaluation.

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

Use the meta-harness workflow to compare or refine harness candidates from
`TrialRecord` evidence. Python callers can use the runtime-neutral facade:

```python
from aec_bench.experimentation.meta_harness import run_harness_study

study = run_harness_study(
    baseline=baseline,
    candidates=candidates,
    evaluate=evaluate_candidate,
    assess=assess_candidates,
)
```

Candidate and assessment values remain caller-owned. The evaluator connects the
candidate to its artifact-task, lifecycle, or interactive-world runtime. The
core does not define a common runtime or persisted meta-harness format.

The CLI also supports a concrete problem-model workflow, reviewer evidence,
governance decisions, and candidate-versus-baseline comparison.

```bash
uv run aec-bench meta-harness recipe \
  --task-file task.md \
  --output artefacts/meta-harness/demo
```

The recipe writes a scriptable workspace for intake, problem-model generation, reviewer
evidence, governance, and comparison artifacts. Run
`aec-bench meta-harness --help` for the complete command surface.

### Finite Lifecycles

All finite lifecycle commands are under `aec-bench task lifecycle`:

```text
list                    list-variants
materialize             start
submit                  status
revisit                 branch
run                     verify
run-smoke               study ablation
study calibration-freeze
```

`start` releases the next checkpoint. `submit` records the active checkpoint.
`revisit` is read-only. `branch` creates a new run from a submitted checkpoint
and keeps the accepted prefix. `run` resumes from the current lifecycle state.
It does not accept a checkpoint start override.

Python callers use `LifecycleTrial`, `LifecycleExecution`,
`run_local_lifecycle()`, `run_lifecycle_trial()`, and
`run_lifecycle_experiment()`. Trial execution returns the created
`TrialRecord` directly and persists it only when the caller supplies a
persistence function.

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

Datasets separate semantic task selection from immutable byte identity. A
schema-2 manifest names the selected tasks. Publication then binds that
manifest to either a full Git commit or one verified detached bundle.

```bash
# Create a dataset from electrical tasks only
uv run aec-bench dataset create electrical-core --domain electrical

# Create from all tasks
uv run aec-bench dataset create full-bench

# Create from a suite.toml (records provenance)
uv run aec-bench dataset create generated-bench --config suite.toml

# Publish an immutable detached bundle under a human label
uv run aec-bench dataset publish electrical-core --label public-2026

# List datasets
uv run aec-bench dataset list

# Show dataset details and integrity status
uv run aec-bench dataset info electrical-core@public-2026

# Generate an experiment config from a dataset
uv run aec-bench dataset config electrical-core@public-2026 --model "<model-id>" -o experiment.yaml

# Verify integrity (for CI — exits 0 if clean, 1 if drifted)
uv run aec-bench dataset validate electrical-core@public-2026

# Export for sharing
uv run aec-bench dataset export electrical-core@public-2026 -o electrical-core.tar.gz

# Import a shared dataset
uv run aec-bench dataset import electrical-core.tar.gz
```

The typical workflow:

```bash
# 1. Create a dataset
uv run aec-bench dataset create electrical-core --domain electrical

# 2. Publish and resolve an immutable reference into the experiment config
uv run aec-bench dataset publish electrical-core --label public-2026
uv run aec-bench dataset config electrical-core@public-2026 --model "<model-id>" -o experiment.yaml

# 3. Run it
uv run aec-bench run --config experiment.yaml
```

The CLI can resolve a human label in an input config:

```yaml
tasks:
  dataset: "electrical-core@public-2026"
  difficulties: ["medium", "hard"]  # optional filter on top
```

Before planning, `aec-bench run` replaces that selector with the exact
`RepositoryDatasetRef` or `BundleDatasetRef`. Generated experiment configs
already contain that exact object. `latest` is rejected and is never persisted.

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

Published evaluation regimes use one artifact reference as their compatibility
identity. Inspect one regime or compare two regimes with semantic field paths:

```bash
uv run aec-bench evaluation regime show <artifact-id> --artifact-root <repository>
uv run aec-bench evaluation regime diff <artifact-id-a> <artifact-id-b> --artifact-root <repository>
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

### Evidence integrity

```bash
# Rebuild the disposable metadata index from portable trial records
uv run aec-bench evidence index rebuild --ledger-root artefacts/ledger

# Verify structured records and referenced exact bytes
uv run aec-bench evidence verify --ledger-root artefacts/ledger --run <run-id>
```

The index is a rebuildable SQLite projection. Portable records and artifacts
remain authoritative. Verification reads and checks those portable files; it
does not rewrite them.

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

The current Web API uses stable domain IDs in routine responses. Full artifact
SHA-256 values are available only through authenticated technical integrity
inspection, which verifies the retained bytes before it returns the digest.
Trial evidence inspection keeps actor, provider, World, lifecycle, and
evaluation authority references separate. Provider qualification inspection
shows the exact adapter, SDK, and runtime version set and keeps keyless proof
separate from live-provider evidence.

### Evolution Workspaces

Evolution workspaces use candidate IDs for lineage and full Git commits for
source. Git tags are optional immutable labels. History displays the Git commit
time; it does not create a new time when it reads old candidates.

Evolution runs use one functional cycle. The search selects a parent and any
inspirations. `CandidateChecks` then plans one shared batch and checks the exact
parent and child against it. A candidate proposer creates the child in scratch.
The search policy decides what to keep. The canonical workspace changes only
after acceptance.

The built-in proposer is bounded agentic variation (AVO). It runs one call in
scratch and returns `submitted`, `abstained`, or `budget_exhausted`. Cooperative
cancellation first stores an exact `cancelled` terminal checkpoint and then
raises `AVOCancellationError`. AVO never writes the canonical source material
or commits a candidate. The application owns final child checks, acceptance,
commit, archive, graveyard, and lineage effects.

Three names describe the evaluation purpose:

- **Selection checks** compare parent and child and decide which material can persist.
- **Revision checks** give AVO private feedback while it edits one candidate. They use public tasks.
- **Qualification checks** are a separate holdout run after development. They never adapt the candidate.

AVO plans one fixed public revision batch for each call, checks the selected
parent first, and then permits bounded scratch revisions. A submitted child is
the exact current revision with its own evidence. AVO
memory is bounded structured attempt evidence. The application can pass that
memory to the next proposal call; it does not change parent selection,
strategy, `EvolutionState`, `QDState`, or swarm decisions. See the
[architecture](docs/ARCHITECTURE.md), [contracts](docs/CONTRACTS.md), and
[invariants](docs/INVARIANTS.md) for the ownership and evidence rules.

The core `AVOBudget` defaults are 12 model requests, 40 tool calls, 7
revision evaluations, 1,800 seconds, two consecutive evaluation errors, three
stagnant evaluations, and zero advisor interventions. Token and cost limits are
optional. The composed AVO proposer enables one conditional advisor call by
default. A direct `run_avo` caller must provide an `advisor_runner` when it
enables interventions. An advisor receives only the bounded request fields, returns
one to three advisory directions or a confirmed output failure, and cannot
change outer search state. Advice stays inside that AVO call and is not part of
`CandidateProposal`.

Usage is fail-closed when a configured limit needs an unknown value. An
explicit `0.0` cost means free; `None` means unknown. The cycle record keeps
the full AVO usage, and an aggregate cost remains unknown when any used cost
plane is unknown. A durable call uses checkpoint schema `2` as its sole resume
authority. Resume rejects a changed run, AVO call, parent, selection,
revision-case order, budget, configuration identity, or scratch material;
an incomplete external effect must be reconciled before retry.

Direct search accepts a valid child until the configured stagnation window is
reached. Clearing the improvement threshold resets that counter and updates the
best candidate. QD accepts a valid child when it enters a new archive
cell or improves an occupied cell; global-best improvement is not required.
The QD host allocates mutation strategies with the strategy bandit and limits
the archive agent to the host shortlist and chosen strategy. Bandit feedback is
updated once from the archive outcome. Graveyard rescue uses only actual
rejected candidate material with a matching candidate ID.

Swarm agents receive exact `SwarmAssignment` values and return a proposal plus
agent cost. They do not score candidates or update the archive. Selection
checks evaluate parent and child, bind exact `TrialRecord` evidence, and apply
archive, graveyard, budget, and reducer effects. The async manager owns
concurrency. Its immutable `SwarmState` owns decisions, while the event log
reports them. Swarm state and candidate snapshots are persisted with the
archive and graveyard so the recorded candidate material remains resolvable.

Direct and QD runs keep selection authority and all effects in the host. Direct
runs select the parent in the host. QD keeps strategy and shortlist selection
in the host, then permits its archive agent to choose only within those
constraints. QD archive cells and strategy-bandit feedback remain in `QDState`;
AVO only proposes a child. Swarm composition gives each agent its own
workspace, candidate proposer, cancellation signal, call-local memory, and
checkpoint identity. The manager remains the owner of shared budget, archive,
graveyard, lineage, reducer, and pivot state.

Local provider-free tests prove the AVO protocol and deterministic boundaries.
They do not qualify a paid or hosted model route. Do not run paid provider or
hosted qualification until an explicit approval covers that run and its cost.

The YAML command is the shortest supported path. The Python API is for callers
that want to replace a check set or proposer without replacing the evolution
loop:

```python
from aec_bench.evolution import CandidateChecks, build_avo, build_local_checks, run_evolution

result = run_evolution(
    workspace=workspace,
    config=config,
    selection_checks=selection_checks,
    propose=propose,
)
```

`selection_checks` is one `CandidateChecks(plan=..., run=..., enrich=...)`
value. `propose` is any callable that accepts a `CandidateProposalRequest` and
returns a `CandidateProposal`. Use `build_local_checks(...)` and
`build_avo(...)` for the built-in local composition.

| API | Meaning |
| --- | --- |
| `CandidateChecks` | Plan and run one consistent set of candidate checks |
| `build_local_checks()` | Use local AEC-Bench tasks as a `CandidateChecks` value |
| `build_avo()` | Create the built-in candidate proposer |
| `gate_candidate()` | Return the pure accept, reject, or skip decision |
| `next_evolution_state()` | Return state after that decision, without effects |
| `run_evolution()` | Coordinate checks, proposals, decisions, and persistence |

Checkpoint schema `2` and usage records keep their existing `development_*`
and `supervisor_*` field names. These are protected wire names. The Python
composition uses the clearer revision-check and advisor terms.

```bash
# Create and run a workspace
uv run aec-bench evolve init ./my-workspace --name "My Agent"
uv run aec-bench evolve run --config ./my-workspace/evolution.yaml

# Inspect candidates or restore one by candidate ID or label
uv run aec-bench evolve history ./my-workspace
uv run aec-bench evolve rollback ./my-workspace <candidate-id-or-label>

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

| Skill | Claude Code | Codex | Purpose |
|-------|-------------|-------|---------|
| **Add Task** | `/add-task` | `$add-task` | Interview-driven seed creation from expert description |
| **Configure Experiment** | `/configure-experiment` | `$configure-experiment` | Select tasks, agents, models, and execution settings for a validated experiment manifest |
| **Create Dataset** | `/create-dataset` | `$create-dataset` | Build and verify a reproducible dataset from templates or existing tasks |
| **Create Template** | `/create-template <seed-path>` | `$create-template <seed-path>` | Build a generation template from a seed file |
| **Hardening Pass** | `/hardening-pass <path>` | `$hardening-pass <path>` | Quality-gate a template or task instance before benchmarking |
| **Domain Check** | `/domain-check` | `$domain-check` | Verify architectural invariants before publishing or committing |
| **Meta-Harness** | `/meta-harness` | `$meta-harness` | Design or compare a harness candidate from task prose and run evidence |

`aec-bench init` installs the packaged skills into `.claude/skills/` for Claude
Code and `.agents/skills/` for Codex. Run `aec-bench init --update-skills` in an
existing project to refresh both packaged copies without removing other skill
directories.

**Typical flow:** Add Task produces an expert-authored seed. For a
parameterisable task, Create Template builds the generation template and
Hardening Pass checks it before benchmark use. Create Dataset freezes a
reproducible selection, then Configure Experiment prepares the run.

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
`aec-bench library export --pretty` for the deterministic schema 2 public
catalogue.

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
seeds/                  # Expert-created seed files (from Add Task)
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
