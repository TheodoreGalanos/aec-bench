# ABOUTME: Repository-wide guidance for coding agents working on AEC-Bench.
# ABOUTME: Protects benchmark validity while keeping implementation changes direct, simple, and replaceable.

# AEC-Bench Agent Guide

## Project purpose and status

AEC-Bench is a Python platform for creating, running, and evaluating Architecture, Engineering, and Construction benchmark tasks for AI agents.

- The project is pre-1.0 and is being actively simplified.
- Python support starts at 3.13; the repository currently pins Python 3.13.2.
- The main CLI entry point is `aec-bench`, implemented by `aec_bench.cli.main:run`.
- The optional Web UI uses FastAPI and a Svelte/Vite frontend.
- The benchmark objective order is:
  `validity > reproducibility > coverage > cost > throughput`.
- When those objectives are equal, prefer the simpler final system.

Do not preserve obsolete code, package structure, or documentation only because it already exists. The task is to leave the current system coherent, not to preserve its full history.

## Communication and language

- Use ASD-STE100 Simplified Technical English for all AEC-Bench work. This rule applies to progress updates, reviews, handoffs, documentation, issues, and pull requests.
- Keep code identifiers, commands, paths, schemas, error messages, and quoted source text exact. Do not rewrite these technical literals to follow ASD-STE100.

## Start with the relevant authority

Read the implementation and tests for the area you will change. Then read only the documents that govern that change:

- `docs/README.md`: documentation taxonomy, status, ownership, and routing.
- `docs/INVARIANTS.md`: non-negotiable benchmark-validity and reproducibility rules.
- `docs/CONTRACTS.md`: logical data contracts at real domain boundaries.
- `docs/ARCHITECTURE.md`: domain ownership and dependency direction.
- `docs/world-authoring.md`: current contributor path for artifact tasks and interactive worlds.
- `README.md`: documented public commands, installation, and user-visible behaviour.
- `pyproject.toml`: Python dependencies, build configuration, and tool settings.
- `docs/PROJECT_STRUCTURE.md`: navigation and design context, not a requirement to preserve obsolete packages or paths.
- Planning, work-item, research, and draft documents: context only unless the task explicitly selects them as requirements.

Use this order when sources disagree:

1. The current task and its accepted behaviour.
2. Applicable invariants and boundary contracts.
3. Explicit documented public behaviour and supported persisted formats.
4. Current implementation and tests as evidence of existing behaviour.
5. Planning documents and historical structure descriptions.

Do not resolve a conflict by supporting both old and new behaviour. Identify the intended authority, implement one path, and update the other sources in the same change. An old test is evidence, not an automatic compatibility promise.

## Repository map

- `src/aec_bench/`: production Python package.
- `tests/`: Python regression, integration, boundary, and public-surface tests.
- `tasks/`: benchmark tasks and task-owned assets.
- `seeds/`: expert-authored task seeds.
- `agents/`: ready-to-use Harbor agent implementations.
- `docs/`: repository-owned architecture, contracts, invariants, and project guidance.
- `scripts/`: local maintenance and workflow scripts.
- `src/aec_bench/web/frontend/`: Svelte/Vite frontend source.
- `typings/`: local type stubs used by mypy.
- `.github/workflows/`: automated checks. A workflow may cover only one area; its presence is not proof of full repository verification.

Prefer a short stable map like this over copied package inventories or test counts, which become stale quickly.

## Commands

Run commands from the repository root unless a command changes directory.

### Python setup and checks

- Install development dependencies: `uv sync --extra webui --dev`
- Run one test: `uv run pytest tests/path/test_file.py::test_name -q`
- Run tests for one area: `uv run pytest tests/path/ -q`
- Run the full Python test suite: `uv run pytest tests/ -q`
- Lint core Python: `uv run ruff check src/ tests/`
- Check core formatting: `uv run ruff format --check src/ tests/`
- Format changed Python paths: `uv run ruff format <paths>`
- Run strict type checking: `uv run mypy`
- Build the Python package: `uv build`

When Python outside `src/` or `tests/` changes, include those changed paths in the relevant Ruff command.

### Frontend checks

Run these from `src/aec_bench/web/frontend/`:

- Clean install from the lockfile: `npm ci`
- Update dependencies intentionally: `npm install`
- Run frontend tests: `npm test`
- Build the frontend: `npm run build`
- Start Vite development mode: `npm run dev`

