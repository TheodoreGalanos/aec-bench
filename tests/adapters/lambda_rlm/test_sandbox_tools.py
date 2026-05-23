# ABOUTME: Unit tests for the sandbox tool-use harness.
# ABOUTME: Verifies off-by-default, four tool dispatch, and cap enforcement.

import pytest

from aec_bench.adapters.lambda_rlm.config import ToolUseCapsConfig
from aec_bench.adapters.lambda_rlm.sandbox import DocumentSandbox
from aec_bench.adapters.lambda_rlm.sandbox_tools import (
    SandboxToolHarness,
    ToolUseCapExceeded,
)


def _make_sandbox() -> DocumentSandbox:
    return DocumentSandbox.from_documents(
        {
            "brief.md": (
                "# T\n\n## Scope\nExampleCo will deliver options assessment.\n\n## Schedule\nPhase 1 by 2026-06-30."
            ),
        },
        extractor_overrides={},
    )


def _caps(per_block: int = 5, total: int = 30) -> ToolUseCapsConfig:
    return ToolUseCapsConfig(max_fetches_per_block=per_block, max_total_fetches=total)


def test_harness_off_by_default_exposes_no_tools():
    h = SandboxToolHarness(sandbox=_make_sandbox(), enabled=False, caps=_caps())
    assert h.tools_for_prompt() == ()


def test_harness_on_lists_four_tools():
    h = SandboxToolHarness(sandbox=_make_sandbox(), enabled=True, caps=_caps())
    names = [t["name"] for t in h.tools_for_prompt()]
    assert names == ["list_labels", "list_anchors", "get_slice", "search"]


def test_harness_invoke_when_disabled_raises():
    h = SandboxToolHarness(sandbox=_make_sandbox(), enabled=False, caps=_caps())
    with pytest.raises(RuntimeError, match="disabled"):
        h.invoke("list_labels", {})


def test_harness_list_labels_returns_known_labels():
    h = SandboxToolHarness(sandbox=_make_sandbox(), enabled=True, caps=_caps())
    assert h.invoke("list_labels", {}) == ["brief.md"]


def test_harness_list_anchors_returns_canonical_ids():
    h = SandboxToolHarness(sandbox=_make_sandbox(), enabled=True, caps=_caps())
    anchors = h.invoke("list_anchors", {"label": "brief.md"})
    assert "#scope" in anchors
    assert "#schedule" in anchors
    assert ":p1" in anchors  # universal secondary


def test_harness_get_slice_returns_text_and_records_fetch():
    h = SandboxToolHarness(sandbox=_make_sandbox(), enabled=True, caps=_caps())
    result = h.invoke("get_slice", {"label": "brief.md", "anchor": "#scope"})
    assert "ExampleCo" in result["text"]
    assert result["label"] == "brief.md"
    assert result["anchor"] == "#scope"
    assert h.fetched_anchors() == ("brief.md#scope",)


def test_harness_enforces_per_block_cap():
    h = SandboxToolHarness(
        sandbox=_make_sandbox(),
        enabled=True,
        caps=_caps(per_block=2, total=10),
    )
    h.invoke("get_slice", {"label": "brief.md", "anchor": "#scope"})
    h.invoke("get_slice", {"label": "brief.md", "anchor": ":p1"})
    with pytest.raises(ToolUseCapExceeded, match="per_block"):
        h.invoke("get_slice", {"label": "brief.md", "anchor": ":p2"})


def test_harness_reset_block_counter_allows_more_fetches():
    h = SandboxToolHarness(
        sandbox=_make_sandbox(),
        enabled=True,
        caps=_caps(per_block=2, total=10),
    )
    h.invoke("get_slice", {"label": "brief.md", "anchor": "#scope"})
    h.invoke("get_slice", {"label": "brief.md", "anchor": ":p1"})
    h.reset_block_counter()
    # Should not raise — per-block counter is reset
    h.invoke("get_slice", {"label": "brief.md", "anchor": "#schedule"})
    assert len(h.fetched_anchors()) == 3


def test_harness_enforces_total_cap_across_blocks():
    h = SandboxToolHarness(
        sandbox=_make_sandbox(),
        enabled=True,
        caps=_caps(per_block=10, total=2),
    )
    h.invoke("get_slice", {"label": "brief.md", "anchor": "#scope"})
    h.reset_block_counter()
    h.invoke("get_slice", {"label": "brief.md", "anchor": ":p1"})
    h.reset_block_counter()
    with pytest.raises(ToolUseCapExceeded, match="total"):
        h.invoke("get_slice", {"label": "brief.md", "anchor": "#schedule"})


def test_harness_search_returns_anchor_snippet_pairs():
    h = SandboxToolHarness(sandbox=_make_sandbox(), enabled=True, caps=_caps())
    hits = h.invoke("search", {"query": "options"})
    assert isinstance(hits, list)
    assert all("anchor" in hit and "snippet" in hit and "label" in hit for hit in hits)
    assert any("options" in hit["snippet"].lower() for hit in hits)


def test_harness_search_case_insensitive():
    h = SandboxToolHarness(sandbox=_make_sandbox(), enabled=True, caps=_caps())
    hits = h.invoke("search", {"query": "EXAMPLECO"})
    assert len(hits) >= 1


def test_harness_unknown_tool_raises():
    h = SandboxToolHarness(sandbox=_make_sandbox(), enabled=True, caps=_caps())
    with pytest.raises(ValueError, match="unknown tool"):
        h.invoke("nonsense", {})
