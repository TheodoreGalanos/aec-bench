<!-- ABOUTME: Contract specification for producing correct engine.py, params.toml, and instruction.md files. -->
<!-- ABOUTME: Covers exact field mappings, validation rules, and Jinja2 patterns for task generation templates. -->

# Template Contract Reference

This document defines the exact rules for producing the three files that constitute a valid task generation template: `engine.py`, `params.toml`, and `instruction.md`. A template directory must contain all three.

---

## 1. engine.py Contract

### Signature

The file MUST define a module-level callable named `compute`. The sampler calls it as:

```python
ground_truth: dict[str, float] = engine_compute(**all_params)
```

where `all_params` is a dict whose keys are exactly the param names declared in `params.toml` and whose values are `float | int | str`.

Therefore `compute()` MUST:

- Accept one keyword argument for every param declared in `[params.*]`.
- Return `dict[str, float]` whose keys are exactly the output names declared in `[outputs.*]`.

### Pure Function Rules

- `compute()` must be a **pure function**: same inputs always produce same outputs, no side effects.
- It must NOT read files, access the network, mutate global state, or print.
- All imports must be from the Python standard library only (`math`, `typing`, etc.). No third-party packages.

### Validation Pattern

Define a private `_validate_inputs()` function that raises `ValueError` with a clear message for invalid inputs. Call it at the top of `compute()`.

```python
def _validate_inputs(param_a: float, param_b: float) -> None:
    """Raise ValueError for invalid input parameters."""
    if param_a < 0:
        msg = "param_a must be >= 0"
        raise ValueError(msg)
```

### Lookup Tables

When the engineering method uses tabulated values (e.g., bearing capacity factors, correction factors), define them as module-level constants:

```python
_FACTOR_TABLE: list[tuple[float, float, float]] = [
    (0, 5.7, 1.0),
    (5, 7.3, 1.6),
    ...
]
```

Provide an interpolation helper when the method requires values between table entries.

### Rounding

All returned values MUST be rounded to 2 decimal places:

```python
return {
    "output_a": round(value_a, 2),
    "output_b": round(value_b, 2),
}
```

This matches the instruction renderer, which also rounds visible float params to 2dp for human-readable instructions.

### Enum Parameters

Enum params arrive as `str`. Use `typing.Literal` for the type hint and validate against allowed values:

```python
def compute(
    footing_shape: Literal["strip", "square", "circular"],
    ...
) -> dict[str, float]:
```

### Optional Parameters with Defaults

If a param has `optional = true` and/or `default` in params.toml, give the corresponding `compute()` kwarg a default value:

```python
def compute(
    water_table_depth_m: float = 100.0,
    factor_of_safety: float = 3.0,
    ...
) -> dict[str, float]:
```

### File Header

Every engine.py MUST start with two ABOUTME comment lines:

```python
# ABOUTME: <What computation this engine performs>.
# ABOUTME: <What method/standard it implements>.
```

---

## 2. params.toml Contract

### Top-Level Sections

A valid params.toml has these TOML sections (in order):

```toml
[meta]           # Required. Template metadata.
[params.*]       # Required. One sub-table per parameter.
[outputs.*]      # Required. One sub-table per expected output.
[archetypes.*]   # Optional. Named parameter-range presets.
[difficulty.*]   # Optional. Difficulty level configurations.
[constraints]    # Optional. Constraint expressions (Phase 2).
```

### [meta] Section

Maps to `TemplateMeta`. All fields required except `standards` and `tags`:

| TOML key      | Pydantic field | Type           | Required | Notes                                    |
|---------------|----------------|----------------|----------|------------------------------------------|
| `name`        | `name`         | `str`          | Yes      | Kebab-case. Used as calc script filename. |
| `description` | `description`  | `str`          | Yes      | One-line summary.                        |
| `discipline`  | `discipline`   | `str`          | Yes      | e.g., `"ground"`, `"structural"`         |
| `category`    | `category`     | `str`          | Yes      | e.g., `"shallow-foundations"`            |
| `standards`   | `standards`    | `list[str]`    | No       | Reference standards/papers.              |
| `tags`        | `tags`         | `list[str]`    | No       | Searchable tags.                         |
| `tool_mode`   | `tool_mode`    | `ToolMode`     | Yes      | `"with-tool"`, `"no-tool"`, or `"both"` |