A release build must compile the frontend before `uv build`, because the package includes `src/aec_bench/web/frontend/dist/` as a build artifact.

### Commands with external effects

Commands that run models, hosted evaluation, Harbor backends, Modal, Morph Cloud, Prime, or provider APIs can require credentials, network access, containers, or paid services.

- Prefer `--dry-run` when the command supports it.
- Do not run a paid, hosted, production-like, or credentialed workflow unless the task requires it and Theo has authorised it.
- Do not infer success from a dry run. State exactly what was and was not exercised.

## Compatibility policy

AEC-Bench is pre-1.0. There is no general backward-compatibility promise for internal implementation.

### Internal and unreleased behaviour

- Do not preserve backward compatibility for private modules, internal APIs, helpers, fixtures, unreleased schemas, temporary formats, or generated local data unless the task explicitly requires it.
- Update all repository callers directly.
- Remove obsolete paths instead of adding compatibility shims, fallback branches, deprecation layers, dual implementations, or `v2` copies.
- Do not retain old behaviour only because an existing test, private import, or historical document references it.
- Regenerate disposable local and test artifacts instead of writing migrations for them.

### Protected boundaries

Treat a boundary as supported only when it is explicitly documented or used outside the repository. Examples include:

- documented CLI commands and options;
- published dataset, trial, evidence, or export formats;
- persisted records that users must retain;
- external provider and Harbor protocols;
- deliberately documented Python exports;
- public-versus-holdout visibility rules.

Ask Theo before breaking a protected boundary. When an approved change affects supported persisted data, use the smallest migration or conversion that protects real data. Do not generalise that migration machinery to internal state.

## Domain immutability is not implementation immutability

AEC-Bench has real immutable and append-only domain artifacts. That requirement is narrow.

- Preserve append-only or immutable semantics for trial evidence, benchmark datasets, provenance records, and ledger artifacts where the contracts or invariants require them.
- Do not apply those semantics to the whole codebase.
- Source code, internal APIs, tests, configuration, documentation, service objects, and in-memory application state are not an immutable ledger.
- Replace and delete obsolete implementation instead of recording every historical form.
- Do not introduce event sourcing, command/event separation, replay infrastructure, audit logs, snapshots, versioned internal state, or receipt objects unless the current product requirement needs them.
- Do not model every mutation as a new immutable object when direct state is simpler and correct.
- Use immutable value objects only when value semantics, hashing, concurrency safety, or artifact integrity gives a concrete benefit.

When changing the ledger or dataset domains, preserve their explicit integrity rules. Do not copy their architecture into unrelated domains.

## Architecture and boundary rules

- Dependencies flow from foundational contracts toward higher-level orchestration and presentation. Do not import upward to avoid passing an explicit dependency.
- Put Pydantic models at actual domain or external boundaries. Do not create boundary models for local intermediate values only for uniformity.
- Use `StrictModel` for validated internal contracts and `LenientModel` only where an external upstream system may add fields.
- Keep task definitions provider-neutral.
- Adapters translate provider or execution protocol. They do not contain task-specific branches, rewrite task intent, select benchmark policy, or score outputs.
- Evaluation owns scoring and behavioural analysis.
- Ledger code owns persistence and queries, not evaluation policy.
- Communication and presentation surfaces report established results. They do not invent a second metric definition.
- State that can change benchmark outcomes must be explicit and reproducible. Ordinary implementation details do not need to become persisted provenance.
- Keep public and holdout material separate. Holdout content must not enter public catalogues, examples, reports, or generated documentation.

These rules protect domain ownership. They do not require one class, service, or package per concept.

### Continual-world changes

- Read `docs/protocols/interactive-world-runtime.md` before changing a persistent, replayable, branchable, or controllable task world.
- Do not add a task-specific run, repository, session, rollout, Harbor, replay, or evaluation stack when the world type already has one.
- Keep actor actions and host controls in separate validated envelopes.
- Keep state, action semantics, events, projections, and verifier rules with the task world. The runtime may store and route them, but it must not interpret task fields.
- Register world definitions at the composition boundary. Do not add task-stage branches to agents, adapters, CLI dispatch, Harbor, or evaluation.
- Before shared-runtime promotion, record ownership and migration, then prove one stable contract with two real task consumers. A mock, duplicate wrapper, or second profile is not a second consumer.
- Stop for architecture review if a change needs a second durable repository, run type, replay path, combined actor/control interface, or transport bridge.
- Move useful coverage before an old path is retired. Preserve accepted artifact bytes and replay results during migration.

