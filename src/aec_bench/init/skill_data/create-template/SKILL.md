---
name: create-template
description: Create a new task generation template from a source_task.json seed file. Use when the user wants to add a new benchmark template, convert a seed task into a template, or asks to create/build a template.
---

# Create Template

Create a complete task generation template from a source_task.json seed file. The template includes engine.py (computation), params.toml (parameter space), and instruction.md (agent prompt).

This skill is part of the aec-bench task generation framework. It automates the research and drafting of engineering calculation templates, then guides the user through validation and refinement.

## When to Use

- User runs `/create-template <path_to_source_task.json>`
- User asks to "create a template from this seed" or "convert this seed to a template"
- User wants to add a new benchmark task type to the generation framework

## Input

The skill accepts a path to a `source_task.json` file. These seed files are found under `tasks/` (old-style, from ngnbench imports) or `seeds/` (enhanced, produced by `/add-task`) and contain:

```json
{
  "status": "proposed",
  "seed_origin": "ngnbench",
  "source": {
    "discipline": "ground",
    "task_id": "infinite-slope",
    "task_name": "Infinite Slope Analysis",
    "description": "Calculate FoS for infinite slope failure",
    "inputs": ["Slope angle", "Friction angle", "Cohesion", ...],
    "outputs": ["Factor of Safety FoS"],
    "standards": ["Standard geotechnical texts"],
    "complexity": "low"
  }
}
```

Enhanced seeds (produced by `/add-task`) may include structured inputs/outputs and additional context:

```json
{
  "status": "proposed",
  "seed_origin": "expert",
  "source": {
    "discipline": "electrical",
    "task_id": "cable-sizing-long-runs",
    "task_name": "Cable Sizing for Long Runs",
    "description": "Calculate minimum conductor cross-section for long cable runs",
    "inputs": [
      {"name": "Cable length", "type": "float", "unit": "m"},
      {"name": "Load current", "type": "float", "unit": "A"}
    ],
    "outputs": [
      {"name": "Cross-section", "type": "float", "unit": "mm²"}
    ],
    "standards": ["AS/NZS 3008.1.1"],
    "reference_details": ["AS3008.1.1 Table 3 Column 4"],
    "complexity": "medium",
    "worked_examples": [
      {
        "description": "200m buried cable at 100A",
        "inputs": {"cable_length": 200, "load_current": 100},
        "outputs": {"cross_section": 95}
      }
    ],
    "edge_cases": ["Derating factors apply when more than 3 cables grouped"]
  }
}
```

## Process

### Phase 1 — Autonomous (research + draft)

Work through these steps autonomously. Do NOT ask the user for input during Phase 1.

**Step 1: Parse the seed file.**

Read the source_task.json. Extract all fields from `source`. Determine:

- **Output directory:** `src/aec_bench/templates/builtin/<discipline>/<task_id_underscored>/`
  - Replace hyphens with underscores in task_id for the directory name (e.g., `infinite-slope` → `infinite_slope`)
  - Create the discipline directory if it doesn't exist (e.g., `builtin/electrical/`)
- **Template meta.name:** Keep the task_id hyphenated (e.g., `infinite-slope`)
- **Category:** Derive from `source.category_id` or the second path segment of `source.suggested_relative_path`

**Step 2: Research the formula.**

Use WebSearch to find:
- The exact formula/procedure from the referenced standards
- Typical parameter ranges used in Australian engineering practice
- Lookup tables or correction factors if applicable
- Special cases and boundary conditions
- Worked examples you can use to verify your implementation

When sources conflict or are uncertain, note the uncertainty for Step 9.

If the seed contains `reference_details`, use those specific clause/table references to focus your web search instead of broad searches. For example, search for "AS3008.1.1 Table 3 Column 4 current-carrying capacity" rather than just "AS3008 cable sizing".

If the seed contains `edge_cases`, note them for difficulty design in Step 5 — they often indicate where hidden parameters or progressive difficulty should apply.

**Step 3: Assess feasibility.**

Check these criteria — ALL must pass:

