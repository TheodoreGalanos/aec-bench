---
name: hardening-pass
description: Review and harden a task template or task instance for correctness, robustness, and benchmark readiness. Use when a template or task has been created and needs quality-gating before use in real benchmarks. Also trigger when the user asks to "harden", "review a template", "check a task", or "validate before benchmarking".
---

# Hardening Pass

Perform a thorough quality review of a task template or task instance before it's used in real benchmarks. This skill protects the **validity** invariant — the top of the objective stack.

A template hardening catches formula and parameter issues before you generate instances. An instance hardening catches problems that only show up in concrete tasks (Dockerfile, verifier, instruction with real values).

## When to Use

- After creating a template with `/create-template`
- After manually authoring a task instance
- Before running a template's generated instances through Harbor for the first time
- When reviewing someone else's template or task
- Periodically, to re-validate existing templates against updated standards

## Input

The skill accepts a path to either:

- **A template directory** (detected by presence of `engine.py` + `params.toml`)
- **A task instance directory** (detected by presence of `task.toml`)

```
/hardening-pass src/aec_bench/templates/builtin/ground/terzaghi_bearing/
/hardening-pass tasks/mechanical/heat-load/audit-office-building/brisbane-8rm/
```

If no path is provided, ask the user what they want to harden.

## Process

### Step 1: Detect Target Type

Read the directory contents:

- If `engine.py` and `params.toml` exist → **Template Hardening** (Step 2)
- If `task.toml` exists → **Instance Hardening** (Step 3)
- If neither → tell the user this doesn't look like a template or task instance

### Step 2: Template Hardening

Read all template files: `engine.py`, `params.toml`, `instruction.md`, `__init__.py`.

#### 2a. Formula Correctness

Read `engine.py` and assess:

- [ ] **Identify the formula/standard** — what engineering calculation does `compute()` implement? Note the standard reference.
- [ ] **Web-verify the formula** — use WebSearch to find the authoritative formula from the referenced standard. Compare against the implementation. Flag discrepancies: wrong coefficients, missing terms, incorrect units.
- [ ] **Check edge cases** — does `_validate_inputs()` catch physically impossible values? (negative angles, zero denominators, out-of-range coefficients)
- [ ] **Check output rounding** — are all outputs `round(value, 2)`?
- [ ] **Check purity** — does `compute()` have side effects? It should be a pure function (inputs → outputs, no I/O, no state).
- [ ] **Stdlib only** — only `import math` allowed, no third-party dependencies.

#### 2b. Parameter Ranges

Read `params.toml` and assess:

- [ ] **Physical realism** — do the min/max ranges for each parameter produce physically realistic values? For example, soil friction angles should be 0-45 degrees, not 0-90.
- [ ] **Archetype combinations** — for each archetype, do the parameter ranges combine to produce reasonable scenarios? Run `compute()` mentally or actually with extreme values from each archetype.
- [ ] **Categorical values** — are enum values exhaustive and correctly spelled? Do they match the terms used in the referenced standard?
- [ ] **Site contexts** — does every archetype have `site_contexts`?

#### 2c. Difficulty Calibration

- [ ] **Progressive difficulty** — are the difficulty presets (easy/medium/hard) genuinely progressive? Easy should have fewer parameters and wider tolerances, hard should have hidden parameters and tighter tolerances.
- [ ] **Hidden parameters** — for medium/hard, are the hidden parameters ones that genuinely test agent knowledge (not trivially guessable)?
- [ ] **Tolerances** — are tolerances appropriate? Guidelines: 0.01 for exact lookups, 0.03 for calculated values, 0.05 for interpolated values. Flag any tolerance above 0.10 or below 0.005.

#### 2d. Instruction Quality

Read `instruction.md` and assess:

- [ ] **Output format clear** — does the instruction clearly specify the JSON output keys and their units?
- [ ] **Output keys match compute()** — do the JSON keys requested in the instruction exactly match the keys returned by `compute()`?
- [ ] **Jinja2 conditionals** — are hidden parameter conditionals correct? When a parameter is hidden, is the agent told to determine it, not given the value?
- [ ] **No ambiguity** — could a competent engineer reading this instruction produce a different but defensible answer? If yes, the instruction needs tightening.

