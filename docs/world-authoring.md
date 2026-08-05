# ABOUTME: Routes contributors through the current artifact-task and interactive-world authoring paths.
# ABOUTME: Defines the minimum world touch points and maps conformance claims to real tests.

# World Authoring

| Field | Value |
| --- | --- |
| Class | Guide |
| Status | Current |
| Audience | Task and interactive-world contributors |
| Owner | Task-world owners and continual-world maintainers |

Choose the task family before changing code. An artifact task and an interactive
world have different state, evaluation, and registration owners.

| Question | Artifact or workspace task | Interactive world |
| --- | --- | --- |
| Main working state | Files, a submission, or a workspace | Task-owned domain state |
| Agent interaction | Create, edit, submit, or use bounded tools | Repeated observations and actions |
| Evaluation | Verify final artifacts and evidence | Evaluate state, trajectory, and artifacts |
| Minimum implementation | Template or task package plus verifier | State, actions, observation, transition, and evaluation |
| Runtime persistence | Workspace and trial artifacts | Optional episode or world recovery |
| Branching and rollout | Usually separate task copies | Optional declared capability |

## Artifact or workspace tasks

Use the existing task-generation path. Do not add an interactive runtime when
the result can be judged from submitted files or a bounded workspace.

1. Capture the task in the installed
   [`add-task`](../src/aec_bench/init/skill_data/add-task/SKILL.md) workflow.
2. For a parameterised calculation, follow
   [`create-template`](../src/aec_bench/init/skill_data/create-template/SKILL.md)
   and its [template contract](../src/aec_bench/init/skill_data/create-template/references/template-contract.md).
3. Keep the engine, parameter space, instruction, assets, and verifier with the
   task or template that owns them.
4. Validate the template, generate a task instance, then validate the generated
   task:

   ```bash
   uv run aec-bench generate validate-template <template-dir>
   uv run aec-bench generate task --template <template-dir> --instances 1 --seed 42 --output /tmp/aec-bench-preview
   uv run aec-bench task validate <generated-task-dir>
   ```

5. Submit the task package with its `task.toml`, `instruction.md`, verifier,
   fixtures, any declared output contract, and passing validation evidence.

Direct validation and `--template` loading are strict: an invalid requested
template fails. Template listing, suite generation, and public library export
use the same diagnostic discovery path, so invalid candidates are reported
without becoming catalogue entries. One validated load supplies the config,
engine, source path, and source digest used for sampling and materialization.

Generated `task.toml` records the template source SHA-256, seed, instance
index, difficulty, and visibility. It does not record ambient generation time
as lineage. The generated directory is the runnable artifact and the current
task loader validates it into `TaskDefinition`; the library catalogue remains
a projection from explicitly supplied public template and seed roots. This
calculation-template path does not apply to the interactive worlds below.

