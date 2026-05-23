# ABOUTME: Tests for config-driven RLM adapter initialisation.
# ABOUTME: Verifies build_rlm_adapter correctly wires config, template, subcalls, hints, and dual-model support.

"""Tests for config-driven RLM adapter initialisation."""

from pathlib import Path
from unittest.mock import MagicMock

from aec_bench.adapters.rlm.adapter import RlmAdapter
from aec_bench.adapters.rlm.initialiser import build_rlm_adapter


def test_build_from_minimal_config(tmp_path: Path) -> None:
    rlm_toml = tmp_path / "rlm.toml"
    rlm_toml.write_text("""\
[template]
tier = "flat"

[guardrails]
token_budget = 50_000
max_iterations = 20
""")
    client = MagicMock()
    adapter = build_rlm_adapter(
        rlm_config_path=rlm_toml,
        client=client,
        adapter_name="test-rlm",
        model_name="test-model",
    )
    assert isinstance(adapter, RlmAdapter)
    assert adapter.adapter_name() == "test-rlm"
    assert adapter.resolved_model() == "test-model"


def test_build_with_template(tmp_path: Path) -> None:
    rlm_toml = tmp_path / "rlm.toml"
    rlm_toml.write_text("""\
[template]
tier = "dependency_tree"
definition = "report_template.toml"
""")

    template_toml = tmp_path / "report_template.toml"
    template_toml.write_text("""\
[meta]
name = "Test"

[[sections]]
id = "intro"
title = "Introduction"
fields = [{ name = "summary", dtype = "str", description = "Summary" }]
depends_on = []
""")

    client = MagicMock()
    adapter = build_rlm_adapter(
        rlm_config_path=rlm_toml,
        client=client,
        adapter_name="test-rlm",
        model_name="test-model",
    )
    assert isinstance(adapter, RlmAdapter)
    assert adapter._template is not None
    assert adapter._template.get_status().total_sections == 1


def test_build_with_subcalls(tmp_path: Path) -> None:
    rlm_toml = tmp_path / "rlm.toml"
    rlm_toml.write_text("""\
[template]
tier = "flat"

[subcalls.extract]
enabled = true

[subcalls.calculate]
enabled = false
""")

    client = MagicMock()
    adapter = build_rlm_adapter(
        rlm_config_path=rlm_toml,
        client=client,
        adapter_name="test-rlm",
        model_name="test-model",
    )
    assert "extract" in adapter._subcall_configs
    assert adapter._subcall_configs["extract"].enabled
    assert not adapter._subcall_configs["calculate"].enabled


def test_build_with_hints(tmp_path: Path) -> None:
    rlm_toml = tmp_path / "rlm.toml"
    rlm_toml.write_text("""\
[template]
tier = "flat"

[hints]
phases = ["Read the brief", "Write the report"]
""")

    client = MagicMock()
    adapter = build_rlm_adapter(
        rlm_config_path=rlm_toml,
        client=client,
        adapter_name="test-rlm",
        model_name="test-model",
    )
    assert adapter._hints == ["Read the brief", "Write the report"]


def test_build_with_dual_model(tmp_path: Path) -> None:
    rlm_toml = tmp_path / "rlm.toml"
    rlm_toml.write_text("""\
[template]
tier = "flat"
""")

    main_client = MagicMock()
    sub_client = MagicMock()
    adapter = build_rlm_adapter(
        rlm_config_path=rlm_toml,
        client=main_client,
        adapter_name="test-rlm",
        model_name="main-model",
        subcall_client=sub_client,
        subcall_model="sub-model",
    )
    assert adapter._subcall_model == "sub-model"


def test_build_with_workspace_loads_system_prompt(tmp_path: Path) -> None:
    rlm_toml = tmp_path / "rlm.toml"
    rlm_toml.write_text('[template]\ntier = "flat"\n')

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "system_prompt.md").write_text("You are a civil engineer.")

    client = MagicMock()
    adapter = build_rlm_adapter(
        rlm_config_path=rlm_toml,
        client=client,
        adapter_name="test-rlm",
        model_name="test-model",
        workspace_path=str(workspace),
    )
    assert "civil engineer" in adapter._external_system_prompt


def test_build_with_workspace_loads_notes(tmp_path: Path) -> None:
    rlm_toml = tmp_path / "rlm.toml"
    rlm_toml.write_text('[template]\ntier = "flat"\n')

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "notes.md").write_text("Focus on drainage design.")

    client = MagicMock()
    adapter = build_rlm_adapter(
        rlm_config_path=rlm_toml,
        client=client,
        adapter_name="test-rlm",
        model_name="test-model",
        workspace_path=str(workspace),
    )
    assert "drainage" in adapter._external_system_prompt


def test_build_with_workspace_sets_scratchpad_path(tmp_path: Path) -> None:
    rlm_toml = tmp_path / "rlm.toml"
    rlm_toml.write_text('[template]\ntier = "flat"\n')

    workspace = tmp_path / "workspace"
    workspace.mkdir()

    client = MagicMock()
    adapter = build_rlm_adapter(
        rlm_config_path=rlm_toml,
        client=client,
        adapter_name="test-rlm",
        model_name="test-model",
        workspace_path=str(workspace),
    )
    assert adapter._scratchpad_path is not None
    assert ".scratchpad.json" in adapter._scratchpad_path


def test_build_with_execution_config(tmp_path: Path) -> None:
    rlm_toml = tmp_path / "rlm.toml"
    rlm_toml.write_text("""\
[template]
tier = "flat"

[execution]
compaction_threshold_pct = 0.75
context_limit = 500_000
""")

    client = MagicMock()
    adapter = build_rlm_adapter(
        rlm_config_path=rlm_toml,
        client=client,
        adapter_name="test-rlm",
        model_name="test-model",
    )
    assert adapter._execution_config.compaction_threshold_pct == 0.75
    assert adapter._execution_config.context_limit == 500_000
