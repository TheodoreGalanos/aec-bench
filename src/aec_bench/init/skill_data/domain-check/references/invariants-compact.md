# ABOUTME: Compact invariant reference for the domain-check skill.
# ABOUTME: All 10 invariants with one-line tests, affected domains, and enforcement details.

# Invariants (Compact Reference)

Source of truth: `docs/INVARIANTS.md`

## Quick Reference

| # | Name | One-Line Test | Affected Domains |
|---|---|---|---|
| 1 | Single source of truth | Can this trial be reproduced from its TrialRecord alone? | Harness, Contracts, Adapters |
| 2 | Contracts at boundaries | Does every cross-domain call validate against a contract? | All cross-domain |
| 3 | No hidden state | Is every input that affects outcomes persisted in the run record? | Adapters, Harness, Agents |
| 4 | Task-adapter independence | Does this task work with ANY adapter? Does this adapter work with ANY task? | Tasks, Adapters, Agents |
| 5 | Evaluation is a pipeline | Does this metric compile from evaluation outputs, not invented data? | Evaluation, Communication |
| 6 | Public/holdout separation | Could holdout content leak through this change? | Communication, Feedback, Tasks |
| 7 | Validate before commit | Has this been smoke-tested on a representative subset? | Any new feature |
| 8 | Provider isolation | Can you describe what this code does without naming a vendor? | Providers, Harness, Agents |
| 9 | Human judgment is structured | Is expert feedback captured as machine-readable, provenanced data? | Feedback |
| 10 | Continuous quality | Does this change pay down drift or add to it? | All |

## Detailed Checks Per Invariant

### 1. Single Source of Truth
- TrialRecord must contain: task revision, verifier revision, adapter revision, model ID, prompt inputs, tool config, runtime image, seed
- Any result that cannot be replayed from its record is invalid
- Check: does the change add any trial input/parameter NOT captured in TrialRecord?

### 2. Contracts at Boundaries
- All domain boundaries are schema-defined (Pydantic `StrictModel` for internal, `LenientModel` for external)
- No component exchanges untyped payloads across domains
- Check: does the change pass raw dicts/strings across domain boundaries instead of validated models?

### 3. No Hidden State
- All state affecting outcomes must be explicit and persisted
- No dependency on local machine quirks, unstored prompts, undocumented defaults
- Check: does the change introduce any default value, retry logic, or timeout not captured in config?

### 4. Task-Adapter Independence
- Tasks must not encode model/SDK/tooling assumptions
- Adapters must not contain task-specific logic
- Agents receive `ToolSpec` from Contracts, not from Tasks directly
- Check: does any adapter reference a specific task? Does any task reference a specific model?

### 5. Evaluation Is a Pipeline
- Reward is necessary but insufficient
- Communication layers cannot invent metrics absent from evaluation outputs
- Check: does the change create any metric/chart/export that doesn't trace back to EvaluationResult fields?

### 6. Public/Holdout Separation
- Holdout task briefs, findings, and verifier logic never shared outside evaluation team
- Aggregate statistics are OK, specific findings are not
- Check: could this code path expose holdout task details to public-facing outputs?

### 7. Validate Before Commit
- New model/adapter/tool changes validated on representative subset before full benchmark
- Check: does the change include a smoke test or validation path?

### 8. Provider Isolation
- Cross-cutting concerns accessed only via provider interfaces
- Domain code cannot directly couple to vendor APIs
- Check: does the change import vendor-specific libraries (Modal, anthropic, openai, etc.) outside of `providers/` or `agents/`?

### 9. Human Judgment Is Structured
- Expert feedback in machine-readable form with provenance
- Free-text without structured tags is advisory only
- Check: does the change capture expert input with reviewer ID, timestamp, and category?

### 10. Continuous Quality
- Drift corrected continuously, not periodically
- Technical debt tracked with owner and deadline
- Check: does this change leave TODO comments without tracking? Does it copy a pattern that should be abstracted?

## Objective Stack (Conflict Resolution)

When invariants conflict:

```
validity > reproducibility > coverage > cost > throughput
```
