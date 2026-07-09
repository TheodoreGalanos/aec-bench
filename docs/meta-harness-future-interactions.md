# Meta-Harness Future Interactions

This note tracks future links between the meta-harness runtime and adjacent AEC-Bench systems. It is intentionally separate from the porting work so the library code can stay focused on contracts and execution boundaries.

## Harness Evolution

The meta-harness operation profile gives harness evolution a more explicit vocabulary for controlled changes:

- projection can isolate one verifier, evidence, trace, or governance surface for ablation;
- difference can remove one declared surface to test whether it is actually necessary;
- subset can restrict task families, evidence channels, or tool affordances without changing the source world;
- product can compose two worlds when both declare a shared composition axis.

The boundary to preserve is that operations produce candidate worlds or recorded proposals. They should not mutate source tasks, verifiers, or generators directly. Evolution can consume operation outputs as candidate variants, but acceptance should still run through its existing scoring, provenance, and promotion gates.

## Optimisation

The autonomous world-process supervisor introduces iteration budgets, score histories, stagnation checks, and candidate selection. Those ideas overlap with optimisation, but the first integration should be read-only:

- optimisation can inspect logic evaluations and operation histories as features;
- meta-harness scoring can learn from existing verifier reward and evolution metrics;
- candidate selection can reuse optimisation summaries without becoming a second optimiser.

The useful shared contract is a process result with stable evidence, score components, and provenance. Avoid coupling optimisation internals to world generation or governance decisions until the contracts have settled.

## CLI And Batch Workflows

The migrated `aec-bench meta-harness` commands give evolution and optimisation a stable batch surface:

- `logic-evaluate` can score existing runs without rerunning tasks;
- `operation-apply` and `operation-orchestrate` can produce candidate worlds for later evolution runs;
- `harbor-task` can materialize an operation task package for external runners;
- `autonomous` can consume queued real artifacts and stop at explicit waiting states.

These commands should stay adapters over library contracts. They are useful for jobs, sweeps, and debugging, but they should not grow separate decision logic from the library.

## Reviewer And Verifier Repair

Reviewer event candidates are the strongest bridge to verifier repair. A reviewer finding such as `verifier_language_gap` or `schema_gap` should become a governed repair candidate, not an immediate verifier edit.

Potential future flow:

1. deterministic verifier produces reward and details;
2. logic profile evaluates closure, construction, and containment;
3. reviewer records event candidates with evidence references;
4. operation orchestrator proposes schema, evidence, or verifier handles;
5. governance decides whether the proposal is run-only, world-schema, or generator-level.

This keeps verifier authority intact while still letting the system notice when the verifier language is too weak for the trace it is judging.

## Implementation Constraint

The port should keep using AEC-Bench native boundaries:

- contracts define typed shapes;
- evaluation materialises and reviews evidence;
- harness owns execution/import;
- meta-harness modules coordinate worlds, operations, governance, and autonomy;
- CLI surfaces call library functions rather than carrying logic themselves.
