# ABOUTME: Integration tests for the grounding_report.json artefact emitted by LambdaRlmAdapter.
# ABOUTME: Validates the report is written (or not) based on sandbox and grounding config.

import json
from pathlib import Path

from aec_bench.adapters.base import AdapterRequest
from aec_bench.adapters.lambda_rlm.initialiser import build_lambda_rlm_adapter
from aec_bench.adapters.rlm.client import ReplayRlmClient, RlmCompletionResponse
from aec_bench.contracts.grounding_report import GroundingReport

# ─────────────────────────────────────────────────────────────────────────────
# Minimal compose-mode template: one section, verbatim + fill blocks.
# The fill block produces one LLM call; the verbatim block writes boilerplate.
# ─────────────────────────────────────────────────────────────────────────────

_TEMPLATE_TOML = """\
[meta]
title = "Grounding Test Report"

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

# ─────────────────────────────────────────────────────────────────────────────
# Config TOML variants
# ─────────────────────────────────────────────────────────────────────────────

_CONFIG_SANDBOX_ENABLED = """\
[template]
definition = "report_template.toml"
[compose]
mode = "agentic"
[sandbox]
enabled = true
tool_use = false
"""

_CONFIG_SANDBOX_DISABLED = """\
[template]
definition = "report_template.toml"
[compose]
mode = "agentic"
"""

_CONFIG_SANDBOX_ENABLED_GROUNDING_OFF = """\
[template]
definition = "report_template.toml"
[compose]
mode = "agentic"
[sandbox]
enabled = true
tool_use = false
[grounding]
check = "off"
"""

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _make_workspace(tmp_path: Path, config_toml: str) -> Path:
    """Scaffold a minimal compose-mode workspace."""
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True)
    (workspace / "lambda-rlm.toml").write_text(config_toml)
    (workspace / "report_template.toml").write_text(_TEMPLATE_TOML)
    (workspace / "boilerplate.toml").write_text(_BOILERPLATE_TOML)
    docs_dir = workspace / "documents"
    docs_dir.mkdir()
    (docs_dir / "brief.md").write_text("# Title\n\n## Scope\nDeliver an options assessment for the WWTP upgrade.")
    return workspace


def _replay_responses() -> list[RlmCompletionResponse]:
    """One canned LLM response for the single fill block."""
    return [
        RlmCompletionResponse(
            output_text='{"deliverable": "an options assessment"}',
            input_tokens=20,
            output_tokens=8,
        ),
    ]


def _run_adapter(workspace: Path) -> None:
    """Build and execute the adapter against the given workspace."""
    client = ReplayRlmClient(_replay_responses())
    adapter = build_lambda_rlm_adapter(
        config_path=workspace / "lambda-rlm.toml",
        client=client,
        adapter_name="lambda-rlm-test",
        model_name="test-model",
        workspace=str(workspace),
    )
    adapter.execute(AdapterRequest(instruction="Test run"))


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_adapter_emits_grounding_report_when_sandbox_enabled(tmp_path: Path) -> None:
    """End-to-end: sandbox enabled → grounding_report.json is written and parses cleanly."""
    workspace = _make_workspace(tmp_path, _CONFIG_SANDBOX_ENABLED)
    _run_adapter(workspace)

    report_path = workspace / "grounding_report.json"
    assert report_path.exists(), "grounding_report.json must be written when sandbox is enabled"

    raw = json.loads(report_path.read_text(encoding="utf-8"))
    report = GroundingReport.from_dict(raw)

    # The template has one compose section ("intro"); it must appear in the report.
    assert isinstance(report, GroundingReport)
    assert len(report.sections) >= 1
    section_ids = {s.section_id for s in report.sections}
    assert "intro" in section_ids, f"Expected 'intro' in section_ids, got {section_ids}"


def test_adapter_skips_grounding_report_when_sandbox_disabled(tmp_path: Path) -> None:
    """No sandbox → grounding_report.json must NOT be written."""
    workspace = _make_workspace(tmp_path, _CONFIG_SANDBOX_DISABLED)
    _run_adapter(workspace)

    report_path = workspace / "grounding_report.json"
    assert not report_path.exists(), "grounding_report.json must not be written when sandbox is disabled"


def test_adapter_skips_grounding_report_when_check_off(tmp_path: Path) -> None:
    """sandbox enabled but grounding.check = 'off' → grounding_report.json must NOT be written."""
    workspace = _make_workspace(tmp_path, _CONFIG_SANDBOX_ENABLED_GROUNDING_OFF)
    _run_adapter(workspace)

    report_path = workspace / "grounding_report.json"
    assert not report_path.exists(), "grounding_report.json must not be written when grounding.check = 'off'"