The `meta.name` value determines the generated CLI tool filename: `{name}_calc.py` (with hyphens replaced during the calc script generation, but the TOML value itself is kebab-case).

### [params.*] Section

**CRITICAL TOML-to-Pydantic Field Mapping:**

The TOML file uses `min` and `max`. The Pydantic model (`ParamSpec`) uses `min_value` and `max_value`. The registry's `_remap_param_spec()` function performs this translation automatically. You MUST write `min` and `max` in TOML, never `min_value` or `max_value`.

| TOML key         | Pydantic field   | Type             | Required                       | Notes                                          |
|------------------|------------------|------------------|--------------------------------|-------------------------------------------------|
| `type`           | `type`           | `ParamType`      | Yes                            | `"float"`, `"int"`, or `"enum"`                |
| `description`    | `description`    | `str`            | Yes                            | Human-readable description.                    |
| `unit`           | `unit`           | `str \| None`    | No                             | Physical unit string, e.g., `"kPa"`, `"m"`.    |
| `min`            | `min_value`      | `float \| None`  | Yes for `float` and `int`      | TOML uses `min`, model uses `min_value`.        |
| `max`            | `max_value`      | `float \| None`  | Yes for `float` and `int`      | TOML uses `max`, model uses `max_value`.        |
| `values`         | `values`         | `list[str] \| None` | Yes for `enum`              | List of allowed string values.                  |
| `default`        | `default`        | `Any \| None`    | No                             | Default value (mirrors engine.py default).      |
| `optional`       | `optional`       | `bool`           | No                             | Defaults to `false`.                            |
| `derivable_from` | `derivable_from` | `str \| None`    | No                             | Hint that value can be inferred (see below).    |

#### Validation Rules (enforced by `ParamSpec.validate_type_constraints`):

- `float` and `int` params **require** both `min` and `max`.
- `enum` params **require** a non-empty `values` list.
- `enum` params must NOT have `min` or `max`.

#### Enum Values Are Always Strings

Even when enum choices look numeric (e.g., borehole diameters), they MUST be strings in TOML:

```toml
[params.borehole_diameter_mm]
type = "enum"
description = "Borehole diameter"
values = ["65", "115", "150", "200"]
```

The sampler returns enum values as `str`. The engine receives them as `str`.

#### `derivable_from` Semantics

When `derivable_from = "archetype"`, it signals that the parameter's value can be inferred from the archetype context (e.g., soil type implies cohesion range). This is informational metadata used during difficulty design — at "hard" difficulty, params with `derivable_from = "archetype"` are typically placed in `hidden_params`, and the agent must infer them from the site description.

### [outputs.*] Section

Maps to `OutputSpec`. Each output key MUST match a key in `compute()`'s return dict.

| TOML key      | Pydantic field | Type    | Required | Notes                                       |
|---------------|----------------|---------|----------|---------------------------------------------|
| `description` | `description`  | `str`   | Yes      | Human-readable output name.                 |
| `tolerance`   | `tolerance`    | `float` | No       | Default: `0.03` (3% relative tolerance).    |

The tolerance value is used by the generated verifier to grade the agent's answer against ground truth.

### [archetypes.*] Section

**CRITICAL: Flat Structure, NOT Nested Under `params`**

Archetype param ranges are written as **flat keys** alongside `description` and `site_contexts`. They are NOT nested under a `params` sub-table. The registry's `_parse_archetype_spec()` collects any key that is a dict with `min` and `max` into the `ArchetypeSpec.params` field automatically.

Correct TOML:

```toml
[archetypes.soft_nc_clay]
description = "Soft normally consolidated clay"
cohesion_kpa = {min = 5, max = 15}
friction_angle_deg = {min = 0, max = 5}
unit_weight_kn_m3 = {min = 15, max = 17}
site_contexts = ["brisbane-alluvial", "darwin-estuarine"]
```

