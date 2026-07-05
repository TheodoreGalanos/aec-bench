# ABOUTME: Step-by-step authoring guide for review-first long-horizon templates across the SSC notes.
# ABOUTME: Encodes the load-bearing invariants, file recipes, verifier contract, tests, and acceptance criteria.

# Review-First Template Authoring Guide

This guide tells an authoring agent exactly how to build one review-first long-horizon template for an SSC product, in the style of the reference implementation `road-low-point-issue-review-package`. Follow it literally. Where the guide says "must", a test or validator enforces it; where it says "why", it is explaining a constraint that previous work got wrong — do not optimize these away.

Read these before starting, in this order:

1. [../long-horizon-course-correction.md](../long-horizon-course-correction.md) — why the previous 150 package templates do not count as long-horizon, and the acceptance criteria you are building against.
2. [review-loop-long-horizon-lessons.md](review-loop-long-horizon-lessons.md) — the review-loop pattern this task shape implements.
3. [ssc01-lh01-review-first-redesign.md](ssc01-lh01-review-first-redesign.md) — the design note behind the reference implementation.
4. The reference implementation itself, all six files: `src/aec_bench/templates/builtin/civil/road_low_point_issue_review_package/` and its test file `tests/templates/test_road_low_point_issue_review_package.py`.
5. For SSC-01 conversions specifically, [ssc01-review-first-conversion-plan.md](ssc01-review-first-conversion-plan.md) — maps each existing SSC-01 product to a review-first candidate and names the next implementation slice.
6. For cross-SSC SME review before implementation, [review-first-task-construction-catalogue.md](review-first-task-construction-catalogue.md) — gives one anchor review-first task seed for every non-SSC-01 note and the product-family expansion rule.

## What You Are Building

One template directory that generates *review* tasks: the agent under test receives a multi-file engineering source packet in its sandbox, must inventory it, preserve object identity, recompute the package's own calculations as evidence, assign one status per review item, raise findings/information requests/actions, and issue a readiness decision. A hidden packet variant plants (or does not plant) a defect; the gold review state flips deterministically with the variant.

The task's difficulty comes from preserving engineering meaning across files and time — not from a longer calculation chain, and not from ambiguity about what output format is expected.

## The Non-Negotiables

Each of these is load-bearing. Each was violated by the earlier 150-template stream, which is why that stream saturated at birth.