### Delivery ownership

Before pull request completion, place each maintained artifact under its permanent owner:

| Artifact | Permanent owner |
|---|---|
| Shared library or runtime behaviour | `src/aec_bench/` |
| Task-template behaviour or data | `src/aec_bench/templates/<family>/` |
| Shared engineering capability | `src/aec_bench/engineering/<family>/` |
| Interactive world behaviour or data | `src/aec_bench/worlds/<family>/` |
| Lifecycle behaviour or data | `src/aec_bench/lifecycles/<family>/` |
| Maintained experiments and qualification | `src/aec_bench/experimentation/` |
| Maintained repository command | `scripts/`, unless it is part of the installed API |
| Permanent tests and test support | `tests/` |
| Normative architecture and operating guidance | `docs/` |
| Notes, generated evidence, and temporary output | Local ignored research or output storage |

Do not deliver maintained code from a research, planning, output, or phase directory. A rarely run generator or certifier is maintained code when the current system needs it. The feature must still build, package, test, and run when local research and phase directories are absent.

## Implementation policy

- Choose the simplest coherent implementation that fully meets current requirements, including required validation, errors, and reliability.
- Optimise for the simplicity of the resulting system, not only for a small diff.
- Modify the existing execution path unless the requirement truly needs a separate path.
- Remove superseded code, tests, comments, adapters, flags, and configuration in the touched scope.
- Do not keep old and new implementations in parallel as insurance.
- Avoid speculative abstractions, plugin systems, registries, factories, managers, service layers, configuration options, and extension points.
- A new abstraction must represent a real boundary, repeated policy, or established repository pattern. One caller is normally not enough.
- Build the smallest working end-to-end increment. Verify it before expanding the design.
- Do not land unused scaffolding or half-integrated infrastructure for a later task.
- Each increment may replace and simplify the previous design. Incremental delivery does not mean permanent layering.
- When requirements are uncertain, choose the simplest reversible decision.
- Prefer a simple design that can change over a complex design that tries to predict future change.
- A temporary measure is acceptable only when the task requires it. State its scope and removal condition; do not quietly turn it into architecture.

## Dependencies

Use this preference order when it fits the problem:

1. An existing repository capability.
2. The Python or browser platform standard library.
3. An existing project dependency.
4. A small direct local implementation.
5. A new dependency.

Before concluding that an installed library lacks a capability, inspect:

- the version in `pyproject.toml`, `uv.lock`, `package.json`, or `package-lock.json`;
- its local types and API;
- its official documentation for that version;
- how the repository already uses it.

Prefer an established, actively maintained library when it materially reduces total implementation, maintenance, or reliability risk. Do not reimplement complex parsers, protocols, cryptography, authentication, or security-sensitive standards without a clear reason.

Ask Theo before adding, replacing, or substantially upgrading a production dependency. A dependency must reduce total system complexity, not only local lines of code. Update lockfiles through `uv` or `npm`; do not edit them by hand.

## Testing policy

- Test changed behaviour.
- Name test modules, classes, and functions after stable behaviour, contracts, boundaries, or failure modes. Do not name them after delivery stages, milestones, or temporary work items.
- For a bug fix, add or identify a regression test that demonstrates the defect when practical.
- Use the lowest test layer that proves the behaviour.
- Add integration or end-to-end coverage only when the change crosses those boundaries or cannot be proved below them.
- Focused fakes, stubs, recorded fixtures, and replay clients are valid at external boundaries. Do not add a production mock mode or fake-success path.
- Default tests must be deterministic and must not require paid services, production credentials, or live model providers.
- Prefer factories and helpers in `tests/support/` over repeated setup.
- Mirror the source package structure in `tests/` when it improves discoverability; do not preserve empty test hierarchy only for symmetry.
- Run targeted tests during implementation. Run the broader checks appropriate to the changed boundary before handoff.
- For frontend changes, run the relevant Vitest tests and a frontend build.
- For package, public-surface, or release-manifest changes, run the relevant top-level tests and `uv build`.
- For documentation-only changes, validate links, commands, and referenced behaviour; do not run unrelated test layers by ritual.
- Do not weaken assertions, suppress diagnostics, or disable functionality only to make checks pass.
- If an intended change makes a test obsolete, update or remove the test. Do not preserve obsolete production code for it.
- Report pre-existing failures separately from failures caused by the change.
- Do not record a fixed test count in instructions or documentation.