The root [README](../README.md#generate-tasks) owns the public CLI route. This
guide does not duplicate the task and template authoring instructions.

## Minimum interactive world

A minimum interactive world owns its engineering behavior. The episode host
owns the live decision sequence around that behavior.

| Concern | World or evaluation owner | Episode/runtime owner |
| --- | --- | --- |
| Scenario or profile | Task inputs and fixed behavior choices | Loads the selected profile |
| State | Current domain facts | Holds the current state for one episode |
| Actions | Task-valid action variants | Routes the submitted action |
| Observation | Actor-visible projection | Associates it with an opaque decision |
| Transition | Acceptance, rejection, output, and domain termination | Advances state and step after recording succeeds |
| Truncation | None | Limits and runtime interruption |
| Evaluation | Interprets state and selected evidence | Invokes it outside the live transition |
| Decision and retry | None | Decision identity, freshness, correlation, and retry |

The shared production values are
[`Transition` and `ActionRejected`](../src/aec_bench/task_world_templates/continual/world_logic.py).
There is no required `WorldLogic` class, base class, or global action union.

### 1. Define task-owned inputs and state

Keep scenario or profile inputs, one authoritative current state, and action
types in the task package. Validate untrusted JSON or files at their actual
boundary. Do not put episode IDs, opaque decisions, step indexes, repository
paths, provider metadata, or content digests in domain state.

The minimum real example is SSC-03 hydraulics:

- [`HydraulicSourceState`, `HydraulicRunRequest`, and `HydraulicTimeStep`](../src/aec_bench/task_world_templates/hydraulics/contracts.py)
  own the task input, action, and observation values;
- [`HydraulicWorldState`](../src/aec_bench/task_world_templates/hydraulics/kernel.py)
  is its authoritative state; and
- no pump session, recorder, rollout, or provider type is required by the
  hydraulic functional core.

Use ordinary dataclasses, enums, tuples, or validated boundary values that fit
the task. A live in-process value does not need a schema version or content
hash merely because a test serializes it.

### 2. Implement deterministic behavior

Provide direct task-owned functions for:

- initial state from the same profile and seed;
- an actor-visible observation derived from current state;
- a transition from current state and one task action; and
- evaluation outside transition execution.

SSC-03 implements these as
[`initial_hydraulic_world_state`, `observe_hydraulic_world`,
`transition_hydraulic_world`, and `evaluate_hydraulic_world`](../src/aec_bench/task_world_templates/hydraulics/kernel.py).

For the same state and action, transition behavior must be deterministic. A
rejection leaves state unchanged. A transition can terminate the domain, but
it must not persist files, call a provider, advance an episode step, calculate
runtime truncation, or perform the full evaluation.

Project observations explicitly. Do not expose the full state and depend on a
later filter to remove verifier-only facts or evidence the actor has not
acquired.

### 3. Register at the composition root

A registered world supplies a current
[`ContinualWorldDefinition`](../src/aec_bench/task_world_templates/continual/definition.py)
with its build, profile references, and profile loader. Add it once to
[`default_continual_world_catalogue`](../src/aec_bench/task_world_templates/continual_catalogue.py).
The catalogue rejects duplicate identities and does not own evaluation,
providers, Harbor, branches, or rollout execution.

A normal minimum contribution changes three ownership areas:

1. the task-owned implementation and definition;
2. the task-owned tests; and
3. the explicit catalogue composition root.

It does not require changes to the episode shell, actor or control contracts,
provider integrations, recorder internals, rollout repositories, pump
persistence, or training code. If one of those changes appears necessary,
identify the missing boundary before adding an adapter or facade.

### 4. Prove behavior at the owning boundary

Use the callable
[`assert_world_conformance`](../tests/task_world_templates/continual/world_conformance.py)
helper. It checks deterministic initialization and observation, safe rejection,
deterministic accepted transitions, optional boundary round trips, evaluation
determinism, and rejection after terminal state.

Add domain reference or property tests for the engineering behavior that can
change benchmark outcomes. SSC-03 proves stage-storage inversion and Rational
Method monotonicity in
[`test_hydraulic_world_conformance.py`](../tests/task_world_templates/continual/test_hydraulic_world_conformance.py).

Decision freshness, accepted-step advancement, recorder ordering, and runtime
truncation belong to the existing
[`Episode` tests](../tests/task_world_templates/continual/test_episode.py). Do
not reimplement those checks in every world.

## Optional capabilities

Add a capability only when a current product need requires it. A minimum world
does not carry placeholder ports for unsupported behavior.

| Capability | Current owner | Required proof | Minimum world |
| --- | --- | --- | --- |
| Host controls | Installed control boundary and task-owned control values | Authorization and registered-control tests | Omit |
| Durable recording and recovery | `EpisodeRecorder` plus the task persistence edge | Failure ordering, replay, and recovery tests | Use memory recording for shell tests |
| Snapshot and branch | Optional `ContinualWorldBranchPort` implementation | Identity, isolation, and recovery tests | Omit |
| Rollout groups | Rollout coordinator with an explicit branch capability | Child isolation, lineage, publication, and recovery tests | Omit |
| Temporal or staged evidence | Task or lifecycle owner | Visibility, provenance, and verifier tests | Omit |
| Harbor or provider packaging | Outward task adapter | Transport and import/export tests | Omit |
| Sealed lifecycle package | Independently consumed package boundary | Exact package and verifier checks | Omit |

The wastewater pump station is the advanced example. Its
[`PumpStationStewardshipState` and `PumpStationAction`](../src/aec_bench/task_world_templates/stewardship/wastewater_pump_station/stewardship_models.py),
task-owned functional core, durable recorder, root controls, temporal evidence,
branching, rollout, current-only persistence, and Harbor boundary show how
optional capabilities compose. Do not copy its package size or control surface
for a minimum world.

The [interactive-world runtime protocol](protocols/interactive-world-runtime.md)
is the authority for those runtime and transport boundaries.

## Local proof without credentials

Run the smallest commands that prove the changed boundary:

```bash
# One SSC-03 engineering property
uv run pytest tests/task_world_templates/continual/test_hydraulic_world_conformance.py::test_stage_storage_inverse_recovers_depth_within_tolerance -q

# Shared conformance and direct local evaluation
uv run pytest tests/task_world_templates/continual/test_hydraulic_world_conformance.py::test_ssc03_hydraulic_world_conforms_to_shared_values -q

# Registered focused integration
uv run pytest tests/task_world_templates/continual/test_hydraulic_world_conformance.py::test_registered_ssc03_lifecycle_operation_uses_hydraulic_transition -q

# Changed Python paths
uv run ruff check <changed-python-paths>
uv run ruff format --check <changed-python-paths>
uv run mypy <changed-production-boundary>

# Documentation ownership and links
uv run pytest tests/docs/test_documentation_ownership.py -q
```

These tests run locally without Harbor, provider credentials, or paid services.

## Contribution checklist

- [ ] Select the artifact/workspace or interactive-world family.
- [ ] Classify task-owned, host-owned, actor-visible, and verifier-only facts.
- [ ] Keep one authoritative domain state and task-owned action types.
- [ ] Keep actor actions separate from host controls.
- [ ] Make seed, time, ordering, and outcome-affecting randomness explicit.
- [ ] Exclude hidden facts and unacquired evidence from observations.
- [ ] Leave state unchanged when rejecting an action.
- [ ] Keep domain termination distinct from runtime truncation.
- [ ] Keep evaluation outside the live transition.
- [ ] Pass shared conformance and applicable domain-property tests.
- [ ] Add one explicit composition-root registration.
- [ ] Justify and test each optional capability; otherwise omit it.
- [ ] Name any protected artifact or external protocol affected by the change.
- [ ] Require no provider or paid service for the local proof.
- [ ] Add no global action union, compatibility layer, live schema version, or
      content hash without a real protected boundary.
- [ ] Update the maintained documentation or explicit composition root when required.
