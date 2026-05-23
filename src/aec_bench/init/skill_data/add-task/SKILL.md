---
name: add-task
description: Create a new benchmark task seed from an expert description. Use when the user wants to add a new task, describe a task idea, or create a seed file for the generation framework.
---

# Add Task

Create a structured benchmark task seed (`source_task.json`) from an expert's description. The skill interviews the expert, validates the captured information, assesses whether the task can be automated via templates, and writes a seed file that feeds into the generation pipeline.

## When to Use

- User runs `/add-task` or `/add-task <description>`
- User asks to "add a task", "create a task", "define a new benchmark task"
- User describes an engineering calculation they want to benchmark

## Process

### Step 1 — Capture or Request Description

Check the arguments passed to the skill.

**If a description was provided:** Extract what you can — discipline, task type, inputs, outputs, standards, complexity. Note what's missing and proceed to Step 2 for targeted follow-ups.

**If no description was provided (or just a greeting):** Ask the expert to describe the task they want to create:
- What does it test?
- What engineering knowledge is needed?
- What would a correct answer look like?

Wait for their response before proceeding.

### Step 2 — Targeted Interview

Read `references/seed-schema.md` to understand the full field list.

Ask follow-up questions for any fields not yet captured. Ask one or two questions at a time — keep it conversational, not like filling out a form.

**Core fields (must collect all):**
- **Discipline**: one of civil, electrical, ground, mechanical, structural
- **Task ID**: suggest a hyphenated slug derived from the task name (e.g., "Cable Sizing for Long Runs" → `cable-sizing-long-runs`)
- **Task name**: human-readable name
- **Description**: one paragraph explaining what the task tests
- **Inputs**: named parameters with types (float, int, categorical) and units. Ask: "What values would an engineer need to plug in?"
- **Outputs**: named results with units. Ask: "What does the calculation produce?"
- **Standards**: referenced codes/standards. Ask for specific ones, not just "Australian Standards"
- **Complexity**: low, medium, or high. Explain: low = straightforward formula, medium = multiple steps or table lookups, high = many interacting parameters or multi-stage calculation

**Extended fields (actively probe for these):**
- **Worked examples**: Ask for at least 2 concrete input → output pairs with real numbers. Say: "Can you give me a worked example with actual numbers? For instance: 'for a 200m cable run at 100A, the answer should be 95mm²'"
- **Edge cases**: Ask: "Are there any gotchas or boundary conditions an engineer should watch for?"
- **Reference details**: Ask: "Can you point me to specific clause or table numbers? For example, not just 'AS3008' but 'AS3008.1.1 Table 3, Column 4'"

### Step 3 — Sanity Check

Before saving, present a summary table to the expert:

```
┌──────────────────────────────────────────────────┐
│ Task: <task_name>                                │
│ Discipline: <discipline>    Complexity: <level>  │
├──────────────────────────────────────────────────┤
│ Inputs (<count>)         │ Outputs (<count>)     │
│ ✓ <name> [<unit>]        │ ✓ <name> [<unit>]     │
│ ...                      │ ...                   │
├──────────────────────────────────────────────────┤
│ Worked Examples                                  │
│ ✓ <summary of each example>                     │
│ ⚠ <warnings if applicable>                      │
├──────────────────────────────────────────────────┤
│ Feasibility: <result>                            │
│ References: <count> specific refs                │
│ Edge cases: <count> captured                     │
└──────────────────────────────────────────────────┘
```

**Flag warnings for:**
- Fewer than 2 worked examples
- No specific clause/table references (just standard names)
- Low input count for stated complexity (e.g., 2 inputs but "high" complexity)
- No edge cases captured
- Missing units on inputs or outputs

Ask the expert to confirm or correct.

### Step 4 — Feasibility Assessment

Read `references/feasibility-criteria.md`.

Assess the task against the 5 parameterisability criteria based on the description and inputs/outputs:

1. **Closed-form computation** — no iteration, no FEM, no optimisation
2. **Deterministic** — same inputs always produce same outputs
3. **Parameterisable inputs** — all inputs are numeric or categorical
4. **Numeric outputs** — all outputs are numbers comparable with tolerances
5. **Single compute() call** — entire calculation fits in one function

Report the result to the expert with explanation. Show which criteria pass/fail.

### Step 5a — Parameterisable Path

If ALL 5 criteria pass:

1. Create the directory `seeds/<discipline>/<task-id>/`
2. Write `source_task.json` with:
   - `status`: "proposed"
   - `seed_origin`: "expert"
   - `created_by`: the expert's name if mentioned, otherwise omit
   - `source`: all collected fields using structured format for inputs/outputs
   - `feasibility`: the assessment results (parameterisable: true, all 5 criteria: true)
3. Tell the expert: "Seed saved to `seeds/<discipline>/<task-id>/source_task.json`"
4. Offer: "This task is parameterisable — I can create a generation template from it right now using `/create-template`. Want me to proceed?"
5. If the expert accepts, run: `/create-template seeds/<discipline>/<task-id>/source_task.json`
6. If declined, say: "No worries — you can run `/create-template seeds/<discipline>/<task-id>/source_task.json` any time."

### Step 5b — Non-Parameterisable Path

If ANY criterion fails:

1. Create the directory `seeds/<discipline>/<task-id>/`
2. Write `source_task.json` with feasibility.parameterisable set to false and notes explaining which criteria failed
3. Explain to the expert which criteria failed and why this task can't be automated into a generation template
4. Read `references/manual-task-guidance.md` and present the guidance — what files they need to create manually, the reward shape convention, and pointers to existing examples

## Output Location

Seeds are written to: `seeds/<discipline>/<task-id>/source_task.json`

The `seeds/` directory is tracked in git. Commit the seed after creation.

## Reference Files

Read these during execution:

- `references/seed-schema.md` — Enhanced seed format, all fields, and examples
- `references/feasibility-criteria.md` — The 5 parameterisability criteria with pass/fail examples
- `references/manual-task-guidance.md` — Guidance for manually building non-parameterisable tasks