## Generated, local, and packaged files

- Do not edit generated output by hand. Change the source or generator and regenerate it.
- `src/aec_bench/web/frontend/dist/` is generated by `npm run build` and is included in package builds.
- `tasks/generated/`, `jobs/`, `runs/`, `artefacts/`, local workspaces, and sealed local packages are execution output, not hand-maintained source.
- `uv.lock` and `src/aec_bench/web/frontend/package-lock.json` are tool-managed lockfiles.
- Do not commit credentials, local caches, downloaded provider output, or ignored run artifacts.
- Do not edit vendored or generated material merely to make style checks pass.

## Python and file conventions

- Use Python 3.13 syntax and complete type annotations on function signatures.
- Ruff uses a line length of 120 and the configured `E`, `F`, `I`, `B`, and `UP` rule sets.
- New hand-written Python files must begin with two `# ABOUTME:` lines that explain the file's purpose. Put required shebangs or encoding declarations first.
- Keep the header when substantially rewriting an existing Python file, but do not edit unrelated files only to add one.
- Do not add these headers to JSON, YAML, TOML, generated files, lockfiles, data files, or formats that do not support them.
- Match the local style of TypeScript, Svelte, Markdown, task data, and configuration files.
- Comments explain intent, domain constraints, or non-obvious decisions. Update or remove comments that become stale or redundant.
- Use evergreen names. Do not create `new`, `improved`, `enhanced`, `legacy`, or version-suffixed implementations to avoid replacing the current one, unless the name is part of a real external version contract.

## Documentation policy

Treat repository documentation as a set of scoped contracts, not as an append-only design diary.

- Update `README.md` when public setup, commands, or user-visible behaviour changes.
- Update `docs/CONTRACTS.md` when a logical boundary contract changes.
- Update `docs/INVARIANTS.md` only when a benchmark guarantee changes deliberately.
- Update `docs/ARCHITECTURE.md` when durable domain ownership or dependency direction changes.
- Update `docs/PROJECT_STRUCTURE.md` only for stable physical layout decisions. Do not use it to list every current package.
- Keep planning and research separate from normative current behaviour.
- New design documents must state whether they are normative, draft, research, or historical.
- Use `MUST`, `MUST NOT`, and `NEVER` only for genuine validity, security, data, or external-contract requirements.
- Prefer links to one authority over duplicated rules, command lists, package trees, or test counts.
- Describe the system as it is meant to operate now. Remove superseded guidance instead of preserving a chronology inside normative documents.

## Security and benchmark integrity

- Keep real credentials in `.env`; commit only placeholders in `.env.example`.
- Never print, copy, commit, or expose tokens, private keys, provider secrets, or secret environment values.
- Treat task packages, provider responses, imported jobs, archives, and external API data as untrusted input at their ingestion boundaries.
- Do not inspect, expose, or copy holdout or sealed evaluation content unless the task explicitly authorises that access.
- Preserve provenance needed to reproduce reported benchmark results.
- Do not claim a run, evaluation, build, or integration works when only a stub, dry run, or disabled path was exercised.

## Git and delivery

- Do not commit, push, publish, release, deploy, or run hosted evaluations unless Theo asks for that action.
- Never bypass configured checks or hooks with `--no-verify` or an equivalent mechanism.
- Do not include unrelated working-tree changes in a commit.
- Before a requested commit, run the relevant targeted checks and the broader repository checks appropriate to the changed files.
- Release and dependency-publishing actions always require explicit approval.

## Handoff

Report:

- the behaviour changed;
- the important files changed;
- obsolete paths removed;
- checks run and their results;
- any approved public contract, persisted format, or dependency change;
- material assumptions, limitations, and unresolved failures.

Do not claim a check passed unless you ran it and observed a passing result.

## Nested instructions

- `docs/AGENTS.md` applies only to work inside `docs/` and must stay documentation-specific.
- Add another nested `AGENTS.md` only when a subsystem has materially different commands, generated-file rules, security boundaries, or conventions.
- Do not copy the repository guide into nested files. State only the local differences.
