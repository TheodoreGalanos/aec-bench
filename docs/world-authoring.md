# ABOUTME: Routes contributors through the current artifact-task and interactive-world authoring paths.
# ABOUTME: Defines the minimum world implementation and the proof required at each owning boundary.

# World Authoring

| Field | Value |
| --- | --- |
| Class | Guide |
| Status | Current |
| Audience | Task and interactive-world contributors |
| Owner | Task, world, and lifecycle owners |

Choose the task family before changing code.

| Question | Artifact or workspace task | Interactive world |
| --- | --- | --- |
| Working state | Files, a submission, or a workspace | Task-owned domain state |
| Agent interaction | Create, edit, submit, or use bounded tools | Repeated observations and actions |
| Evaluation | Verify submitted artifacts and evidence | Evaluate state, trajectory, and artifacts |
| Minimum implementation | Task package or template plus verifier | State, actions, observation, transition, and evaluation |

## Artifact and workspace tasks

Use the existing task-generation path when submitted files or a bounded
workspace are sufficient.

1. Use the installed
   [`add-task`](../src/aec_bench/init/skill_data/add-task/SKILL.md) workflow.
2. For parameterised calculations, follow
   [`create-template`](../src/aec_bench/init/skill_data/create-template/SKILL.md)
   and its [template contract](../src/aec_bench/init/skill_data/create-template/references/template-contract.md).
3. Keep the engine, parameters, instructions, assets, and verifier with their
   task or template owner.
4. Validate the template, generate one instance, and validate that task:

   ```bash
   uv run aec-bench generate validate-template <template-dir>
   uv run aec-bench generate task --template <template-dir> --instances 1 --seed 42 --output /tmp/aec-bench-preview
   uv run aec-bench task validate <generated-task-dir>
   ```

The generated directory is the runnable artifact. Its `task.toml` records
source identity, seed, instance index, difficulty, and visibility. The root
[README](../README.md#generate-tasks) owns public CLI instructions; this guide
does not duplicate the full task-authoring workflow.

## Minimum interactive world

The world owns engineering behaviour. The episode host owns the decision
sequence around it.

| Concern | World or evaluation owner | Episode host owner |
| --- | --- | --- |
| State and actions | Domain facts and task-valid actions | Current state for one episode |
| Observation | Actor-visible projection | Opaque decision association |
| Transition | Acceptance, rejection, output, and domain termination | Recording and accepted-step advancement |
| Truncation | None | Limits and runtime interruption |
| Evaluation | Meaning of state and verified evidence | Invocation outside live transition |
| Retry | None | Decision freshness and request correlation |

Shared transitions use
[`Transition` and `ActionRejected`](../src/aec_bench/worlds/runtime/world_logic.py).
There is no required world base class, universal protocol, or global action
union.

### 1. Own the domain values

Keep scenario inputs, one authoritative state, observations, and action types
with the task. Validate untrusted JSON or files at their real boundary. Do not
put episode IDs, opaque decisions, step indexes, repository paths, provider
metadata, or content digests in domain state.

The current registered examples are:

- [`stewardship_models.py`](../src/aec_bench/worlds/stewardship/wastewater_pump_station/stewardship_models.py)
  owns its authoritative task state;
- [`coupled_runtime.py`](../src/aec_bench/worlds/stewardship/wastewater_pump_station/coupled_runtime.py)
  owns task transitions and actor observations; and
- [`evaluation.py`](../src/aec_bench/worlds/stewardship/wastewater_pump_station/evaluation.py)
  owns task evaluation.
- [`dam_seepage/world.py`](../src/aec_bench/worlds/monitoring/dam_seepage/world.py)
  owns a separate monitoring state, evidence actions, actor observation, and
  evaluation without pump persistence or controls.

Both functional cores have no session, recorder, rollout, or provider type.

Use ordinary dataclasses, enums, tuples, or validated boundary values. Live
in-process values do not need schema versions or content hashes.

### 2. Implement deterministic behaviour

Provide direct task-owned functions for initial state, actor-visible
observation, transition, and evaluation. A rejection leaves state unchanged.
A transition may terminate the domain, but it does not persist files, call a
provider, advance the episode step, decide truncation, or perform evaluation.

Project observations explicitly. Hidden verifier facts and unreleased
evidence must never enter the actor view.

### 3. Register once

A registered world supplies a
[`InteractiveWorldDefinition`](../src/aec_bench/worlds/runtime/definition.py)
with build identity, profile references, and a profile loader. Add it once to
[`default_interactive_world_catalogue`](../src/aec_bench/worlds/catalogue.py).

A minimum contribution normally changes only the task-owned implementation,
its tests, and the catalogue composition root. It does not require episode,
actor-contract, provider, recorder, rollout, or persistence changes.

### 4. Prove the owning boundaries

Use
[`assert_world_conformance`](../tests/worlds/world_conformance.py)
for deterministic initialization and observation, safe rejection,
deterministic accepted transitions, optional boundary round trips, evaluation,
and terminal rejection. Add task-owned reference or property tests for
engineering behaviour that can change benchmark outcomes.

Decision freshness, recorder ordering, limits, and truncation belong to the
existing [episode tests](../tests/worlds/runtime/test_episode.py),
not every world test suite.

## Optional capabilities

Add only capabilities with a current consumer. A minimum world carries no
placeholder ports.

| Capability | Owner | Minimum world |
| --- | --- | --- |
| Host controls | Installed control boundary and task values | Omit |
| Durable recovery | Recorder and task persistence edge | Omit |
| Snapshot, branch, and rollout | Explicit branch implementation and rollout owner | Omit |
| Staged evidence | Lifecycle owner | Omit |
| Harbor or provider packaging | Outward task adapter | Omit |

The wastewater pump station is the advanced example. Its controls, durable
recording, temporal evidence, branching, rollout, and Harbor integration are
capabilities to justify independently, not a template for minimum worlds. See
the [interactive-world runtime protocol](protocols/interactive-world-runtime.md).

## Local proof

```bash
uv run pytest tests/worlds/monitoring/dam_seepage/test_world.py -q
uv run pytest tests/worlds/test_pump_station_world_conformance.py -q
uv run pytest tests/worlds/runtime/test_episode.py -q
uv run ruff check <changed-python-paths>
uv run ruff format --check <changed-python-paths>
uv run mypy <changed-production-boundary>
uv run pytest tests/docs/test_documentation_ownership.py -q
```

The proof must run without Harbor, provider credentials, or paid services.
Before handoff, confirm one authoritative state, explicit visibility,
unchanged-state rejection, separate termination and truncation, evaluation
outside transition, one registration, and a real consumer for every optional
capability.
