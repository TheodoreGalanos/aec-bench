# AEC-Bench Extension Authoring

| Field | Value |
| --- | --- |
| Class | Guide |
| Status | Current |
| Audience | Contributors adding tasks, worlds, lifecycles, or execution backends |
| Owner | Repository maintainers and domain owners |

This guide is the short route for adding a maintained AEC-Bench extension. Use
the domain guide linked in each section for detailed contracts and examples.

## Task

Use the [add-task workflow](../src/aec_bench/init/skill_data/add-task/SKILL.md)
to create the task package. For a parameterised calculation, use the
[create-template workflow](../src/aec_bench/init/skill_data/create-template/SKILL.md).
Keep the task instructions, environment, verifier, and task-owned assets in
the task or template package.

Give the task a readable key, a UUIDv7 identity, and a positive version. Set
its lifecycle and visibility in `task.toml`. Validate the package before
review:

```bash
uv run aec-bench task validate <task-dir>
```

The [world authoring guide](world-authoring.md) explains the task-family
choice and the complete generation and validation path.

## Interactive world

Keep the state, actions, observations, transitions, and evaluation with the
world owner. Put episode limits, decision freshness, recording, and provider
execution at the host boundary. A world owner provides:

1. An `InteractiveWorldDefinition` with build identity, profiles, and profile
   metadata.
2. One `InteractiveWorldOwnerDescriptor` in the owner package.
3. One `WorldConformanceCase` from the owner-local conformance entry point.

Add the owner import to
[`src/aec_bench/catalogue.py`](../src/aec_bench/catalogue.py), then update the
generated composition with:

```bash
uv run aec-bench catalogue build
uv run aec-bench catalogue check
uv run aec-bench conformance world <world-key>
```

The world key in the conformance command is the readable key used by the
owner case, such as `monitoring/dam-seepage`. See
[World Authoring](world-authoring.md) and the
[interactive-world runtime protocol](protocols/interactive-world-runtime.md)
for the state and host boundaries.

## Lifecycle

Keep the lifecycle metadata, checkpoints, materializer, verifier, executable
source roots, and variants with the lifecycle owner. A lifecycle owner
provides:

1. A `LifecycleDefinition` with a UUIDv7 identity, readable key, positive
   version, and template ID.
2. One `LifecycleOwnerDescriptor` from the owner package.
3. One `LifecycleConformanceCase` from the owner-local conformance entry
   point.

Add the owner import to
[`src/aec_bench/catalogue.py`](../src/aec_bench/catalogue.py), then build and
check the generated composition:

```bash
uv run aec-bench catalogue build
uv run aec-bench catalogue check
uv run aec-bench conformance lifecycle <lifecycle-key>
```

The [staged evidence protocol](protocols/staged-evidence-and-publication.md)
defines checkpoint, visibility, and publication behaviour.

## Harbor backend

Implement the scheduler-facing backend boundary in
[`src/aec_bench/harness/harbor_backend.py`](../src/aec_bench/harness/harbor_backend.py).
Bind each submitted work item to its planned trial and preserve that identity
through submission, inspection, collection, cancellation, reconciliation,
attempt receipts, and finalization.

Declare the backend capabilities required by the scheduler. Add a provider-free
`HarborBackendConformanceCase` using the shared checks in
[`src/aec_bench/harness/harbor_conformance.py`](../src/aec_bench/harness/harbor_conformance.py),
then run the focused backend tests:

```bash
uv run pytest tests/harness/test_harbor_backend.py -q
```

Use a focused client fake at the transport boundary. The conformance case
must exercise successful collection, repeated collection, unknown remote
state, cancellation, retryable and terminal failures, persisted transport
fields, and wrong-identity rejection.

## Catalogue review

The catalogue source is the explicit owner list. The generated Python modules
are checked-in composition output. Build a JSON snapshot when reviewing a
catalogue change and compare a later build with:

```bash
uv run aec-bench catalogue build --snapshot /tmp/aec-bench-catalogue.json
uv run aec-bench catalogue diff --against /tmp/aec-bench-catalogue.json
```

Review identity, readable key, version, metadata, profile or variant
registration, and owner conformance together. The UUIDv7 is the entity
identity. Build-reference checksums record source integrity. Catalogue
snapshots record semantic identity and metadata for review.
