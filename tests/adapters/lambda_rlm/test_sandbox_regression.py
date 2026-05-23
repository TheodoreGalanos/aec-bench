# ABOUTME: Regression test for the sandbox-grounding back-compat invariant.
# ABOUTME: Same workspace + replay client, sandbox.enabled=true vs false → byte-identical output.

from pathlib import Path

import pytest

from aec_bench.adapters.base import AdapterRequest
from aec_bench.adapters.lambda_rlm.initialiser import build_lambda_rlm_adapter
from aec_bench.adapters.rlm.client import ReplayRlmClient, RlmCompletionResponse

# ─────────────────────────────────────────────────────────────────────────────
# Template and config TOML strings
# ─────────────────────────────────────────────────────────────────────────────

# One compose section with two blocks:
#   1. A verbatim block (no LLM call)
#   2. A fill block with one slot (one LLM call per section)
_TEMPLATE_TOML = """\
[meta]
title = "Regression Test Report"

[boilerplate]
path = "boilerplate.toml"

[[sections]]
id = "intro"
title = "Introduction"
generation_mode = "compose"

[sections.fields]
content = "str"

[[sections.blocks]]
type = "verbatim"
ref = "intro.preamble"

[[sections.blocks]]
type = "fill"
ref = "intro.project_line"
sources = ["brief"]
"""

_BOILERPLATE_TOML = """\
[intro]
preamble = "This Statement of Work covers the scope below."

[intro.project_line]
text = "ExampleCo will deliver {{deliverable}} for the project."
"""

_LAMBDA_RLM_TOML_DISABLED = """\
[template]
definition = "report_template.toml"
[compose]
mode = "agentic"
"""

_LAMBDA_RLM_TOML_ENABLED = """\
[template]
definition = "report_template.toml"
[compose]
mode = "agentic"
[sandbox]
enabled = true
tool_use = false
"""


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _make_workspace(tmp_path: Path, lambda_rlm_toml: str) -> Path:
    """Scaffold a minimal workspace with report_template.toml, boilerplate.toml,
    and a source document in documents/."""
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True)
    (workspace / "lambda-rlm.toml").write_text(lambda_rlm_toml)
    (workspace / "report_template.toml").write_text(_TEMPLATE_TOML)
    (workspace / "boilerplate.toml").write_text(_BOILERPLATE_TOML)
    docs_dir = workspace / "documents"
    docs_dir.mkdir()
    (docs_dir / "brief.md").write_text("# Title\n\n## Scope\nDeliver an options assessment for the WWTP upgrade.")
    return workspace


def _replay_responses() -> list[RlmCompletionResponse]:
    """Canned LLM responses for one compose section (one fill block, one LLM call)."""
    return [
        RlmCompletionResponse(
            output_text='{"deliverable": "an options assessment"}',
            input_tokens=20,
            output_tokens=8,
        ),
    ]


def _run_adapter(workspace: Path, config_toml: str) -> str:
    """Build, execute the adapter and return the output.md text."""
    client = ReplayRlmClient(_replay_responses())
    adapter = build_lambda_rlm_adapter(
        config_path=workspace / "lambda-rlm.toml",
        client=client,
        adapter_name="lambda-rlm-test",
        model_name="test-model",
        workspace=str(workspace),
    )
    request = AdapterRequest(instruction="Test run")
    adapter.execute(request)
    return (workspace / "output.md").read_text(encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "sandbox_enabled,config_toml",
    [
        (False, _LAMBDA_RLM_TOML_DISABLED),
        (True, _LAMBDA_RLM_TOML_ENABLED),
    ],
    ids=["sandbox_disabled", "sandbox_enabled"],
)
def test_output_contains_expected_text(tmp_path: Path, sandbox_enabled: bool, config_toml: str) -> None:
    """Both sandbox modes produce output containing the verbatim preamble and
    the LLM-filled slot value."""
    workspace = _make_workspace(tmp_path, config_toml)
    text = _run_adapter(workspace, config_toml)

    assert "This Statement of Work covers the scope below." in text, (
        f"Verbatim preamble missing from output (sandbox_enabled={sandbox_enabled})"
    )
    assert "an options assessment" in text, f"Filled slot value missing from output (sandbox_enabled={sandbox_enabled})"


def test_output_text_identical_across_sandbox_toggle(tmp_path: Path) -> None:
    """Same workspace content + same replay responses → byte-identical output.md
    regardless of the sandbox.enabled flag.

    This is the Q12 back-compat invariant: enabling the sandbox must not change
    the assembled document text when inputs and LLM responses are held constant.
    """
    workspace_off = _make_workspace(tmp_path / "off", _LAMBDA_RLM_TOML_DISABLED)
    text_off = _run_adapter(workspace_off, _LAMBDA_RLM_TOML_DISABLED)

    workspace_on = _make_workspace(tmp_path / "on", _LAMBDA_RLM_TOML_ENABLED)
    text_on = _run_adapter(workspace_on, _LAMBDA_RLM_TOML_ENABLED)

    assert text_off == text_on, (
        "Sandbox toggle changed output.md text — sandbox path is introducing drift.\n"
        f"\n--- sandbox=false ---\n{text_off}\n"
        f"\n--- sandbox=true  ---\n{text_on}"
    )