**WRONG** (do NOT do this):

```toml
[archetypes.soft_nc_clay]
description = "Soft clay"
site_contexts = ["brisbane"]
[archetypes.soft_nc_clay.params]      # WRONG - no nested params table
cohesion_kpa = {min = 5, max = 15}
```

The flat keys that have `{min = ..., max = ...}` structure are detected by `_parse_archetype_spec()` and collected into `ArchetypeSpec.params` as `ArchetypeRange` objects.

Archetype param range keys MUST match declared `[params.*]` names exactly.

`site_contexts` is a list of strings used to generate human-readable instance names and context descriptions. Each entry represents a plausible geographic/geologic setting for that archetype.

### [difficulty.*] Section

Maps to `DifficultyPreset`. Convention is to define `easy`, `medium`, and `hard`.

**Known fields** (handled by `_parse_difficulty_preset`):

| TOML key           | Pydantic field     | Type                | Required | Notes                                         |
|--------------------|--------------------|---------------------|----------|-----------------------------------------------|
| `description`      | `description`      | `str`               | Yes      | Human-readable difficulty description.        |
| `visibility`       | `visibility`       | `VisibilityLevel`   | Yes      | `"all_given"`, `"partial"`, `"scenario_only"` |
| `archetypes`       | `archetypes`       | `list[str]`         | Yes      | Which archetypes are valid at this level.      |
| `hidden_params`    | `hidden_params`    | `list[str]`         | No       | Params hidden from the agent.                 |
| `replacement_text` | `replacement_text` | `str \| None`       | No       | Text shown instead of hidden params.           |

**Visibility validation:** `"partial"` visibility REQUIRES at least one entry in `hidden_params`.

#### Difficulty Extras Pattern

**Any key in a `[difficulty.*]` section that is NOT in the known fields set becomes an `extra` entry.** The registry's `_parse_difficulty_preset()` splits the raw TOML into known fields and everything else, putting the rest into `DifficultyPreset.extra: dict[str, Any]`.

The sampler consumes extras in two ways:

1. **List constraint:** If `extra[param_name]` is a list, the sampler restricts that param to `rng.choice(extra[param_name])` instead of sampling from the full range. Example:

   ```toml
   [difficulty.easy]
   footing_shape = ["strip"]        # Only strip footings at easy difficulty
   ```

2. **Boolean disable:** If `extra[key]` is `false` and a param name starts with that key, the sampler sets the param to its `max_value` (effectively disabling it). Example:

   ```toml
   [difficulty.easy]
   water_table = false              # Sets water_table_depth_m to its max (100m = no water table)
   ```

   The prefix matching rule: `param_name.startswith(extra_key)` — so `water_table = false` affects `water_table_depth_m`.

Extra keys that are `true` are allowed but have no special sampler behavior (they exist as metadata).

### Constraints Section

Optional. Either a flat list at the top level or a section with a `rules` key:

```toml
constraints = ["rule1", "rule2"]
# OR
[constraints]
rules = ["rule1", "rule2"]
```

Constraint evaluation is deferred to Phase 2.

---

## 3. instruction.md Contract

### Jinja2 Template Syntax

The instruction.md file is a Jinja2 template rendered by the instruction renderer. It receives these context variables:

#### Direct Param Access

Every param declared in `[params.*]` is available as a top-level template variable by its param name. Float values are pre-rounded to 2 decimal places.

```jinja2
| Footing width (B) | {{ footing_width_m }} | m |
| Footing shape | {{ footing_shape }} | - |
```

#### Structured Context Variables

| Variable              | Type            | Description                                              |
|-----------------------|-----------------|----------------------------------------------------------|
| `visible_params`      | `list[dict]`    | Each dict has `name`, `value`, `unit`, `description`.    |
| `outputs`             | `list[dict]`    | Each dict has `name`, `description`.                     |
| `standards`           | `list[str]`     | From `meta.standards`.                                   |
| `tool_mode`           | `str`           | String value of `ToolMode`.                              |
| `tool_available`      | `bool`          | `True` if tool_mode is `with-tool` or `both`.            |
| `archetype`           | `dict`          | Has `description` (str) and `site_context` (str).        |
| `archetype_description` | `str`         | Human-readable archetype description.                    |
| `site_context`        | `str`           | The selected site context string.                        |
| `meta`                | `dict`          | Full `TemplateMeta` as a dict (name, discipline, etc.).  |

