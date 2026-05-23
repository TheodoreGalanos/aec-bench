# ABOUTME: Guide for writing and maintaining Python adapters.
# ABOUTME: Covers thin adapters, interface contracts, tool handling, transcript capture, and onboarding new providers.

# Adapters Guide

Adapters are translation layers between the harness and a specific model SDK or provider API. In Python, this likely means a mix of SDK wrappers and `httpx`-based integrations. The architectural rule is unchanged: adapters translate protocol only.

Parent document: [ARCHITECTURE.md](ARCHITECTURE.md).
Data shapes: [CONTRACTS.md](CONTRACTS.md).
Rules: [INVARIANTS.md](INVARIANTS.md).

---

## Thin Adapter Principle

Adapters do:

- pass instruction content through unchanged,
- translate tool declarations,
- manage the conversation loop,
- capture transcripts,
- collect output and execution metadata.

Adapters do not:

- branch on task type,
- rewrite instructions,
- choose tools,
- score outputs,
- encode benchmark strategy.

If an adapter needs task-specific code, the architecture is already drifting.

---

## Interface Contract

Inputs from harness:

- instruction
- optional system prompt
- tools
- configuration
- workspace
- output path

Outputs to harness:

- agent output
- transcript
- completion status
- token usage where available
- duration
- error information

Keep instruction, system prompt, and protocol translation separate.

---

## Tool Handling

Tasks declare tools. Adapters translate those tool declarations into the provider's native format.

For tool-loop adapters:

1. receive tool call,
2. execute tool within the task environment,
3. capture output and exit status,
4. return structured result to the model,
5. continue until a structural completion signal occurs.

Tool failures must be surfaced to the model, not swallowed.

---

## Conversation Management

Python adapters should manage multi-turn sessions with explicit rules for:

- turn limits,
- timeouts,
- transcript completeness,
- completion detection from protocol signals,
- tool result formatting.

Do not detect completion by parsing natural-language phrases like "done".

---

## Onboarding a New Provider

Before implementing a new adapter, map provider protocol concepts to the standard adapter surface:

- instruction message
- system prompt support
- tool declaration format
- tool call and tool result format
- completion signal
- token usage reporting
- transcript representation

Document protocol gaps instead of hiding them with workaround behavior that changes benchmark semantics.

---

## Lambda-RLM Extraction Uncertainty

The `lambda_rlm` adapter now records extraction-time uncertainty signals and can use them to decide whether the review phase runs for a section. This stays within the adapter boundary: no task logic changes, no evaluation-layer metrics invented here, and the default policy remains backward-compatible.

### Signals recorded during extraction

- **Verbalized confidence**: the extraction prompt asks the model to emit a reserved top-level key named `__confidence__` with a float in `[0.0, 1.0]`. The executor strips that key before storing the semantic extraction payload and records the numeric value in runtime state.
- **Self-consistency**: when `extract.k_candidates > 1`, the adapter fans out K extraction calls for the same chunk, vote-merges the candidates deterministically, and records a per-source consistency score.
- **Trace length**: output token counts from leaf extraction calls are recorded for every run. When uncertainty scoring is active, those lengths combine with confidence to produce a joint uncertainty score.

### Review trigger policy

The review phase is no longer only on/off for `lambda_rlm`. When `review.enabled = true`, `review.trigger` controls whether review runs:

| Trigger | Behaviour |
| --- | --- |
| `always` | Run review for every section. This is the default and preserves prior behaviour. |
| `never` | Skip review for every section. Useful for ablations. |
| `uncertainty` | Run review only when the section's max joint uncertainty score exceeds `uncertainty.review_joint_threshold`. |
| `consistency` | Run review only when the section's mean extraction consistency falls below `review.consistency_threshold`. |
| `both` | Run review only when both the uncertainty and consistency conditions are met. |

If a trigger requires data that does not exist yet, the adapter falls back conservatively to `always` and records the reason in the trajectory. Example: `trigger = "consistency"` with `extract.k_candidates = 1` has no consistency evidence, so review still runs.

### Config examples

Minimal smart-review setup:

```toml
k_candidates = 3

[review]
trigger = "both"
```

More explicit tuning:

```toml
[extract]
k_candidates = 3
temperature = 0.7
keep_candidates_artifact = true

[uncertainty]
lambda = 0.5
min_confidence_eps = 0.01
min_samples = 3
review_joint_threshold = 1.0

[review]
trigger = "uncertainty"
consistency_threshold = 0.7
```

### Observability

- `PlanState.snapshot()` now includes `confidence`, `consistency`, and `uncertainty` blocks for `lambda_rlm` runs.
- The adapter can write `extraction_candidates.json` when `extract.keep_candidates_artifact = true`.
- Real-time trajectory output includes `confidence`, `uncertainty`, and `review_decision` lines so operators can see why review ran or was skipped.

### Compatibility notes

- `review.trigger = "always"` with `extract.k_candidates = 1` reproduces the prior review behaviour.
- The repo's current `lambda_rlm` tests use inline `ReplayRlmClient` responses rather than external replay fixture files, so validation for this feature remains test-driven in code rather than by refreshing standalone fixtures.

---

## Conformance Expectations

- no task imports,
- no silent behavior-affecting defaults,
- faithful transcript capture,
- configuration recorded into TrialRecord,
- no adapter-owned randomness.
