# ABOUTME: Integration tests for constitutional inference in build_lambda_rlm_adapter.
# ABOUTME: Uses a stub RlmClient to verify the inference call fires and manifest flows into adapter.

import json
from pathlib import Path

from aec_bench.adapters.lambda_rlm.initialiser import build_lambda_rlm_adapter
from aec_bench.adapters.rlm.client import RlmCompletionResponse, RlmMessage


class _StubClient:
    """Stub RlmClient that returns a canned inference response."""

    def __init__(self, response_json: dict) -> None:
        self._response = response_json
        self.calls: list[tuple[str, list[RlmMessage]]] = []

    def generate(
        self,
        *,
        model: str,
        messages: list[RlmMessage],
        system_prompt: str | None,
        temperature: float | None = None,
    ) -> RlmCompletionResponse:
        self.calls.append((model, messages))
        return RlmCompletionResponse(
            output_text=json.dumps(self._response),
            input_tokens=100,
            output_tokens=50,
            cache_read_tokens=0,
            cache_write_tokens=0,
        )


def _write_minimal_task(tmp_path: Path) -> Path:
    """Create a minimal workspace with a lambda-rlm.toml pointing at a constitution TOML."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "documents").mkdir()
    (workspace / "documents" / "brief.md").write_text("Alpha bravo charlie.")

    template_path = workspace / "report_template.toml"
    template_path.write_text("""
[[sections]]
id = "introduction"
title = "Introduction"
writing_guidance = ["one line"]
generation_mode = "prose"
input_mapping = ["brief"]
""")

    constitution_path = workspace / "constitution.toml"
    constitution_path.write_text("""
version = "0.1.0"

[[principles]]
name = "source_fidelity"
description = "Never fabricate."
evaluation_criteria = "All claims trace to sources."

[[principles]]
name = "information_minimality"
description = "Filter noise from context."
evaluation_criteria = "Only surface what is needed."
""")

    config_path = workspace / "lambda-rlm.toml"
    config_path.write_text("""
[template]
tier = "dependency_tree"
definition = "report_template.toml"

[constitution]
path = "constitution.toml"
model = "au.anthropic.claude-haiku-4-5-20251001-v1:0"
""")

    return workspace


def test_build_adapter_fires_constitutional_inference(tmp_path):
    workspace = _write_minimal_task(tmp_path)
    stub = _StubClient(
        response_json={
            "source_fidelity": {
                "require_source_tracing": True,
                "tbd_placeholder": "[TBD]",
                "gap_framing": "exclude",
            },
            "information_minimality": {
                "default_threshold": 2000,
                "search_threshold": 15000,
                "preview_length": 300,
                "truncation_strategy": "metadata",
            },
        }
    )

    adapter = build_lambda_rlm_adapter(
        config_path=workspace / "lambda-rlm.toml",
        client=_StubClient({}),  # main client stub — won't be invoked in builder
        adapter_name="lambda-rlm",
        model_name="test-model",
        workspace=str(workspace),
        constitutional_client=stub,
        task_metadata={"difficulty": "hard", "tags": ["public-works"], "category": "report"},
    )

    # Inference should have fired exactly once
    assert len(stub.calls) == 1
    # Manifest should be stashed on the adapter
    assert adapter._constitution is not None
    assert adapter._constitution.source_fidelity is not None
    assert adapter._constitution.source_fidelity.gap_framing == "exclude"
    assert adapter._constitution.information_minimality is not None
    assert adapter._constitution.information_minimality.preview_length == 300


def test_build_adapter_without_constitution_does_nothing(tmp_path):
    """Without [constitution] block, no inference fires, no manifest set."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "documents").mkdir()
    (workspace / "documents" / "brief.md").write_text("Alpha.")

    template_path = workspace / "report_template.toml"
    template_path.write_text("""
[[sections]]
id = "introduction"
title = "Introduction"
writing_guidance = ["one line"]
generation_mode = "prose"
input_mapping = ["brief"]
""")

    config_path = workspace / "lambda-rlm.toml"
    config_path.write_text("""
[template]
tier = "dependency_tree"
definition = "report_template.toml"
""")

    adapter = build_lambda_rlm_adapter(
        config_path=config_path,
        client=_StubClient({}),
        adapter_name="lambda-rlm",
        model_name="test-model",
        workspace=str(workspace),
    )

    assert adapter._constitution is None


def test_build_adapter_with_constitution_but_no_client_uses_base_manifest(tmp_path):
    """When [constitution] is configured but no constitutional_client is provided,
    the base manifest is used without inference."""
    workspace = _write_minimal_task(tmp_path)

    adapter = build_lambda_rlm_adapter(
        config_path=workspace / "lambda-rlm.toml",
        client=_StubClient({}),
        adapter_name="lambda-rlm",
        model_name="test-model",
        workspace=str(workspace),
        # NOTE: no constitutional_client passed
    )

    # Constitution should be resolved (principles present from the TOML) but
    # params should be None because no inference fired.
    assert adapter._constitution is not None
    assert len(adapter._constitution.principles) == 2
    principle_names = {p.name for p in adapter._constitution.principles}
    assert principle_names == {"source_fidelity", "information_minimality"}
    assert adapter._constitution.source_fidelity is None
    assert adapter._constitution.information_minimality is None


def test_build_adapter_inline_param_tables_are_preserved(tmp_path):
    """When [constitution.inline] declares param tables, they must survive
    even without a constitutional_client (no inference fires, but user
    overrides are preserved verbatim)."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "documents").mkdir()
    (workspace / "documents" / "brief.md").write_text("Alpha.")

    (workspace / "report_template.toml").write_text("""
[[sections]]
id = "introduction"
title = "Introduction"
writing_guidance = ["one line"]
generation_mode = "prose"
input_mapping = ["brief"]
""")

    config_path = workspace / "lambda-rlm.toml"
    config_path.write_text("""
[template]
tier = "dependency_tree"
definition = "report_template.toml"

[constitution.inline]
version = "0.1.0"

[[constitution.inline.principles]]
name = "source_fidelity"
description = "Never fabricate."
evaluation_criteria = "All claims trace to sources."

[constitution.inline.source_fidelity]
gap_framing = "tbd"
tbd_placeholder = "[MISSING DATA]"

[constitution.inline.information_minimality]
preview_length = 150
""")

    adapter = build_lambda_rlm_adapter(
        config_path=config_path,
        client=_StubClient({}),
        adapter_name="lambda-rlm",
        model_name="test-model",
        workspace=str(workspace),
    )

    assert adapter._constitution is not None
    assert adapter._constitution.source_fidelity is not None
    assert adapter._constitution.source_fidelity.gap_framing == "tbd"
    assert adapter._constitution.source_fidelity.tbd_placeholder == "[MISSING DATA]"
    assert adapter._constitution.information_minimality is not None
    assert adapter._constitution.information_minimality.preview_length == 150
