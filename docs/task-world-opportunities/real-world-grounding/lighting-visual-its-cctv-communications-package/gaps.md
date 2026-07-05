# ABOUTME: Gap register for the SSC-13 road visual operations synthetic source pack.
# ABOUTME: Separates runnable-synthetic readiness from benchmark/runtime readiness.

# Gaps

## Closed By This Pass

- A first task-owned SSC-13 source-pack seed exists for `SSC-13-LH-01`.
- The pack has a closed scene, source manifest, stage graph, case ledger, handoff ledger, oracle tables, expected output, verification rules, negative cases, and verifier implementation brief.
- The pack is specific enough to drive a future deterministic parser/verifier.
- `road-visual-operations-package` now exists as a `CompositeTaskWorldTemplate` entry.
- The existing composite-template materializer can generate a package-contract example with `template.json`, `world.json`, hidden state, a structured answer, a deliverable file, and `verifier/result.json`.
- The existing package-contract verifier passes the generated example at score `1.0`.

## Still Open

- No source-pack parser/verifier recomputes the oracle rows from these files yet.
- The generated package-contract example verifies handoff presence and continuity, not full source-file formula closure.
- The lighting values are task-owned oracle values, not recomputed from photometric files.
- The VMS rule is a task-owned policy excerpt, not a full MUTCD compliance check.
- The CCTV, bandwidth, PoE, fibre, and UPS checks are deliberately simple and do not represent a manufacturer design report.
- No public accepted project evidence, authority approval, or commissioning record has been captured.

## Next Work

1. Implement a small deterministic verifier for the pack files.
2. Add one selected variant at a time, beginning with a cabinet relocation or camera target-width failure.
3. Only after the synthetic verifier works, decide whether to seek public project evidence or richer source adapters.