#### 2e. Validation Run

Run the template through validation:

```bash
uv run aec-bench generate validate-template <template_dir>
```

Then generate a test instance and compute with sample values:

```bash
uv run aec-bench generate task <template-name> --instances 1 --seed 42 --output /tmp/hardening-preview/ --dry-run
```

Check: does the generated instruction look correct with concrete parameter values?

### Step 3: Instance Hardening

Read all instance files: `task.toml`, `instruction.md`, and check for `environment/Dockerfile`, `tests/verify.py`.

#### 3a. Metadata

Read `task.toml` and check:

- [ ] **Required sections** — does it have `[metadata]`, `[agent]`, `[verifier]`, and `[environment]`?
- [ ] **Difficulty level** — is `[metadata].difficulty` set to one of easy/medium/hard?
- [ ] **Tags** — are `[metadata].tags` present and include the discipline?
- [ ] **Tools** — if `[[environment.tools]]` is declared, do the referenced tool files exist?

#### 3b. Instruction

Read `instruction.md` and check:

- [ ] **No template placeholders** — search for `{{`, `{%`, `TODO`, `FIXME`. None should remain.
- [ ] **Output format specified** — does the instruction tell the agent what output to produce, in what format, and where to write it?
- [ ] **Concrete values** — are all parameter values concrete numbers, not descriptions or ranges?
- [ ] **Achievable** — given the tools declared in task.toml, can an agent plausibly complete this task?

#### 3c. Environment

If `environment/Dockerfile` exists:

- [ ] **Base image specified** — does it use a specific, pinned base image?
- [ ] **Tool scripts staged** — are any declared tool scripts (e.g., `codes_search.py`) copied into the container?
- [ ] **No secrets in Dockerfile** — no API keys, tokens, or credentials hardcoded

#### 3d. Verifier

If `tests/verify.py` (or `tests/test.sh`) exists:

- [ ] **Reward shape** — does it write `{"reward": <float>}` to the correct location?
- [ ] **All outputs checked** — does the verifier check every output field mentioned in the instruction?
- [ ] **Tolerance-based comparison** — for numeric outputs, does it use tolerances (not exact equality)?
- [ ] **Partial credit** — does it give partial credit for partially correct answers, or is it all-or-nothing? (Both are valid, but should be intentional)
- [ ] **Error handling** — does it handle missing output files, malformed JSON, or wrong output format without crashing?

If no verifier exists:

- [ ] **Flag as critical** — a task without a verifier cannot be scored

### Step 4: Produce the Report

Output a structured hardening report:

```
## Hardening Report

**Target:** <path>
**Type:** Template / Instance
**Standard:** <referenced standard if applicable>

### Checks

| # | Category | Check | Status | Notes |
|---|----------|-------|--------|-------|
| 1 | Formula  | Coefficients match standard | PASS/WARN/FAIL | detail |
| ... | ... | ... | ... | ... |

### Findings

**[FINDING-1]** severity: critical/high/medium/low
- Check: #N
- Issue: [what's wrong]
- Fix: [what to do]
- Evidence: [why this matters — cite the standard or show the calculation]

### Summary
- X checks run, Y passed, Z warnings, W failures
- Benchmark readiness: READY / NEEDS FIXES / NOT READY
```

**Benchmark readiness criteria:**
- **READY** — no failures, warnings are acknowledged
- **NEEDS FIXES** — failures exist but are fixable, or critical warnings need attention
- **NOT READY** — critical failures (missing verifier, wrong formula, physically impossible parameters)

### Step 5: Offer Fixes

If findings exist, offer to fix them:

- For template issues: edit engine.py, params.toml, or instruction.md directly
- For instance issues: edit the relevant files
- Re-run the applicable checks after fixing
- Update the report

## Reference Files

Read these as needed:

- `references/checklist-summary.md` — Quick reference of all checks in table format
