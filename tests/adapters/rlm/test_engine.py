# ABOUTME: Tests for the RLM REPL execution engine.
# ABOUTME: Covers code block parsing, persistent execution state, and output truncation.
"""Tests for the RLM REPL execution engine."""

from aec_bench.adapters.rlm.engine import (
    ReplEnvironment,
    parse_code_block,
    parse_code_blocks,
    truncate_after_first_block,
)


def test_parse_code_block_extracts_repl_fenced_code() -> None:
    model_output = """Let me explore the data.

```repl
x = 2 + 2
print(x)
```

That should give us 4."""
    code = parse_code_block(model_output)
    assert code == "x = 2 + 2\nprint(x)"


def test_parse_code_block_ignores_python_blocks() -> None:
    model_output = """```python
result = [i**2 for i in range(5)]
```"""
    code = parse_code_block(model_output)
    assert code is None  # only ```repl is executable


def test_parse_code_block_returns_none_when_no_code() -> None:
    model_output = "I think the answer is 42."
    code = parse_code_block(model_output)
    assert code is None


def test_parse_code_block_extracts_last_block_when_multiple() -> None:
    model_output = """```repl
x = 1
```
Some text.
```repl
y = 2
```"""
    code = parse_code_block(model_output)
    assert code == "y = 2"


def test_parse_code_block_ignores_bare_fenced_code() -> None:
    model_output = """Some reasoning.

```
x = 42
print(x)
```"""
    code = parse_code_block(model_output)
    assert code is None  # only ```repl is executable


def test_parse_code_blocks_returns_all_repl_blocks() -> None:
    model_output = """```repl
x = 1
```
Some text.
```repl
y = 2
```
More text.
```repl
z = x + y
```"""
    blocks = parse_code_blocks(model_output)
    assert len(blocks) == 3
    assert blocks[0] == "x = 1"
    assert blocks[1] == "y = 2"
    assert blocks[2] == "z = x + y"


def test_parse_code_blocks_ignores_non_repl() -> None:
    model_output = """```repl
x = 1
```

```json
{"key": "value"}
```

```python
y = 2
```"""
    blocks = parse_code_blocks(model_output)
    assert len(blocks) == 1
    assert blocks[0] == "x = 1"


def test_truncate_after_first_block_keeps_first_only() -> None:
    text = """Let me start.

```repl
x = 1
```

Now compute.

```repl
y = x * 2
```

Done.

```repl
FINAL_VAR(y)
```"""
    truncated = truncate_after_first_block(text)
    assert "x = 1" in truncated
    assert "y = x * 2" not in truncated
    assert "FINAL_VAR" not in truncated
    assert truncated.endswith("```")


def test_truncate_preserves_text_before_block() -> None:
    text = """Some reasoning here.

```repl
print(HELP())
```

More blocks follow.

```repl
print(DOCS())
```"""
    truncated = truncate_after_first_block(text)
    assert "Some reasoning here." in truncated
    assert "print(HELP())" in truncated
    assert "print(DOCS())" not in truncated


def test_truncate_returns_unchanged_when_no_blocks() -> None:
    text = "Just some text, no code blocks."
    assert truncate_after_first_block(text) == text


def test_truncate_returns_unchanged_when_single_block() -> None:
    text = """Here is my code.

```repl
x = 42
```"""
    assert truncate_after_first_block(text) == text


def test_repl_executes_code_and_captures_output() -> None:
    repl = ReplEnvironment()
    result = repl.execute("x = 2 + 2\nprint(x)")
    assert "4" in result.stdout
    assert result.error is None


def test_repl_persists_state_across_executions() -> None:
    repl = ReplEnvironment()
    repl.execute("counter = 0")
    repl.execute("counter += 1")
    result = repl.execute("print(counter)")
    assert "1" in result.stdout


def test_repl_captures_runtime_errors() -> None:
    repl = ReplEnvironment()
    result = repl.execute("1 / 0")
    assert result.error is not None
    assert "ZeroDivisionError" in result.error


def test_repl_truncates_long_output() -> None:
    repl = ReplEnvironment(max_output_chars=100)
    result = repl.execute("print('x' * 500)")
    assert len(result.stdout) <= 120  # allows for truncation message
    assert "truncated" in result.stdout.lower() or len(result.stdout) <= 100


def test_repl_tracks_variable_names() -> None:
    repl = ReplEnvironment()
    repl.execute("alpha = 1")
    repl.execute("beta = 'hello'")
    variables = repl.list_variables()
    assert "alpha" in variables
    assert "beta" in variables


