# ABOUTME: Local instructions for maintaining repository-owned AEC-Bench documentation.
# ABOUTME: Keeps normative contracts current without duplicating implementation inventories or historical layers.

# Documentation Guide

The root `AGENTS.md` also applies. This file adds rules only for work inside `docs/`.

## Document authority

- `INVARIANTS.md` defines non-negotiable benchmark guarantees.
- `CONTRACTS.md` defines logical shapes and semantics at real domain boundaries.
- `ARCHITECTURE.md` defines durable domain ownership and dependency direction.
- `PROJECT_STRUCTURE.md` gives stable navigation and layout guidance. It is not an inventory of every package.
- Files marked draft, plan, work item, research, or historical do not become implementation requirements unless the task explicitly selects them.

State the status of a new design document near its title: `Normative`, `Draft`, `Research`, or `Historical`.

## Editing policy

- Verify technical claims against the current implementation, tests, and configuration before editing.
- Change the smallest authoritative document set. Link to an existing authority instead of repeating it.
- Remove superseded normative text. Do not preserve obsolete guidance as a compatibility layer or change log.
- Do not copy package trees, test counts, dependency versions, CLI output, or other volatile inventories when a source file or live command is the better authority.
- Use examples to explain a contract, not to create a second contract.
- Keep code identifiers, paths, commands, and schema fields exact.
- Use `MUST`, `MUST NOT`, and `NEVER` only for genuine benchmark, security, data, or public-contract requirements.
- Do not expand architecture while documenting a local behaviour change. Record only the durable decision the change actually makes.

## Update routing

- Public installation, commands, and user-visible behaviour: update `../README.md` and the public documentation source when it is part of the task.
- Boundary semantics: update `CONTRACTS.md`.
- Benchmark guarantees: update `INVARIANTS.md` only with deliberate approval.
- Domain ownership or dependency direction: update `ARCHITECTURE.md`.
- Stable repository layout: update `PROJECT_STRUCTURE.md`.

When code and documentation disagree, do not document both. Determine the intended behaviour, then update code, tests, and the authoritative document as one coherent change.

## Validation

- Check every changed path, command, identifier, and relative link.
- Run focused tests when documentation contains executable examples or describes changed runtime behaviour.
- Documentation-only edits do not require unrelated unit, integration, and end-to-end test runs.
