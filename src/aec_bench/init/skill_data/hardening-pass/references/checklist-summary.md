# ABOUTME: Quick-reference checklist for the hardening-pass skill.
# ABOUTME: All checks in table format for fast scanning during reviews.

# Hardening Checklist Summary

## Template Checks

| # | Category | Check | Severity if Failed |
|---|----------|-------|--------------------|
| T1 | Formula | Coefficients match referenced standard | Critical |
| T2 | Formula | Edge cases caught in _validate_inputs() | High |
| T3 | Formula | Outputs rounded to 2 decimal places | Low |
| T4 | Formula | compute() is a pure function (no side effects) | High |
| T5 | Formula | Only stdlib imports (math) | Medium |
| T6 | Params | Min/max ranges are physically realistic | Critical |
| T7 | Params | Archetype combinations produce reasonable scenarios | High |
| T8 | Params | Categorical values match standard terminology | Medium |
| T9 | Params | Every archetype has site_contexts | Medium |
| T10 | Difficulty | Presets are genuinely progressive (easy < medium < hard) | High |
| T11 | Difficulty | Hidden parameters test real knowledge | Medium |
| T12 | Difficulty | Tolerances are appropriate (0.01-0.05 typical) | High |
| T13 | Instruction | Output format and keys clearly specified | High |
| T14 | Instruction | Output keys match compute() return dict | Critical |
| T15 | Instruction | Jinja2 conditionals correct for hidden params | High |
| T16 | Instruction | No ambiguity in task description | Medium |
| T17 | Validation | validate-template passes | Critical |
| T18 | Validation | Generated instance looks correct | High |

## Instance Checks

| # | Category | Check | Severity if Failed |
|---|----------|-------|--------------------|
| I1 | Metadata | task.toml has [meta] and [difficulty] | High |
| I2 | Metadata | Difficulty level is valid (easy/medium/hard) | Medium |
| I3 | Metadata | Tags present and include discipline | Low |
| I4 | Metadata | Declared tool files exist | High |
| I5 | Instruction | No template placeholders remaining | Critical |
| I6 | Instruction | Output format specified | High |
| I7 | Instruction | All values are concrete (no ranges/descriptions) | High |
| I8 | Instruction | Task is achievable with declared tools | Medium |
| I9 | Environment | Dockerfile uses pinned base image | Medium |
| I10 | Environment | Tool scripts staged in container | High |
| I11 | Environment | No hardcoded secrets | Critical |
| I12 | Verifier | Exists | Critical |
| I13 | Verifier | Writes correct reward shape | Critical |
| I14 | Verifier | Checks all output fields | High |
| I15 | Verifier | Uses tolerance-based comparison for numerics | High |
| I16 | Verifier | Handles missing/malformed output gracefully | Medium |

## Benchmark Readiness

| Verdict | Criteria |
|---------|----------|
| READY | No failures, warnings acknowledged |
| NEEDS FIXES | Failures exist but fixable |
| NOT READY | Critical failures present |
