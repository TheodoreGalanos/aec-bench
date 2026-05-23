# ABOUTME: Guide for authoring, managing, and evolving benchmark tasks in the Python aec-bench plan.
# ABOUTME: Covers task design, instances, lifecycle, visibility, verifiers, and quality rules.

# Tasks Guide

Tasks are what the benchmark measures. A task remains a self-contained unit with an instruction, environment, verifier, and metadata. The Python implementation does not change task semantics; it only changes the loader and orchestration code around them.

Parent document: [ARCHITECTURE.md](ARCHITECTURE.md).
Data shapes: [CONTRACTS.md](CONTRACTS.md).
Rules: [INVARIANTS.md](INVARIANTS.md).

---

## Task Anatomy

A task has two layers:

- **Task type**: the problem family being tested.
- **Instance**: one concrete runnable scenario.

Task types define:

- BRIEF
- shared tools
- payload schema

Instances define:

- resolved instruction
- environment
- verifier
- difficulty/tags/timeouts

---

## Design Rules

### Start with the BRIEF

Every task type begins with a design brief that explains:

- what is being tested,
- why it matters,
- what constitutes a valid finding or result,
- what does not count,
- how instances are created,
- how outputs are scored.

The BRIEF is the source of truth for the task family and is never sent to the agent.

### Category selection

Task paths use the top-level discipline or domain as the first segment, such
as `civil`, `electrical`, or `mechanical`. Use `metadata.category` for the task
family or review mode being evaluated, such as `reasoning`, `cable-sizing`, or
`pipe-hydraulics`.

### Difficulty

Difficulty is about reasoning complexity, not prestige or domain mystique. It should be calibrated against observed agent performance.

---

## Instance Rules

### Fully resolved instructions

An instance instruction contains no placeholders. It must stand alone with the declared tools.

### Clean instance rule

Minimum 1 clean instance per 3 total instances of a task type.

Clean instances:

- contain no true issues,
- still require schema-valid output,
- test false-positive resistance.

### Naming

Use `<jurisdiction>-<building-type>` naming unless a stronger established convention exists.

---

## Environment Rules

The environment provides everything the agent container needs:

- staged inputs,
- declared tools,
- known output paths,
- verifier log paths.

Key principles:

- tasks declare tools,
- adapters do not decide tool availability,
- runtime dependencies are task-level decisions,
- benchmark inputs are staged before execution.

---

## Verifier Rules

Verifiers are task-specific and deterministic.

They should:

- validate output shape first,
- score content second,
- produce a reward file,
- optionally produce details,
- penalize false positives,
- never depend on randomness or external services.

Rubric-scored tasks remain valid in the Python plan. The verifier handles the mechanical floor; richer rubric assessment belongs in evaluation.

---

## Lifecycle and Visibility

Lifecycle states:

- `proposed`
- `active`
- `deprecated`
- `retired`

Promotion from `proposed` to `active` requires at minimum:

- resolved instruction,
- working environment,
- verified verifier,
- expert review of task meaning,
- clean-instance rule satisfied.

Visibility remains independent of lifecycle:

- `public`
- `holdout`

Holdout content follows the anti-contamination rules in [INVARIANTS.md](INVARIANTS.md).
