# ABOUTME: Tests for the lambda-rlm adapter factory function.
# ABOUTME: Validates config loading, source document discovery, and adapter wiring.

from pathlib import Path
from unittest.mock import MagicMock

from aec_bench.adapters.lambda_rlm.initialiser import (
    build_lambda_rlm_adapter,
    discover_source_docs,
)

_LAMBDA_RLM_TOML = """
[template]
tier = "dependency_tree"
definition = "report_template.toml"

[planner]
context_window_chars = 100_000

[guardrails]
token_budget = 750_000
"""

_TEMPLATE_TOML = """
[[sections]]
id = "background"
title = "Background"
depends_on = []
generation_mode = "transform"
writing_guidance = ["Carry language verbatim"]
input_mapping = ["brief:Description"]

[[sections.fields]]
name = "context"
dtype = "str"
"""


def test_discover_source_docs_from_workspace(tmp_path: Path):
    docs_dir = tmp_path / "documents"
    docs_dir.mkdir()
    (docs_dir / "brief.md").write_text("Project brief content.")
    refs_dir = docs_dir / "references"
    refs_dir.mkdir()
    (refs_dir / "proposal.md").write_text("Reference proposal.")
    supp_dir = docs_dir / "supplementary"
    supp_dir.mkdir()
    (supp_dir / "context.md").write_text("Extra context.")

    docs = discover_source_docs(str(tmp_path))
    assert "brief" in docs
    assert "Project brief content." in docs["brief"]
    assert "references/proposal" in docs
    assert "supplementary/context" in docs


def test_build_lambda_rlm_adapter(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "lambda-rlm.toml").write_text(_LAMBDA_RLM_TOML)
    (workspace / "report_template.toml").write_text(_TEMPLATE_TOML)
    docs_dir = workspace / "documents"
    docs_dir.mkdir()
    (docs_dir / "brief.md").write_text("Brief content.")

    client = MagicMock()
    adapter = build_lambda_rlm_adapter(
        config_path=workspace / "lambda-rlm.toml",
        client=client,
        adapter_name="lambda-rlm",
        model_name="test-model",
        workspace=str(workspace),
    )

    assert adapter.adapter_name() == "lambda-rlm"
    assert adapter.resolved_model() == "test-model"


def test_build_adapter_without_config_uses_defaults(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "report_template.toml").write_text(_TEMPLATE_TOML)
    docs_dir = workspace / "documents"
    docs_dir.mkdir()
    (docs_dir / "brief.md").write_text("Brief.")

    client = MagicMock()
    adapter = build_lambda_rlm_adapter(
        config_path=None,
        template_path=workspace / "report_template.toml",
        client=client,
        adapter_name="lambda-rlm",
        model_name="test-model",
        workspace=str(workspace),
    )

    assert adapter.adapter_name() == "lambda-rlm"


# ─── boilerplate loading ───────────────────────────────────────────────────────


_BOILERPLATE_TOML = """
[the_site.condition]
preamble = "The Site remains operational throughout the Works."

[the_site.access]
access_route = "Access via the {{access_point}}."
"""


def test_discover_boilerplate_fragments_loads_from_reference_data(tmp_path: Path):
    from aec_bench.adapters.lambda_rlm.initialiser import discover_boilerplate_fragments

    template_path = tmp_path / "report_template.toml"
    template_path.write_text(_TEMPLATE_TOML)
    ref_dir = tmp_path / "reference_data"
    ref_dir.mkdir()
    (ref_dir / "sow_boilerplate.toml").write_text(_BOILERPLATE_TOML)

    fragments = discover_boilerplate_fragments(template_path)
    assert fragments["the_site"]["condition"]["preamble"].startswith("The Site remains")
    assert "{{access_point}}" in fragments["the_site"]["access"]["access_route"]


def test_discover_boilerplate_fragments_returns_empty_when_file_missing(tmp_path: Path):
    from aec_bench.adapters.lambda_rlm.initialiser import discover_boilerplate_fragments

    template_path = tmp_path / "report_template.toml"
    template_path.write_text(_TEMPLATE_TOML)
    # No reference_data/ directory at all.
    assert discover_boilerplate_fragments(template_path) == {}


def test_build_adapter_passes_boilerplate_fragments_when_present(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "report_template.toml").write_text(_TEMPLATE_TOML)
    ref_dir = workspace / "reference_data"
    ref_dir.mkdir()
    (ref_dir / "sow_boilerplate.toml").write_text(_BOILERPLATE_TOML)
    docs_dir = workspace / "documents"
    docs_dir.mkdir()
    (docs_dir / "brief.md").write_text("Brief.")

    client = MagicMock()
    adapter = build_lambda_rlm_adapter(
        config_path=None,
        template_path=workspace / "report_template.toml",
        client=client,
        adapter_name="lambda-rlm",
        model_name="test-model",
        workspace=str(workspace),
    )

    assert adapter.boilerplate_fragments["the_site"]["condition"]["preamble"].startswith("The Site remains")


def test_build_adapter_boilerplate_defaults_to_empty_when_absent(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "report_template.toml").write_text(_TEMPLATE_TOML)
    docs_dir = workspace / "documents"
    docs_dir.mkdir()
    (docs_dir / "brief.md").write_text("Brief.")

    client = MagicMock()
    adapter = build_lambda_rlm_adapter(
        config_path=None,
        template_path=workspace / "report_template.toml",
        client=client,
        adapter_name="lambda-rlm",
        model_name="test-model",
        workspace=str(workspace),
    )

    assert adapter.boilerplate_fragments == {}


def test_build_adapter_skips_sandbox_when_disabled(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "lambda-rlm.toml").write_text(_LAMBDA_RLM_TOML)
    (workspace / "report_template.toml").write_text(_TEMPLATE_TOML)
    docs_dir = workspace / "documents"
    docs_dir.mkdir()
    (docs_dir / "brief.md").write_text("# T\n\n## Scope\nbody")
    client = MagicMock()
    adapter = build_lambda_rlm_adapter(
        config_path=workspace / "lambda-rlm.toml",
        client=client,
        adapter_name="lambda-rlm",
        model_name="test-model",
        workspace=str(workspace),
    )
    assert adapter._sandbox is None  # default config has sandbox.enabled=false


def test_build_adapter_builds_sandbox_when_enabled(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    config_text = _LAMBDA_RLM_TOML + "\n[sandbox]\nenabled = true\n"
    (workspace / "lambda-rlm.toml").write_text(config_text)
    (workspace / "report_template.toml").write_text(_TEMPLATE_TOML)
    docs_dir = workspace / "documents"
    docs_dir.mkdir()
    (docs_dir / "brief.md").write_text("# T\n\n## Scope\nbody")
    client = MagicMock()
    adapter = build_lambda_rlm_adapter(
        config_path=workspace / "lambda-rlm.toml",
        client=client,
        adapter_name="lambda-rlm",
        model_name="test-model",
        workspace=str(workspace),
    )
    assert adapter._sandbox is not None
    assert "brief" in adapter._sandbox.labels()
