# Maritime (IACS CSR / Class-Society) Task Contribution Guide

A practical checklist for adding maritime benchmark tasks (IACS Common
Structural Rules, class-society notations, and similar rulebook-driven
calculations) without drifting from aec-bench's quality bar. It does not
replace [`docs/tasks-guide.md`](tasks-guide.md), [`docs/INVARIANTS.md`](INVARIANTS.md),
or the `/add-task`, `/create-template`, `/hardening-pass`, `/domain-check`
skills — it cross-references them for the maritime-specific pitfalls.

---

## 1. Sourcing rule (non-negotiable)

Every equation, coefficient, and table value must be **transcribed from the
actual IACS CSR PDF**, not reconstructed from memory or from a web summary.

- Pin the edition in every reference: currently **CSR-H, 01 JUL 2025**. Any
  clause citation that doesn't carry an edition date is incomplete.
- Cite the full clause path: `Part / Chapter / Section / §` (e.g.
  `Pt 1 Ch 1 Sec 4 §3.1.1`), plus the PDF page number where practical.
- `pdftotext -layout` frequently garbles fractions, subscripts, and
  multi-line formulas in class-society PDFs. **If a formula looks garbled
  or ambiguous after text extraction, render that PDF page to an image and
  read it visually before writing any code.** Do not guess at a coefficient
  because the text extraction was unclear.
- Never reconstruct a coefficient, table value, or clamp bound "from
  engineering judgement" or recollection of similar rules (e.g. IACS UR,
  class NKs, or other societies' rules). If you can't find it verbatim in
  the pinned edition, the task is not ready.

This rule exists because an earlier unsourced maritime task attempt was
discarded for exactly this reason — treat it as load-bearing, not
bureaucratic.

---

## 2. Terminology

Use the rulebook's own symbols and subscripts verbatim — don't rename them
to look more "Pythonic":

- `L` (Rule length), `L_LL` (freeboard length), `L_PP` (length between
  perpendiculars), `L0`, `L1`, `L2` (regime-specific lengths), `B` (breadth),
  `D` (depth), `T` (draught), `T_SC` (scantling draught), `Δ` (displacement),
  `C_B` (block coefficient), `V` (speed), etc.
- Rule length is capital `L`, not `l` or `RuleLength`.
- Match output keys to the rule's own notation where practical — e.g. the
  Rule length output key is `rule_length_L_m`, not `rule_length` or `L_m`.
- If the rulebook only describes a quantity in prose (no symbol given),
  name the param/output from that prose, in the same style used elsewhere
  in the template (e.g. `stem_to_rudder_stock_distance_m`,
  `extreme_length_on_waterline_at_TSC_m`).

---

## 3. Rules-compliant artifact checklist

Full field-level rules live in
[`src/aec_bench/init/skill_data/create-template/references/template-contract.md`](../src/aec_bench/init/skill_data/create-template/references/template-contract.md).
Summary for maritime tasks specifically:

- [ ] **Seed** — `seeds/maritime/<task-id>/source_task.json`, conforming to
      `seeds/seed_schema.json` (see
      [`add-task/references/seed-schema.md`](../src/aec_bench/init/skill_data/add-task/references/seed-schema.md)).
      `status: "proposed"`, structured `inputs`/`outputs`, `reference_details`
      with the verbatim clause quote, ≥2 worked examples computed by hand
      (or independently) from the PDF, `feasibility` block.
- [ ] **Template `engine.py`** — pure function, **stdlib only** (no
      third-party imports), two ABOUTME header lines, `_validate_inputs()`
      raising `ValueError` for physically impossible inputs, **every
      returned output wrapped in `round(x, 2)`**. Categorical/enum params
      (e.g. `has_rudder_stock`) arrive from the generator as **strings**
      (`"true"` / `"false"`), never real booleans — normalize them inside
      the engine (see `_normalize_has_rudder_stock` in
      `src/aec_bench/templates/builtin/maritime/rule_length/engine.py` for
      the pattern). Do not assume Python truthiness on the raw param.
- [ ] **`params.toml`** — `[meta]` with pinned `standards`; `[params.*]`
      using `min`/`max` (never `min_value`/`max_value`); `[outputs.*]` with
      `tolerance`; `[archetypes.*]` with **flat** min/max ranges (not
      nested under a `params` sub-table) plus `site_contexts`;
      `[difficulty.*]` for easy/medium/hard. Enum `values` are always
      strings, even when they look boolean or numeric.
- [ ] **`instruction.md`** — Jinja2 template; guard every hideable param
      with `{% if <param> is defined %}`; the JSON output block's keys
      must exactly match the keys returned by `compute()`; ends with an
      instruction to write the solution to `/workspace/output.md`.
- [ ] **Instance(s)** under `tasks/maritime/<task-id>/<instance-name>/`:
      `task.toml`, a fully-resolved `instruction.md` (no `{{`/`{%` left,
      no placeholders), `tests/verify.py` (self-contained, tolerance-based),
      `tests/test.sh`, `tests/fixtures/golden_pass.md` and
      `golden_fail.md`, `environment/Dockerfile`, optionally
      `solution/solve.py`.
- [ ] Lifecycle starts at `proposed` (see promotion criteria in
      [`tasks-guide.md`](tasks-guide.md#lifecycle-and-visibility)).
- [ ] **Clean-instance rule**: at least 1 clean instance per 3 total
      instances of the task type (an instance with no true issues that
      still requires schema-valid output — tests false-positive
      resistance).

---

## 4. Verification (the step that catches generation bugs)

Static reading of `engine.py`/`params.toml` is not enough — the generator's
categorical and hidden-param code paths only run when you actually generate
instances. Run all of these, in order:

1. `uv run aec-bench generate validate-template <template_dir>` — structural
   validation of the template files.
2. `uv run aec-bench generate task <name> --instances N` — **run this for
   real, not just with `--dry-run`.** `--dry-run` skips codepaths that
   resolve enum/categorical values and hidden-param substitution; only a
   real generation run exercises them end-to-end.
3. The engine's unit test (e.g. `tests/templates/test_<name>_engine.py`) —
   assert `compute()` against the seed's worked examples.
4. The instance verifier against both golden fixtures:
   `tests/fixtures/golden_pass.md` must score as passing,
   `tests/fixtures/golden_fail.md` must score as failing.
5. `/hardening-pass` on the template (and again on each instance) —
   catches formula drift, unrealistic archetype ranges, and tolerance
   miscalibration.
6. `/domain-check` — confirms the new files respect the dependency
   directions and invariants in `docs/INVARIANTS.md` (e.g. templates stay
   pure computation, no upward imports).

---

## 5. Discipline registration

`maritime` must already be present everywhere the discipline enum is
duplicated: `SeedSource` (contracts), `LibraryEntryBase` (contracts), and
`seeds/seed_schema.json`. The introspection guard test
`tests/contracts/test_discipline_consistency.py` enforces this — it must
stay green. If you're the first to add a maritime task and the test fails,
that's a signal the discipline needs registering upstream, not that the
test is wrong.

---

## 6. Commits / PR

- Use conventional commit prefixes: `feat:` for a new task/template,
  `fix:` for a correction to an existing one, `docs:` for guide-only
  changes, `test:` for test-only additions.
- Keep the seed, template, and instance changes in separate, reviewable
  commits where practical.
- If you only have pull (read-only) access to the main repository, fork
  it and open a pull request from your fork rather than pushing a branch
  directly.
