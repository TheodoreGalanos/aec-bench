# ABOUTME: Gives domain-check users concise tests for the current stable AEC-Bench guarantees.
# ABOUTME: Defers lifecycle and storage mechanics to their owning protocols.

# Invariants: Compact Reference

Source of truth: `docs/INVARIANTS.md`. Read that file when a check is ambiguous
or a change could alter a benchmark guarantee.

| Guarantee | One-line check |
| --- | --- |
| Benchmark validity | Does the result measure the declared task, condition, limits, and verifier without contamination or identity drift? |
| Reproducible identity and provenance | Is every outcome-affecting input and implementation identity recorded directly or by durable content reference? |
| Controlled actor-visible information | Can the actor see only the observation, files, tools, and history allowed by the visibility policy? |
| Provider-neutral task semantics | Could the task or world keep the same meaning under another conforming provider, backend, or transport? |
| Evaluation authority | Do reward, validity, diagnostics, and confidence come from evaluation rather than persistence or presentation? |
| Public and holdout separation | Can sealed or holdout content enter a public catalogue, prompt, example, export, report, or generated document? |
| Explicit failures | Can an error, timeout, interruption, malformed result, or incomplete recovery be mistaken for success? |
| Structured human judgment | Is result-affecting expert judgment attributable and bound to its evidence and method? |
| Permanent ownership | Does every required build, run, generation, verification, certification, migration, or test artifact have a tracked owner? |
| Deterministic replay | Does replay use recorded identity, inputs, order, and lineage and reproduce the declared result or tolerance? |
| Boundary validation | Is untrusted, persisted, external, or cross-process data validated when admitted? |
| Declared evidence integrity | Does accepted or published evidence follow the immutability or append-only semantics its contract declares? |

## Objective order

Resolve conflicts in this order:

```text
validity > reproducibility > coverage > cost > throughput
```

## Review notes

- A content-addressed artifact reference can provide provenance without copying
  every byte into one record.
- Ordinary implementation details do not become persisted evidence unless they
  can affect the benchmark outcome.
- Strict boundary validation does not require a Pydantic model for every local
  intermediate value.
- Domain evidence can be immutable while source code and internal APIs remain
  replaceable.
- An internal test or caller is evidence of current behaviour, not by itself a
  public compatibility promise.
- Protocols own detailed locking, transaction, recovery, and publication
  mechanics.
