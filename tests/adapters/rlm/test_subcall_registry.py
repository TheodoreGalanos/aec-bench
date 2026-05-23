# ABOUTME: Tests for sub-call registry and REPL injection.
# ABOUTME: Verifies that build_subcall_functions creates correct closures and injects into REPL.

"""Tests for sub-call registry and REPL injection."""

from aec_bench.adapters.rlm.client import ReplayRlmClient, RlmCompletionResponse
from aec_bench.adapters.rlm.config import SubcallConfig
from aec_bench.adapters.rlm.engine import ReplEnvironment
from aec_bench.adapters.rlm.subcall_registry import build_subcall_functions


def test_build_creates_extract_function() -> None:
    client = ReplayRlmClient(
        responses=[
            RlmCompletionResponse(
                output_text='```json\n{"speed": 45}\n```',
                input_tokens=100,
                output_tokens=30,
            ),
        ]
    )
    configs = {"extract": SubcallConfig(name="extract", enabled=True)}
    functions = build_subcall_functions(
        configs=configs,
        client=client,
        model="test",
    )
    assert "extract" in functions
    result = functions["extract"](text="Wind speed is 45", fields=["speed"])
    assert result.values["speed"] == 45


def test_disabled_subcall_not_included() -> None:
    client = ReplayRlmClient(responses=[])
    configs = {
        "extract": SubcallConfig(name="extract", enabled=True),
        "calculate": SubcallConfig(name="calculate", enabled=False),
    }
    functions = build_subcall_functions(
        configs=configs,
        client=client,
        model="test",
    )
    assert "extract" in functions
    assert "calculate" not in functions


def test_inject_into_repl() -> None:
    client = ReplayRlmClient(
        responses=[
            RlmCompletionResponse(
                output_text='```json\n{"val": 42}\n```',
                input_tokens=50,
                output_tokens=20,
            ),
        ]
    )
    configs = {"extract": SubcallConfig(name="extract", enabled=True)}
    functions = build_subcall_functions(
        configs=configs,
        client=client,
        model="test",
    )

    repl = ReplEnvironment()
    for name, fn in functions.items():
        repl.inject_object(name, fn)

    result = repl.execute('result = extract(text="speed is 42", fields=["val"])')
    assert result.error is None
    val = repl.get_variable("result")
    assert val.values["val"] == 42
