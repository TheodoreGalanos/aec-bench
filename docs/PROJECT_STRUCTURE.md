# ABOUTME: Provides stable navigation and ownership guidance for the AEC-Bench repository.
# ABOUTME: Avoids volatile package inventories while locating source, task worlds, tests, docs, and artifacts.

# Project Structure

| Field | Value |
| --- | --- |
| Class | Guide |
| Status | Current |

This is a navigation guide, not a physical inventory. Use `rg --files` and the
live package tree when exact paths matter.

## Repository map

| Path | Stable responsibility |
| --- | --- |
| `src/aec_bench/` | Installed Python library, CLI, runtimes, evaluation, persistence, and presentation code |
| `tests/` | Permanent unit, contract, integration, and public-surface coverage |
| `tasks/` | Runnable benchmark task packages and task-owned assets |
| `seeds/` | Expert-authored task sources used to create or extend templates |
| `agents/` | The repository-owned Harbor execution entrypoint |
| `scripts/` | Maintained repository commands that are not installed API surfaces |
| `docs/` | Current repository design authorities, protocols, guides, and selected history |
| `assets/` | Repository and public-presentation assets |
| `typings/` | Local type information needed by static checks |
| `.github/workflows/` | Automated repository checks and build workflows |

`pyproject.toml`, `uv.lock`, and the frontend lockfile own dependency and tool
configuration. The root `README.md` owns the concise public setup and command
surface.

## High-level source ownership

The installed package groups code by responsibility:

- Contracts validate real external, persisted, untrusted, or cross-process
  boundaries. They are not a universal application layer. Import a contract
  from its owning module; `aec_bench.contracts` deliberately exports no
  contract symbols.
- Task loading, templates, generation, and datasets own authoring, compilation,
  deterministic generation, and benchmark snapshot identity.
- Tasks, templates, lifecycles, and worlds keep the calculations and technical
  verifiers that define their own benchmark behaviour. Extract shared domain
  code only when two real owners use the same stable behaviour.
- `worlds` owns interactive-world runtime behavior, concrete world semantics,
  and packaged world data. `worlds/catalogue.py` is the composition root and
  does not move task behavior into the shared runtime.
- `lifecycles` owns finite staged progression, checkpoint operation protocols,
  concrete lifecycle definitions, and lifecycle compilation.
- Adapters, agents, providers, and `harness` own model execution, process
  coordination, and compute integration without taking over task semantics.
- Evaluation owns scoring, validity interpretation, diagnostics, and
  task-specific evaluation extensions.
- Ledger and artifact modules own persistence and retrieval mechanics.
- CLI, TUI, web, communication, and export modules present or compose lower
  layers.
- `experimentation` owns proposals, governance, qualification, lifecycle
  studies, and maintained research experiments. The public `meta-harness` CLI
  composes these owners; there is no matching umbrella source package.

See [Architecture](ARCHITECTURE.md) for current flows and dependency direction.

## Task-owned world code

Reusable interactive-world behavior lives under
`src/aec_bench/worlds/runtime/`. Concrete state, action, control, event,
projection, physics, and verifier semantics live under their world family.
`src/aec_bench/worlds/catalogue.py` may import concrete definitions; the
task-neutral runtime must not.

Do not move a pump or other task field into the shared runtime to
avoid passing an opaque task-owned value through its registered port.

## Test ownership

Tests follow the behavior they prove:

- contract tests sit near the contract family under `tests/contracts/`;
- source-domain tests mirror the owning source area when that improves
  discoverability;
- task-world behavior remains under its task-world test family;
- provider parity and end-to-end tests exist only where lower layers cannot
  prove the boundary; and
- reusable fixtures and factories belong under `tests/support/`.

Test names describe stable behavior, contracts, or failure modes. They do not
preserve delivery phases or migration step names.

## Generated, published, and research artifacts

Generated task instances, runs, jobs, trial artifacts, ledgers, and dataset
snapshots are runtime output under configured roots. They are not edited as
source. Published datasets and accepted trial or evidence artifacts can be
immutable even when their local generation workspace is disposable.

The ignored `research/` tree and temporary output directories may hold
experiments and evidence. Product source, packaging, permanent tests, and
builds must work when those directories are absent. Move any required
generator, certifier, migration, fixture, or data file to its permanent owner.

## Dependency rules

- Task definitions and task worlds do not depend on adapters or providers.
- Shared runtime packages do not import concrete task worlds.
- Provider SDKs stay behind adapter, provider, compute, or transport
  boundaries.
- Persistence does not import scoring policy.
- Evaluation does not depend on reports, the TUI, or the web UI.
- Presentation layers consume established contracts and results; they do not
  define competing metrics.
- Composition roots may assemble lower-level implementations but must not move
  domain policy into the registration layer.

The focused rules above are enforced by `tests/test_package_ownership.py`.
Keep enforcement explicit and standard-library based; do not add a dependency
graph framework or plugin registry for package layout.

Add a new top-level directory or package only when it owns a stable
responsibility that does not fit an existing owner.

## Related documents

- [Documentation index](README.md)
- [Architecture](ARCHITECTURE.md)
- [Boundary contracts](CONTRACTS.md)
- [Benchmark invariants](INVARIANTS.md)