def test_repl_injects_initial_variables() -> None:
    repl = ReplEnvironment()
    repl.inject_variable("greeting", "'hello world'")
    result = repl.execute("print(greeting)")
    assert "hello world" in result.stdout


def test_repl_get_variable_returns_value() -> None:
    repl = ReplEnvironment()
    repl.execute("answer = 42")
    assert repl.get_variable("answer") == 42


def test_repl_get_variable_returns_none_for_missing() -> None:
    repl = ReplEnvironment()
    assert repl.get_variable("nonexistent") is None


def test_repl_inject_object_makes_callable_available() -> None:
    repl = ReplEnvironment()
    repl.inject_object("add", lambda a, b: a + b)
    result = repl.execute("answer = add(3, 4)\nprint(answer)")
    assert "7" in result.stdout
    assert "add" in repl.list_variables()


def test_repl_snapshot_captures_values() -> None:
    repl = ReplEnvironment()
    repl.execute("x = 42")
    repl.execute("name = 'voltage'")
    repl.execute("data = {'a': 1, 'b': 2}")
    repl.execute("values = [1.1, 2.2, 3.3]")
    snap = repl.snapshot_variables()
    assert snap["x"] == 42
    assert snap["name"] == "voltage"
    assert snap["data"] == {"a": 1, "b": 2}
    assert snap["values"] == [1.1, 2.2, 3.3]


def test_repl_snapshot_handles_non_serializable() -> None:
    repl = ReplEnvironment()
    repl.execute("import math")
    repl.inject_object("fn", lambda: None)
    snap = repl.snapshot_variables()
    # Non-serialisable objects get repr()
    assert isinstance(snap["fn"], str)
    assert "lambda" in snap["fn"] or "function" in snap["fn"]


def test_repl_snapshot_tracks_across_iterations() -> None:
    repl = ReplEnvironment()
    repl.execute("total = 0")
    snap1 = repl.snapshot_variables()
    assert snap1["total"] == 0

    repl.execute("total += 10")
    snap2 = repl.snapshot_variables()
    assert snap2["total"] == 10

    repl.execute("total += 5")
    snap3 = repl.snapshot_variables()
    assert snap3["total"] == 15


# ---- Protected variables ----


def test_protected_var_excluded_from_list_variables() -> None:
    repl = ReplEnvironment()
    repl.inject_object("NOTE", lambda k, v: None, protected=True)
    repl.execute("x = 1")
    variables = repl.list_variables()
    assert "x" in variables
    assert "NOTE" not in variables


def test_protected_var_excluded_from_snapshot() -> None:
    repl = ReplEnvironment()
    repl.inject_object("RECALL", lambda k=None: None, protected=True)
    repl.execute("y = 42")
    snap = repl.snapshot_variables()
    assert "y" in snap
    assert "RECALL" not in snap


def test_protected_kwarg_defaults_to_false() -> None:
    """Backward compat: inject_object without protected= still shows in list."""
    repl = ReplEnvironment()
    repl.inject_object("helper", lambda: "hi")
    assert "helper" in repl.list_variables()


def test_restore_protected_restores_overwritten_vars() -> None:
    repl = ReplEnvironment()

    def original_fn() -> str:
        return "original"

    repl.inject_object("NOTE", original_fn, protected=True)
    scaffolds = {"NOTE": original_fn}

    # Agent overwrites NOTE
    repl.execute("NOTE = 'oops'")
    assert repl.get_variable("NOTE") == "oops"

    # Restore
    repl.restore_protected(scaffolds)
    assert repl.get_variable("NOTE") is original_fn


# ---- FINAL_VAR mechanism ----


def test_final_value_defaults_to_none() -> None:
    repl = ReplEnvironment()
    assert repl.final_value is None
    assert repl.final_called is False


def test_final_value_set_by_code() -> None:
    repl = ReplEnvironment()

    def final_var(value):
        repl.final_value = value
        repl.final_called = True
        return f"FINAL_VAR set: {type(value).__name__}"

    repl.inject_object("FINAL_VAR", final_var, protected=True)
    # exec() doesn't capture return values — agent must print() if they want output
    result = repl.execute('result = FINAL_VAR({"answer": 42})\nprint(result)')
    assert repl.final_called is True
    assert repl.final_value == {"answer": 42}
    assert "FINAL_VAR set" in result.stdout


def test_final_value_not_in_snapshot() -> None:
    repl = ReplEnvironment()
    repl.inject_object("FINAL_VAR", lambda v: None, protected=True)
    repl.execute("x = 1")
    snap = repl.snapshot_variables()
    assert "FINAL_VAR" not in snap
    assert "x" in snap