| # | Rule | Why | Enforced by |
|---|---|---|---|
| 1 | Source values live in generated files under `sources/`, never in `instruction.md`. The instruction may contain zero engineering numbers. | If values are in the prompt, the task is a worksheet: no inventory, no extraction, no tool use. Also, the instruction renderer rounds floats to 2 decimal places and will silently corrupt values like Manning's `n = 0.016`. | Template test asserting the instruction has no unresolved placeholders and no source numerics; source files rendered by your own f-strings. |
| 2 | Methods and conventions are source-owned: the criteria/comments file states the assessment bases (formulas, coefficients, datums). The prompt never pins them. | Resolving "which method, which convention, which basis" is the engineering content. Pinning it in the prompt was how the earlier templates deleted their own difficulty. Putting it in a source document keeps it graded (the agent must find and follow the declared basis). | Design review; closure test recomputes evidence using the bases as printed in the criteria file. |
| 3 | The packet variant is a hidden enum param, and every derivation margin is a hidden param too. | If the variant or a margin is visible, defect presence leaks. Sampler visibility: use `visibility = "partial"` and list them in `hidden_params` in every difficulty preset. | Params.toml difficulty presets; test that sources differ between variants. |
| 4 | Numeric params sample real ranges — `min < max` everywhere engineering sense allows. | `min == max` means one frozen instance: no distribution, no pass^k, trivial contamination. 143/150 of the earlier templates had this defect. | Template test: ≥10 distinct values of a derived metric across 40 seeds. |
| 5 | Quantize before use: snap every sampled float to a reporting grid, then use the quantized value for *all* derivation and *all* printing. | If the engine computes with `97.33421` but the source prints `97.3`, the agent can never reproduce gold evidence. One quantize helper, one grid table, used by `compute` and `build_sources` identically. | Closure test (see rule 9). |
| 6 | Derivation-controlled margins: sample the *margin*, derive the criterion or input, and round in the safe direction. | Random independent sampling cannot guarantee "clean always passes" and "the failure variant always fails" across the whole parameter box. Deriving the criterion from computed value + sampled margin guarantees the inequality by construction. Round derived criteria toward the side that preserves the intended inequality (`ceil` capacities and allowables above pass points; subtract deficits for failure variants). | Template tests per variant: clean clears every criterion; the genuine-failure variant violates exactly its criterion. |
| 7 | Gold state is encoded in `compute()`'s float-only return: status codes (0 pass, 1 fail, 2 not_applicable, 3 insufficient_data), readiness code (0/1/2), required register counts, and the numeric evidence keys. | `SampledInstance.ground_truth` is `dict[str, float]` — a hard contract. Strings live only in the agent-facing vocabulary; the verifier maps them to codes. | Type contract; per-variant gold tests. |
| 8 | The verifier is stage-gated, not flat per-key partial credit. Status credit for computed items requires consistent evidence; readiness credit requires gold match AND self-consistency AND evidence support. The shipped `golden_fail` is the fluent-unsafe memo (all-pass, ready, no evidence, approval claims), not a zeroed answer. | Flat partial credit double-counts correlated keys and lets a fluent guesser score high. The fluent-unsafe memo is the exact adversary this task family exists to catch; it must score ≤ 0.5 on every variant (reference lands 0.28–0.37). | Verifier tests: golden pass 1.0 on all variants; fluent memo ≤ 0.5; evidence-stripped golden loses matrix+evidence+readiness credit; localization assertions on `details.json`. |
| 9 | Closure test: a test must reparse the *rendered source files* with regexes and recompute every gold evidence key with independently written formulas (do not import the engine's helpers). | This proves the task is solvable from what the agent actually sees. It catches precision drift, missing source lines, and formula/print mismatches that self-consistency tests cannot. | `test_evidence_recomputable_from_source_files_alone`. |
| 10 | `tool_mode = "no-tool"`. | With-tool templates ship a generated calc CLI wrapping the engine — which contains the variant logic and gold derivation. That is an answer key in the sandbox. | Template test: no `*_calc.py` in `environment/`. |
| 11 | Inverted acceptance: a template is *not* done when strong models score 1.0. Done = goldens pass, the fluent adversary fails, failures localize, and (later) at least one strong model scores below 1.0 somewhere on the variant distribution. | "Debug until Sonnet and Haiku reach 1.0" guarantees zero headroom. That was the core process failure being corrected. | Acceptance checklist at the end of this guide. |
| 12 | Do not create new runtime machinery. The scaffolder hooks below are the full extension surface. If you believe you need more, stop and raise it. | The runtime already supports everything this task shape needs. Parallel mechanisms drift. | Code review. |
| 13 | Instructions are variant-blind. The instruction and system prompt may state the generic review protocol (matrix definitions, status vocabulary, linkage rules, output schema, one generic missing-data rule). They may never map a specific defect, field, document, or scenario to a specific item, status, key omission, or readiness outcome. Test: a reader of `instruction.md` + `system_prompt.md` alone must not be able to enumerate the packet variants or their expected statuses. | Mapping defects to answers converts engineering judgment into transcription. This is how the first SSC-01 hardening pass silently re-saturated its templates: each sub-1.0 model run was "fixed" by writing that variant's gold answer into the prompt until the model scored 1.00. | Variant-blindness review before claiming; probe triage section below. |

## How Generation Works (What The Harness Gives You)

The pipeline is: `registry.load_template` → `sampler.sample_instance(config, engine.compute, difficulty, seed, index)` → `scaffolder.scaffold_task_instance(...)`, which writes a Harbor task directory:

```text
<out>/<discipline>/<category>/<template-name>/<instance-name>/
  task.toml
  instruction.md                  # Jinja-rendered; yours contains no values
  environment/
    Dockerfile                    # COPYs system_prompt.md + every sources/ file into /workspace/
    system_prompt.md              # your template-owned prompt (override)
    sources/*.md                  # from your build_sources hook
    trajectory_writer.py
  tests/
    verify.py                     # your custom verifier, copied verbatim
    instance.json                 # written automatically because you have a custom verifier
    test.sh
    fixtures/golden_pass.md       # from your build_golden_pass hook
    fixtures/golden_fail.md       # from your build_golden_fail hook
```

Critical safety fact: the agent only sees `/workspace/` (built from `environment/`). The `tests/` directory — including `instance.json` with the full gold state — is only uploaded for the verification phase. Never put gold state or variant markers anywhere under `environment/` except as legitimately printed source content.

The scaffolder hooks you implement (all optional, detected by attribute on your `engine.py` module or file presence in the template dir):

| Hook | Signature / location | What the scaffolder does with it |
|---|---|---|
| `build_sources` | `def build_sources(all_params: dict) -> dict[str, str]` in engine.py | Writes each `{relpath: content}` under `environment/` and adds a Dockerfile `COPY <relpath> /workspace/<relpath>` line. Use `sources/<kebab-name>.md` paths. |
| `build_golden_pass` | `def build_golden_pass(all_params: dict, ground_truth: dict) -> str` | Becomes `tests/fixtures/golden_pass.md` verbatim. Must score exactly 1.0. |
| `build_golden_fail` | `def build_golden_fail(all_params: dict, ground_truth: dict) -> str` | Becomes `tests/fixtures/golden_fail.md`. Must be the fluent-unsafe memo and score ≤ 0.5. |
| custom verifier | `verify.py` in the template dir | Copied to `tests/verify.py` unmodified; `tests/instance.json` (`instance_name`, `seed`, `difficulty`, `all_params`, `ground_truth`) is written next to it. |
| system prompt | `system_prompt.md` in the template dir | Replaces the default 3-4-turn calculation prompt. Yours should describe the review workflow with an 8-12 turn budget. |

## Design Worksheet (Do This Before Writing Any Code)

Work through these on paper (in your working notes) first. Every later file falls out of this worksheet.

**W1. Pick the product.** Use the SSC note's first hardening candidate or one of its `SSC-XX-LH-YY` products (see the per-SSC table at the end). The human title is always "Review the &lt;product&gt; package for issue." The template name is `<scene>-issue-review-package` (kebab-case); the directory is the same in snake_case; the category is `<domain>-review`.

**W2. Define the scene.** 5–9 physical objects with stable IDs following the SSC's existing ID conventions (e.g. `PMP-06-01`, `WW-06-WETWELL-01`). Reuse object IDs from the SSC's existing baseline package template so the cluster stays coherent. One scenario/case ID (storm case, fire case, outage case, design tide...).

**W3. Define 6–8 source files.** Always include, under these roles:

1. `document-register.md` — every source doc with ID, title, revision, status. This is the anchor for the stale-revision variant.
2. Two or three *domain evidence* files (geometry/process/load/schedule) carrying the sampled input values and the package's *claimed* results.
3. One *equipment/exposure* file — the asset whose adequacy the genuine-failure variant breaks.
4. One *secondary-discipline* file (power/comms, controls, acoustics — whatever the SSC's cross-discipline surface is).
5. One *scenario/operations* file — the anchor for the copy-forward variant.
6. `criteria-comments.md` — acceptance criteria (the derived allowables), the **assessment bases** (every formula and coefficient the reviewer needs, stated as source-owned methods), and the review comments table (anchor for the two comment variants).

Every file gets a document ID and revision in its header, matching the register (except where a variant plants a mismatch).

**W4. Adopt the review matrix.** Reuse the nine-item pattern with domain wording; keep the IDs `RLR-01`..`RLR-09` (or an SSC-flavored prefix, but then update the verifier and instruction consistently — simplest is to keep `RLR`):

| Item | Role (generic) |
|---|---|
| RLR-01 | Packet completeness (register vs delivered files) |
| RLR-02 | Object identity (IDs, chainage/location frame, datum, case stability across files) |
| RLR-03 | Primary domain basis (traceable + recomputable calculations) |
| RLR-04 | Asset exposure / criterion adequacy (the recomputed pass/fail check) |
| RLR-05 | Scenario consequence (same case used across disciplines) |
| RLR-06 | Secondary-discipline resilience (source-backed capacity/runtime/headroom) |
| RLR-07 | Comment and action closure |
| RLR-08 | Readiness decision consistency |
| RLR-09 | Claim boundary |

Boundary rule: define the primary/collateral behavior for every defect variant before implementing the verifier, but keep that definition out of `instruction.md` and `system_prompt.md`. If `scenario_copy_forward` is intended to flip only RLR-05, the generated source packet must contain enough positive evidence that adjacent items such as RLR-02/RLR-04/RLR-06/RLR-07 are explicitly reviewable from the files rather than plausibly `insufficient_data`. Add a source-boundary regression test for every subtle variant. Also define RLR-08 as reviewer self-consistency, not package-claim consistency: `not_ready_to_issue` can still make RLR-08 pass when the decision follows the matrix, findings, and action register.

**W5. Adopt the eight variants.** The variant set generalizes across every SSC; only the domain content changes:

| Variant (enum value) | Flips | Readiness | Required registers |
|---|---|---|---|
| `clean` | — | 0 (`ready_to_issue`) | — |
| `missing_<critical-field>` | RLR-04 → 3 | 2 | 1 information request naming the field + source |
| `stale_<basis>_revision` | RLR-03 → 1 | 2 | 1 finding |
| `<identity>_mismatch` (datum/chainage/tag) | RLR-02 → 1 | 2 | 1 finding |
| `scenario_copy_forward` | RLR-05 → 1 | 2 | 1 finding |
| `open_critical_comment` | RLR-07 → 1 | 2 | 1 finding |
| `minor_open_comment_carried` | — | 1 (`ready_with_carried_actions`) | 1 carried action (owner + action) |
| `<genuine-criterion-failure>` | RLR-04 → 1 | 2 | 1 finding |

Rules: exactly one primary flip per variant (localization depends on this); the genuine failure must be a *recomputable* engineering exceedance, ideally one the package's own files mis-claim via a realistic wrong method (the reference uses "freeboard measured to the road level instead of the controlling water level").

**W6. Define 6–9 evidence keys** (floats, unit-suffixed names like `spread_width_m`) and the item→evidence map (which keys back RLR-03/04/05/06). One key must be the derived criterion itself (e.g. `allowable_spread_m`) so the agent proves it read the criteria file. Decide which key disappears from `ground_truth` in the missing-evidence variant.

**W7. Decide the derivation-controlled quantities.** For each criterion: which margin is sampled (hidden), what is derived from it, and the safe rounding direction. Also decide the quantization grid for every sampled float (a realistic reporting precision: levels 0.005 m, intensities 0.1, coefficients 0.01...).

**W8. Borrow the math.** Do not invent domain formulas. Lift the physics from the SSC's existing baseline package engine (they are correct and tested) — e.g. for SSC-06, take the Hazen-Williams/NPSH/feeder math from `pump_station_duty_power_npsh_feeder_package/engine.py`. You are re-housing that math inside the review shape, not re-deriving it.

## File-By-File Recipe

Create `src/aec_bench/templates/builtin/<discipline>/<template_snake_name>/` with exactly these six files. Model every one on the reference implementation — same section order, same helper names.

### 1. `params.toml`

- `[meta]`: kebab-case `name`, `category = "<domain>-review"`, `tool_mode = "no-tool"`, honest `long_description` describing the review shape and variants.
- `[params.*]`: every sampled input with real ranges; enums for discrete hardware values (pipe diameters, speeds, autonomy hours). Include the sampled margins (`*_margin_*`, `*_deficit_*`, `*_target_*`) — these are hidden later. Include `packet_variant` as an enum with all eight values.
- `[outputs.*]`: one entry per ground-truth key. Status/readiness/count keys get `tolerance = 0.0`; evidence keys get `tolerance = 0.02`. (Outputs are documentation for this template — your custom verifier owns actual scoring — but keep them accurate.)
- Two `[archetypes.*]` for site flavor, with slightly different ranges for one or two params, each with `site_contexts`.
- Three `[difficulty.*]` presets (`easy`/`medium`/`hard`), all `visibility = "partial"`, all with the *same* `hidden_params` list = `packet_variant` + every margin param. Constrain the variant mix per difficulty by listing `packet_variant = [...]` directly in the preset (this flows through `DifficultyPreset.extra`): easy = obvious defects (`clean`, missing-evidence, genuine-failure), medium = all eight, hard = the four subtle documentary defects.

### 2. `engine.py`

Structure (keep these exact responsibilities and names):

```python
_QUANT_STEPS = {...}                  # every float param -> grid step

def _q(value, step): ...              # snap to grid, round(...,10) to kill float dust
def _ceil_to(value, step): ...        # safe-direction rounding for derived criteria

def _quantize(params) -> dict: ...    # snap floats, cast numeric enums with float(), int() counts,
                                      # str() the variant. EVERYTHING downstream uses only this.

def _derive(raw_params) -> dict: ...  # the single forward model: true metrics, derived criteria,
                                      # AND the package's claimed values (claims differ from truth
                                      # only where the variant plants the defect)

_VARIANT_GOLD = {...}                 # variant -> {flips, readiness, findings, requests, carried}

def compute(**params) -> dict[str, float]:
    # statuses (default 0.0, apply flips), readiness_code, required_*_count,
    # evidence keys from _derive; omit the missing-evidence key in that variant.

def build_sources(all_params) -> dict[str, str]:
    # calls _derive once; renders every file with f-strings at the SAME precision
    # as the quantization grid (:.3f for 0.005 grids, :.2f for 0.01, etc.)

_VARIANT_FINDINGS = {...}             # variant -> the one gold finding (item, severity,
                                      # source_id, object_id, consequence, action)

def _golden_payload(all_params, ground_truth) -> dict: ...
def build_golden_pass(all_params, ground_truth) -> str: ...   # prose + one fenced JSON block
def build_golden_fail(all_params, ground_truth) -> str: ...   # the fluent-unsafe memo
```

Annotations:

- **One `_derive`, called everywhere.** `compute`, `build_sources`, and `_golden_payload` must all read from the same derivation. Never duplicate a formula between them.
- **Claims vs truth.** For untouched items, printed claimed results equal true values (print at 3 decimals). The defect lives in exactly one place per variant: a revision header + superseded-basis note; a contradictory datum note; a copied assessment speed with its claimed reading time; an open comment row; a wrong-method claimed adequacy. Everything else stays consistent — the reviewer must find the defect, not wade through noise.
- **Safe rounding worked example.** `allowable_spread = _ceil_to(spread + margin, 0.25)` can only move the criterion *away* from the computed value, so clean always passes. The failure variant must not rely on rounding: derive the failing input directly (`pad = controlling + min_freeboard − deficit`), so the exceedance is guaranteed by construction.
- **Provisioned quantities.** When a printed capacity is derived with rounding (battery kWh, uplink Mbps), round *up* with `_ceil_to`, then recompute the gold evidence *from the printed value* — the agent can only recompute from what is printed.
- **The float-only contract.** `compute` returns only floats. Status vocabulary strings exist solely in the verifier and golden payloads.

### 3. `verify.py` (custom verifier)

Copy the reference verifier and adapt the constant tables only: `ITEM_EVIDENCE` (your item→evidence map), `EVIDENCE_KEYS`, `VARIANT_REQUEST_TOKENS` (tokens the information request must mention in your missing-evidence variant), `REQUIRED_LEDGER_TOKENS` (your object IDs + datum + location token). Keep everything else identical:

- Self-contained: stdlib only, reads `instance.json` via `Path(__file__).resolve().parent`, takes `--input`/`--output`, writes `{"reward": <float>}` plus a `details.json` sibling. Any exception → reward 0.0 with zeroed details, never a crash.
- Gate weights: matrix 0.30, evidence 0.20, linkage 0.20, readiness 0.20, identity/claims 0.10. They sum to 1.0 exactly; goldens must hit 1.0 without float slop.
- Matrix gate: per-item status match against gold; computed items (those in `ITEM_EVIDENCE`) earn status credit only if every gold-present evidence key is within tolerance (`rel_tol=0.02, abs_tol=0.01`); a gold `insufficient_data` item instead requires a matching information request.
- Linkage gate = mean of four booleans: matrix covers exactly the nine items with valid vocabulary; every agent-claimed `fail` has a complete finding; every agent-claimed `insufficient_data`/`not_applicable` has its request/reason; gold-required registers are satisfied (findings for gold-fail items, token-matched requests, carried actions with owner). The fourth check is what stops the fluent memo from passing linkage vacuously on defect variants.
- Readiness gate is all-or-nothing: vocabulary + gold match + self-consistency (own fails/IDs ⇒ `not_ready_to_issue`; own carried actions ⇒ not plain `ready_to_issue`) + evidence-gate score ≥ 0.5. The evidence condition is the stage-gating that zeroes the fluent memo's readiness credit even on the clean variant.
- Claims check is a *positive contract* (statement exists, contains the task-owned synthetic scope, an explicit negation such as "does not claim" or "does not constitute", and the core non-claim categories), never a forbidden-phrase scan — negated mentions ("does not claim approval") would false-positive a phrase blacklist.

Verify your weights hold the adversary bound before writing tests. Reference arithmetic for the fluent-unsafe memo: clean variant → matrix 5/9·0.30 = 0.167 (four computed items lose status credit for missing evidence) + linkage 0.20 (all four checks vacuously/actually true) = **0.37**. Defect-on-computed-item variants → 5/9·0.30 + 0.75·0.20 = **0.32**. Defect-on-plain-item variants (e.g. open comment) → 4/9·0.30 + 0.15 = **0.28**. All ≤ 0.5 with margin. If you change weights or item counts, redo this arithmetic.

### 4. `instruction.md`

Static text (no Jinja values — the file still passes through the renderer, so any stray `{{ }}` will be caught by the validator). Contains, in order: the reviewer role and scene sentence; the statement that the packet in `/workspace/sources/` is the only numeric truth; the 8-step review workflow; the matrix table with your nine review questions; the exact output JSON schema (copy the reference schema, adjust `computed_evidence` keys); the rules block (evidence from own recomputation, fail⇒finding, insufficient_data⇒request, not_applicable⇒reason, carried actions have owners, every finding/request/action names one exact RLR item, readiness must reconcile, claim-boundary sentence requirements). Must reference `/workspace/sources/` and `/workspace/output.md` and every `RLR-0X` ID.

Repeat the exact `computed_evidence` key-name contract in the rules block and system prompt. Models often produce useful explanatory keys such as `vms_reading_time_correct_speed_s` or `feeder_voltage_drop_margin_percent`; the verifier should ignore those unless the exact schema keys such as `vms_reading_time_s`, `vms_message_margin_chars`, and `voltage_drop_margin_percent` are present. Add a scaffold test that asserts the instruction and system prompt tell the model not to rename `computed_evidence` keys.

### 5. `system_prompt.md`

Copy the reference: inventory → extract → check → decide → consolidate, budget 8–12 turns, output discipline (one fenced JSON block, never invent missing values).

### 6. `__init__.py`

Two `# ABOUTME:` comment lines. Nothing else.

## TDD Workflow

Write the test file **first** at `tests/templates/test_<template_snake_name>.py`, by copying the reference test file and adapting the constant tables (`TEMPLATE_DIR`, `VARIANT_EXPECTATIONS`, `SOURCE_FILES`, evidence keys, ID lists, and the closure-test regexes/formulas). The required test set — do not drop any of these:

1. Discovery by name, discipline, category, `no-tool`.
2. Numeric variation across 40 seeds (≥10 distinct values of one derived metric) and ≥3 variants observed.
3. Same-seed determinism.
4. Per-variant gold statuses, readiness, and required counts (parametrized over all eight).
5. Clean-variant criterion clearance; genuine-failure exceedance; missing-variant evidence-key omission.
6. Source pack: file set, object IDs, register doc IDs; variant markers (missing field text, revision mismatch, both directions vs clean).
7. **Closure test**: regex-parse the rendered sources, recompute every evidence key with independently written formulas, match gold within 1%.
8. Scaffolded layout: sources under `environment/`, Dockerfile COPY lines, `instance.json` content, custom verify.py present, template system prompt used, no calc script, instruction placeholder-free with both workspace paths and all item IDs.
9. Golden pass scores exactly 1.0 — parametrized over **all eight variants** (find instances by scanning seeds with `_instance_for_variant`).
10. Fluent-unsafe golden fail ≤ 0.5 on clean and on one defect variant.
11. Localization: flip one status in the golden payload → reward < 1.0 and `details["gates"]["matrix"]["items"][<item>]` < 1.0.
12. Anti-gaming: strip `computed_evidence` → reward ≤ 0.6 and readiness gate 0.0; flip readiness to `ready_to_issue` on the failure variant → readiness gate 0.0.

Run cycle (targeted tests only — never the full suite):

```bash
uv run pytest tests/templates/test_<name>.py -q
uv run ruff check src/aec_bench/templates/builtin/<disc>/<name>/ tests/templates/test_<name>.py
uv run ruff format src/aec_bench/templates/builtin/<disc>/<name>/ tests/templates/test_<name>.py
```

Note: this repo formats with `ruff format` (black is not installed). Line limit is 120.

Then the end-to-end check every template must pass before it is claimed:

```bash
uv run aec-bench generate task <template-name> --instances 8 --difficulty medium --seed <seed> --output /tmp/<name>-e2e
for d in /tmp/<name>-e2e/*/*/*/*/; do uv run aec-bench task validate "$d"; done
```

Every instance must report `golden_pass.md scored 1.000` and `golden_fail.md scored ≤ 0.5`, zero errors. Also confirm the eight instances cover ≥4 distinct variants (read `tests/instance.json`).

## Model-Probe Triage: Contract Defect Or Task Difficulty

When a model run scores below 1.0, you must classify the loss before touching anything. There are exactly two categories, and only one of them permits edits.

**Contract defects — fix them, in the named place:**

| Symptom | Correct fix | Wrong fix |
|---|---|---|
| The golden fixture itself cannot score 1.0, or the verifier crashes | Fix verifier or golden builder | — |
| Model uses a synonymous evidence key (`ped_required_time_s` for `ped_clearance_required_s`) | State exact key names in the output schema (generic, all keys) | Per-variant key guidance |
| Model writes `null` for an unrecomputable key | One generic schema rule: omit keys you cannot recompute | Naming which key to omit in which situation |
| Model uses equivalent claim-boundary wording ("does not constitute") | Normalize the *verifier* to accept explicit negation of the required categories | Telling the model the literal phrase to write |
| Identity-ledger credit lost to strict ID matching | Loosen the *verifier* to accept any of the document's legitimate IDs | Instructing which IDs to write in which ledger field |
| Two defensible gold readings of the same packet (a real ambiguity: "is a pending survey value RLR-03 or RLR-04?") | Sharpen the *generic matrix item definitions* so the boundary is decidable from the definitions (e.g. RLR-01 = document presence; RLR-03 = traceability of evidence that is present; RLR-04 = adequacy of the exposed asset, with `insufficient_data` when this check's own input is missing) | Enumerating which defect lands on which item |
| Harness bug (sources not mirrored into the workspace) | Fix the harness; discard the run | — |
| A unit or conversion convention the packet never states (decimal vs 1024, ratio vs percent) | State it in the criteria source file, or make the key name self-documenting (`thermal_utilization_ratio`) | Stating it in instruction/system prompt, or including a worked example whose value approximates any variant's gold evidence |

**Task difficulty — collect it, change nothing:**

- The model cascades one defect into adjacent items (fails RLR-02/03/04/06 for a copied scenario). That is the localization skill under measurement. A sub-1.0 score with the defect correctly found but over-attributed is *evidence*, and among the most valuable this task family produces.
- The model misjudges missing-data semantics (converts a pending value into `fail` instead of `insufficient_data`) even though the generic matrix definitions decide it. Evidence.
- The model applies a wrong convention that the criteria source *does* state. Evidence.
- The model chooses `ready_with_carried_actions` over an unresolved critical blocker. Evidence — this is precisely the unsafe-reviewer behavior the verifier exists to catch. Do not add "missing X means not_ready_to_issue" to the prompt; the generic rule ("unresolved failures or missing critical evidence mean the package is not ready") already covers it.

Rule of thumb: contract fixes make the *grading* fair without changing what a competent reviewer must figure out. If an edit tells the reviewer anything about *this packet's defects*, it is not a contract fix. When in doubt, leave the task alone and record the run.

## Common Failure Modes (All Observed; Check Each One)

1. **Values through the instruction renderer.** Floats get rounded to 2 dp (`0.016` → `0.02`). Never template numerics into `instruction.md`; print them in `build_sources` with explicit format specs matching the quantization grid.
2. **Print/derive drift.** A value printed `:.2f` but quantized on a 0.005 grid loses a digit and breaks closure. Format precision must match the grid everywhere.
3. **Rounding across the criterion boundary.** Deriving a criterion then rounding it toward the computed value can flip pass/fail for corner samples. Always round away from the boundary, and derive failure-variant inputs directly rather than through rounding.
4. **Vacuous linkage.** If the linkage gate only validates the agent's own claims, an all-pass memo passes it trivially. The gold-required-registers check exists precisely to prevent this; keep it.
5. **Variant leakage.** Margin/deficit params visible in any rendered artifact, defect names in file text, or claimed values that only appear in one variant's *formatting* (rather than its content) all leak. Diff sources between variants and confirm only the intended defect differs.
6. **Answer key in the sandbox.** `tool_mode` other than `no-tool` ships the engine as a calc script. Gold state anywhere under `environment/`. Both are catastrophic and silent — test for them.
7. **Zeroed golden_fail.** An empty/zero answer proves nothing about the verifier. The fail fixture must be the strongest fluent adversary so the ≤ 0.5 validator bound is a real claim.
8. **Correlated evidence keys.** Do not add derived keys that are pure arithmetic of other keys (margin = allowable − value) unless one side carries independent information (reading the criteria file). Prefer the criterion + the computed value over the subtraction.
9. **Forbidden-phrase claim scanning.** The claim-boundary statement *negates* claim phrases; scan-for-phrase implementations false-positive on it. Check the positive contract instead.
10. **Multiple flips per variant.** More than one primary flip destroys failure localization and makes gold ambiguous ("is the datum mismatch also an RLR-03 failure?"). One variant, one flipped item, one finding.
11. **Tuning difficulty away.** If a baseline model aces every variant during your checks, the correct response is to make the defect subtler or the evidence sparser — never to pin more conventions into the prompt. Saturation is a defect, not a done-marker.
12. **Boundary-rule leakage.** The gravest observed form of #11: after a sub-1.0 model probe, adding "boundary rules" to the instruction that map the probed defect to its item, status, omitted keys, source citation, and readiness outcome (e.g. "missing revised C-008 chainage: keep RLR-03 pass, set RLR-04 insufficient_data, omit `changed_chainage_delta_m`, request it from MARKUP-SSC01-008"). Each such rule deletes the exact judgment the variant exists to measure, and copying the pattern into sibling templates pre-answers variants no model has even attempted. Apply the probe-triage section instead: verifier-side equivalence fixes, generic definition sharpening, and criteria-source conventions are allowed; defect-to-answer mappings are never allowed. Tests must not assert the presence of such mappings in prompts.
13. **Missing data reclassified as failure.** Models often treat a pending source value as a failed criterion because the package cannot prove adequacy. Fix only the generic matrix definitions and source-owned review discipline: present evidence is traced under RLR-03, adequacy inputs missing from the exposed asset belong under the relevant adequacy item as `insufficient_data`, and unrecomputable evidence keys are omitted. Do not name the specific missing field, expected item, adjacent passes, source citation, or readiness outcome in `instruction.md` or `system_prompt.md`.
14. **Combined item IDs in registers.** Models may write one finding with `"item": "RLR-03, RLR-04"` or one linked action covering multiple matrix rows. Verifiers expect exact item IDs so localization works. The schema rules should say that every finding, information request, and linked action uses one exact single RLR item; multiple affected items require multiple entries.
15. **Missing critical evidence carried as an action.** Models may correctly mark a review item `insufficient_data` but still decide `ready_with_carried_actions`, treating the missing source value as a managed follow-up. Keep the generic rule that unresolved failures or missing critical evidence mean the package is not ready; do not add variant-specific "missing X means not_ready_to_issue" text to the prompt or criteria memo.
16. **Implicit unit conversion conventions.** Models will use reasonable-but-different conventions if the criteria source only says "convert to TB" or "convert units". State the exact conversion basis in the source-owned method, especially decimal vs binary storage, e.g. "decimal TB; divide by 8, then by 1000 twice; do not use 1024." Add a closure or source-text regression test for any conversion that has multiple professional conventions.
17. **Missing evidence emitted as `null`.** Models may understand that a value is unrecomputable but still include the schema key with `null`, `0`, or a placeholder because the example JSON lists every key. The prompt and system prompt may state the generic omit-vs-null schema rule; the verifier should give evidence credit for gold-absent keys only when they are absent from `computed_evidence`. Do not name the variant-specific key that will be missing.
18. **Brittle claim-boundary wording.** Models can state the correct non-claim boundary with equivalent wording such as "does not constitute" rather than the reference phrase "does not claim". The verifier should require the task-owned synthetic scope, explicit negation, and the core boundary categories; it should not require one exact sentence.

## Per-SSC Adaptation Table

The universal variants (missing evidence, stale revision, identity mismatch, scenario copy-forward, two comment variants) apply to every SSC unchanged. This table gives the domain-specific choices: the review product, the exposure check (RLR-04 analogue), example evidence keys, the genuine-failure variant, and where to borrow the math.

| SSC | Review product | Exposure / criterion check | Example evidence keys | Genuine failure | Borrow math from |
|---|---|---|---|---|---|
| SSC-01 | Reference plus three additive companions | Cabinet freeboard vs controlling water level; pedestrian clearance and sight distance vs source criteria; PoE budget for road visual operations; comment-response propagation through drainage, pedestrian, VMS, voltage, and closeout checks | spread, freeboard, runtime, headroom; stopping distance, yellow interval, pedestrian clearance margin; illuminance, network headroom, CCTV storage, PoE headroom, UPS energy; chainage delta, HGL margin, VMS margin, voltage-drop margin, closeout percent | Freeboard deficient; pedestrian clearance deficient; PoE budget exceeded; unsupported downstream repair | `road_low_point_resilience_package`, `intersection_timing_grade_sight_distance_package`, `road_lighting_its_drainage_operations_package`, `multimodal_corridor_review_response_package` |
| SSC-02 | Level crossing warning-time and backup-power packet | Warning time vs approach time at crossing speed | warning_time_s, approach_time_s, battery_runtime_h | Warning-time margin deficient | `level_crossing_warning_backup_power_package` |
| SSC-03 | Detention and outlet design packet | Basin freeboard / HGL clearance at design storm | required_storage_m3, orifice_release_m3_s, freeboard_m | Basin freeboard deficient | `detention_outlet_hgl_package` |
| SSC-04 | Coastal outfall, pump, and electrical elevation packet | Switchboard/pump elevation vs design flood level (tide + SLR + runup) | design_flood_level_m, runup_m, equipment_freeboard_m | Switchboard below design flood level; identity variant = chart datum vs AHD | `coastal_flood_outfall_pump_elevation_package` |
| SSC-05 | Mechanical-load feeder and voltage packet | Voltage drop vs limit at design load | load_kva, feeder_current_a, voltage_drop_pct | Voltage drop exceeds limit | `mechanical_load_feeder_voltage_package` |
| SSC-06 | Pump station duty, power, NPSH, feeder packet | NPSH margin vs required minimum | tdh_m, npsh_available_m, motor_input_kw, voltage_drop_pct | NPSH margin deficient | `pump_station_duty_power_npsh_feeder_package` |
| SSC-07 | Ground structural-electrical safety packet | Bearing capacity FoS vs minimum | corrected_spt, allowable_bearing_kpa, grid_resistance_ohm, touch_voltage_v | Bearing FoS deficient; identity variant = soil strength vs resistivity report confusion | `ground_structural_electrical_safety_package` |
| SSC-08 | Station population, egress, vertical movement packet | Egress capacity/time vs code limit for the population | design_population, egress_time_s, handling_capacity_pph | Egress capacity deficient | `station_population_egress_vertical_package` |
| SSC-09 | Facade wind, bracket, anchor packet | Anchor utilization vs 1.0 at zone pressure | zone_pressure_kpa, bracket_load_kn, anchor_utilization | Anchor over-utilized; identity variant = pressure-zone drift | `facade_wind_bracket_anchor_package` |
| SSC-10 | Wastewater energy island packet | Aeration/oxygen-transfer capacity vs demand | total_oxygen_demand_kg_h, blower_capacity_kg_h, chp_output_kw | Aeration capacity deficient | `wastewater_energy_island_package` |
| SSC-11 | Pump transient and protection packet | Transient pressure vs pipe MAWP | wave_speed_m_s, joukowsky_rise_m, mawp_margin, trip_margin | Transient exceeds MAWP | `pump_transient_protection_package` |
| SSC-12 | Acoustic receiver impact packet | Received level vs criterion per period | swl_db, receiver_spl_dba, criterion_margin_db | Night-time criterion exceeded | `acoustic_receiver_impact_package` |
| SSC-13 | Road visual operations packet | PoE/power budget vs supply; lux vs requirement | avg_lux, uniformity, poe_budget_w, storage_days | PoE budget exceeded | `road_visual_operations_package` |
| SSC-14 | Pipe support and foundation packet | Bearing pressure / anchor shear vs allowable | thrust_kn, support_reaction_kn, bearing_pressure_kpa | Eccentric bearing exceeds allowable | `pipe_transient_support_foundation_package` |
| SSC-15 | Product submittal compliance packet | Certificate coverage and chemistry limits | carbon_equivalent, cert_coverage_count, batch_trace_count | Carbon equivalent exceeds limit (naturally review-first — lean on register/traceability defects) | `product_submittal_compliance_package` |
| SSC-16 | Construction stage controls packet | Sediment basin sizing vs stage catchment | basin_volume_m3, required_volume_m3, temp_power_kw | Basin undersized for the staged catchment | `construction_stage_controls_package` |
| SSC-17 | Pumping outage resilience packet | Backup energy margin through the outage | storm_volume_m3, pumpable_volume_m3, bess_margin_kwh, runtime_h | Backup energy margin negative | `stormwater_pumping_outage_resilience_package` |
| SSC-18 | Control loop and signal packet | Valve Cv vs design case; scaling correctness | required_cv, selected_cv_margin, ma_at_setpoint | Valve Cv insufficient | `control_loop_signal_package` |
| SSC-19 | Fire-water and sprinkler storage packet | Storage volume vs demand × duration | sprinkler_demand_l_min, hydrant_allowance_l_min, storage_margin_m3 | Storage volume deficient | `fire_water_sprinkler_storage_package` |

`SSC-20` gets no template: its authority/criteria content is already embedded in every review task through the criteria-comments file and the claim-boundary contract.

## Acceptance Checklist (Definition Of Done)

A template is claimable when all of the following hold — record them in your completion note:

- [ ] All template tests pass (the twelve-item set above), targeted run.
- [ ] `ruff check` and `ruff format --check` clean on the template and test files.
- [ ] 8 CLI-generated medium instances all pass `aec-bench task validate` (golden 1.000, fluent fail ≤ 0.5, zero errors), covering ≥4 variants.
- [ ] Closure test recomputes every evidence key from rendered sources with independent formulas.
- [ ] You have diffed sources across variants and confirmed only the intended defect differs.
- [ ] Variant-blindness holds: nobody can enumerate the packet variants or their expected statuses from `instruction.md` + `system_prompt.md` alone, and no prompt text maps a specific defect to an item, status, key omission, or readiness outcome.
- [ ] Every post-probe edit is classified under the probe-triage section, and no edit falls in the forbidden column.
- [ ] You have NOT tuned any ambiguity out of the task to make a model score higher.
- [ ] Model-run evidence, when it is collected, is judged by the inverted criteria: goldens at 1.0, at least one strong model below 1.0 somewhere on the variant distribution, and every sub-ceiling run localizing in `details.json`. Models at ceiling everywhere = reopen the template and subtle-ize the defects.

## Non-Claims

Templates produced with this guide are task-owned synthetic review environments. They do not claim accepted project evidence, authority approval, real source-pack parsing, full standards compliance, or benchmark readiness. Completion notes must preserve these non-claims, and generated tasks must keep the claim-boundary contract in their instructions and verifiers.