### Conditional Blocks for Hidden Params

Use Jinja2 `{% if ... is defined %}` guards around params that may be hidden at harder difficulties. When a param is in `hidden_params`, it is removed from `visible_params` and is not injected as a direct-access variable. Use `is defined` to test whether a param should be shown:

```jinja2
{% if cohesion_kpa is defined %}
| Effective cohesion (c') | {{ cohesion_kpa }} | kPa |
{% endif %}
```

**Important:** The renderer only exposes visible param values as direct template variables. Hidden params remain available to the engine and verifier, but not to the instruction template through names like `{{ cohesion_kpa }}`. The `is defined` pattern is the intended way to exclude hidden params from generated instructions.

### Archetype Description Block

When params are hidden, a site description replaces them. Include a conditional block:

```jinja2
{% if archetype_description is defined %}

### Site Conditions

{{ archetype_description }}
{% endif %}
```

The `replacement_text` from `DifficultyPreset` is a Jinja2 template itself that can reference `{{ archetype.description }}` and `{{ archetype.site_context }}`.

### Tool Section

Conditionally include tool usage instructions:

```jinja2
{% if tool_available %}
## Available Tool

A calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}
```

**Tool filename convention:** The scaffolder generates the calc script as `{meta.name}_calc.py` where `meta.name` is the kebab-case template name from `[meta]`. However, because the scaffolder uses `config.meta.name` directly and the CLI wrapper generator builds argparse flags from param names, the tool script name in the instruction should reference `{{ meta.name }}_calc.py` (note: hyphens in the name are preserved in the filename).

### Output Format Section

Every instruction MUST end with:

1. A "Required" section listing what to calculate (matching `[outputs.*]` keys).
2. An "Output Format" section specifying the exact JSON keys the agent must produce.
3. A directive to write the solution to `/workspace/output.md`.

```jinja2
## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "output_key_a": <numeric_value>,
  "output_key_b": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
```

The JSON keys in the output format MUST exactly match the keys in `[outputs.*]` (and therefore the keys returned by `compute()`).

### Role Preamble

Start with a role statement that sets the engineering context:

```
You are a senior geotechnical engineer specializing in <domain>.
```

### Constraints Section

Include a "Constraints" section with:
- No internet access statement.
- The specific equations/method the agent must use (matching the engine's implementation).
- Any physical constants (e.g., `gamma_w = 9.81 kN/m3`).
- Special cases the agent should handle (e.g., `phi = 0` for undrained clay).

---

## Validation Checklist

Before considering a template complete, verify:

- [ ] `engine.py` has `compute()` accepting all `[params.*]` as kwargs
- [ ] `engine.py` returns dict with keys matching all `[outputs.*]` names
- [ ] All returned values are `round(..., 2)`
- [ ] `engine.py` has `_validate_inputs()` and calls it
- [ ] `engine.py` uses only stdlib imports
- [ ] `engine.py` has two ABOUTME header lines
- [ ] `params.toml` uses `min`/`max` (NOT `min_value`/`max_value`)
- [ ] All `enum` params have `values` as a list of strings
- [ ] All `float`/`int` params have both `min` and `max`
- [ ] Archetype param ranges are flat keys (NOT nested under `[archetypes.*.params]`)
- [ ] Archetype param range keys match declared `[params.*]` names
- [ ] Difficulty extras for enum constraints are lists of strings
- [ ] Difficulty extras for boolean disables use `false` with correct prefix
- [ ] `"partial"` visibility has at least one `hidden_params` entry
- [ ] `instruction.md` JSON output keys match `[outputs.*]` keys exactly
- [ ] `instruction.md` has `{% if ... is defined %}` guards for hideable params
- [ ] `instruction.md` has conditional `{% if tool_available %}` tool section
- [ ] `instruction.md` ends with output format and `/workspace/output.md` directive
