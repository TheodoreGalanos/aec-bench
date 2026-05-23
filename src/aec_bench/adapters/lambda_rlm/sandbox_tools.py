# ABOUTME: Tool-use harness for the sandbox. Off by default; bounded by caps.
# ABOUTME: Four tools: list_labels, list_anchors, get_slice, search.

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aec_bench.adapters.lambda_rlm.config import ToolUseCapsConfig
from aec_bench.adapters.lambda_rlm.sandbox import DocumentSandbox


class ToolUseCapExceeded(RuntimeError):
    """Raised when sandbox tool-use exceeds per-block or total caps."""


@dataclass
class SandboxToolHarness:
    """Wraps a DocumentSandbox with bounded, Anthropic-style tool dispatch.

    When enabled=False, tools_for_prompt() returns () and invoke() raises.
    When enabled=True, four tools are exposed: list_labels, list_anchors,
    get_slice, and search. Caps are enforced per-block and over the lifetime.
    """

    sandbox: DocumentSandbox
    enabled: bool
    caps: ToolUseCapsConfig
    _fetches_this_block: int = field(default=0, init=False)
    _fetches_total: int = field(default=0, init=False)
    _fetched: list[str] = field(default_factory=list, init=False)

    def reset_block_counter(self) -> None:
        """Reset the per-block fetch counter; total counter is unchanged."""
        self._fetches_this_block = 0

    def fetched_anchors(self) -> tuple[str, ...]:
        """Return all anchor refs fetched via get_slice, in order."""
        return tuple(self._fetched)

    def tools_for_prompt(self) -> tuple[dict[str, Any], ...]:
        """Return Anthropic-style tool descriptors, or empty tuple if disabled."""
        if not self.enabled:
            return ()
        return (
            {
                "name": "list_labels",
                "description": "List all source-document labels in the sandbox.",
                "input_schema": {"type": "object", "properties": {}},
            },
            {
                "name": "list_anchors",
                "description": "List the canonical anchor IDs for one source document.",
                "input_schema": {
                    "type": "object",
                    "properties": {"label": {"type": "string"}},
                    "required": ["label"],
                },
            },
            {
                "name": "get_slice",
                "description": "Fetch the text of one anchored slice.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string"},
                        "anchor": {"type": "string"},
                    },
                    "required": ["label", "anchor"],
                },
            },
            {
                "name": "search",
                "description": ("Substring-search across slice texts; returns (label, anchor, snippet) hits."),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "labels": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["query"],
                },
            },
        )

    def invoke(self, name: str, args: dict[str, Any]) -> Any:
        """Dispatch a tool call by name. Raises if disabled or name is unknown."""
        if not self.enabled:
            msg = "tool-use is disabled"
            raise RuntimeError(msg)
        if name == "list_labels":
            return list(self.sandbox.labels())
        if name == "list_anchors":
            return [a.canonical for a in self.sandbox.anchors(args["label"])]
        if name == "get_slice":
            self._enforce_caps()
            sl = self.sandbox.slice(args["label"], args["anchor"])
            self._fetched.append(f"{sl.label}{sl.anchor}")
            return {"text": sl.text, "anchor": sl.anchor, "label": sl.label}
        if name == "search":
            return self._search(args["query"], args.get("labels"))
        msg = f"unknown tool: {name}"
        raise ValueError(msg)

    def _enforce_caps(self) -> None:
        """Check caps before counting a fetch; raises ToolUseCapExceeded if exceeded."""
        if self._fetches_this_block >= self.caps.max_fetches_per_block:
            msg = f"max_fetches_per_block ({self.caps.max_fetches_per_block}) exceeded"
            raise ToolUseCapExceeded(msg)
        if self._fetches_total >= self.caps.max_total_fetches:
            msg = f"max_total_fetches ({self.caps.max_total_fetches}) exceeded"
            raise ToolUseCapExceeded(msg)
        self._fetches_this_block += 1
        self._fetches_total += 1

    def _search(self, query: str, labels: list[str] | None) -> list[dict[str, str]]:
        """Search slice texts for query (case-insensitive); return snippet hits."""
        targets = labels or list(self.sandbox.labels())
        results: list[dict[str, str]] = []
        for label in targets:
            for anchor in self.sandbox.anchors(label):
                sl = self.sandbox.slice(label, anchor.canonical)
                idx = sl.text.lower().find(query.lower())
                if idx >= 0:
                    snippet_start = max(0, idx - 40)
                    snippet_end = min(len(sl.text), idx + len(query) + 40)
                    results.append(
                        {
                            "label": label,
                            "anchor": anchor.canonical,
                            "snippet": sl.text[snippet_start:snippet_end],
                        }
                    )
        return results