- [ ] **Closed-form computation** — no iteration, no FEM, no optimisation required
- [ ] **Deterministic** — same inputs always produce same outputs, no randomness
- [ ] **Parameterisable inputs** — all inputs are numeric (float/int) or categorical (enum)
- [ ] **Numeric outputs** — all outputs are numbers comparable with tolerances
- [ ] **Single compute() call** — entire calculation fits in one function

If ANY check fails, **STOP**. Explain to the user why this seed can't be templated and suggest what would need to change (e.g., "This requires iterative pile capacity analysis — not suitable for a single `compute()` call").

**Step 4: Draft engine.py.**

Read `references/template-contract.md` for the exact rules.
Read `references/example-engine.md` for the annotated pattern.

Write engine.py to the output directory. Key requirements:
- ABOUTME 2-line header
- `_validate_inputs()` function with ValueError for each invalid param
- Pure `compute()` function returning `dict[str, float]`
- Lookup tables as module-level constants
- All outputs `round(value, 2)`
- Only `import math` (stdlib only)

If the seed contains structured `inputs` with types and units, use those to inform parameter naming and validation. For example, `{"name": "Cable length", "type": "float", "unit": "m"}` suggests a parameter named `cable_length_m` with float validation.

**Step 5: Draft params.toml.**

Read `references/template-contract.md` for TOML-specific rules. Critical points:
- Use `min`/`max` in TOML (NOT `min_value`/`max_value`)
- Archetype param ranges are flat siblings of `description` (NOT nested under `params`)
- Difficulty extra keys go into the `extra` dict — use for constraints
- Enum values are always strings, even for numeric-looking values
- Add `site_contexts` to every archetype (required field)

Design decisions:
- Choose archetypes that produce physically realistic parameter combinations
- Design 3 difficulty presets with progressive complexity
- Set tolerances: 0.03 for calculated values, 0.01 for exact lookups, 0.05 for interpolated

If the seed contains structured inputs with categorical values (e.g., `"values": ["buried", "in-tray", "in-conduit"]`), use those directly as enum values in params.toml instead of researching from scratch.

**Step 6: Draft instruction.md.**

Follow the pattern from existing templates (read one in `references/example-engine.md` or from the builtin directory). Use Jinja2 conditionals for hidden params and tool availability. Output JSON keys must exactly match `compute()` return dict keys.

**Step 7: Create `__init__.py`.**

Write a 2-line ABOUTME package marker to the output directory.

---

### Phase 2 — Interactive (validate + refine)

Now involve the user.

**Step 8: Validate.**

Run validation and report results:

```bash
uv run aec-bench generate validate-template <template_dir>
```

Also call `compute()` directly with sample inputs from each difficulty preset's archetypes. Show the inputs and outputs so the user can verify the numbers make engineering sense.

If the seed contains `worked_examples`, use those as validation inputs for `compute()`. Compare your computed outputs against the expert's expected outputs. Flag any discrepancies — they may indicate a formula error, a different edition of the standard, or rounding differences. Worked examples from the expert are higher-confidence test cases than web-sourced examples.

**Step 9: Present to the user.**

Show a summary:

1. **Template location** — directory and files created
2. **Sample outputs** — `compute()` results for each difficulty level with the inputs used
3. **Concerns** — flag any coefficients, lookup values, or formula details that came from web search and should be verified against authoritative sources
4. **Seed outputs vs. template outputs** — note if you added intermediate outputs beyond what the seed specified (e.g., seed says "Factor of Safety" but template also outputs driving/resisting stresses)
5. **Next steps** — write tests with independently verified expected values, generate instances, run through Harbor

**Step 10: Iterate.**

If the user requests changes:
1. Apply the changes to the relevant files
2. Re-run `validate-template`
3. Show updated sample outputs
4. Repeat until satisfied

**Step 11: Generate a test instance.**

```bash
uv run aec-bench generate task <meta.name> --instances 1 --seed 42 --output /tmp/template-preview/
```

Show the generated `instruction.md` with concrete parameter values so the user can see exactly what an agent would receive.

## Reference Files

Read these during execution:

- `references/template-contract.md` — Rules for producing correct engine.py, params.toml, instruction.md
- `references/example-engine.md` — Annotated Terzaghi and SPT engines showing every pattern decision
