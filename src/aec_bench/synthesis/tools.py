# ABOUTME: Pure tool implementations for the synthesis tool-loop driver.
# ABOUTME: Each tool is deterministic over SynthesisInput, no LLM calls or side effects.

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from aec_bench.contracts.synthesis import SynthesisInput

_SNIPPET_WINDOW_CHARS = 240


def get_candidate(
    input: SynthesisInput,
    i: int | None = None,
) -> list[dict[str, Any]]:
    """Return all K candidates or a single candidate by index.

    Matches AggAgent's ``get_solution`` semantics: coarse-read of the K drafts
    the synthesiser is composing across.
    """
    if i is None:
        return [{"candidate_id": c.candidate_id, "content": c.content} for c in input.candidates]
    if i < 0 or i >= len(input.candidates):
        raise IndexError(
            f"candidate index {i} out of range (K={len(input.candidates)})",
        )
    c = input.candidates[i]
    return [{"candidate_id": c.candidate_id, "content": c.content}]


def get_source(input: SynthesisInput, source_label: str) -> str:
    """Return the extracted content for a given source label."""
    if source_label not in input.references:
        raise KeyError(
            f"source_label {source_label!r} not found. Available: {sorted(input.references)}",
        )
    return input.references[source_label]


def _literal_match_snippets(
    text: str,
    query: str,
    k: int,
    anchor: str,
) -> list[dict[str, Any]]:
    """Return up to k snippet dicts for literal (case-insensitive) matches."""
    if not query or not text:
        return []
    matches: list[dict[str, Any]] = []
    query_lc = query.lower()
    text_lc = text.lower()
    start = 0
    while True:
        hit = text_lc.find(query_lc, start)
        if hit < 0 or len(matches) >= k:
            break
        window_start = max(0, hit - _SNIPPET_WINDOW_CHARS // 2)
        window_end = min(len(text), hit + len(query) + _SNIPPET_WINDOW_CHARS // 2)
        snippet = text[window_start:window_end].strip()
        matches.append({anchor: _anchor_value(anchor, text), "snippet": snippet})
        start = hit + max(len(query_lc), 1)
    return matches


def _anchor_value(anchor: str, text: str) -> str:  # noqa: ARG001
    # placeholder; real value is injected at call sites.
    return ""


def search_source(
    input: SynthesisInput,
    source_label: str | None,
    query: str,
    k: int = 5,
) -> list[dict[str, Any]]:
    """Search extracted data for a query. Scope to one source if label given."""
    if not query:
        return []
    if source_label is not None:
        labels: Sequence[str] = (source_label,)
    else:
        labels = tuple(input.references.keys())
    out: list[dict[str, Any]] = []
    for label in labels:
        if label not in input.references:
            continue
        text = input.references[label]
        for snip in _literal_match_snippets(text, query, k - len(out), "source_label"):
            out.append({"source_label": label, "snippet": snip["snippet"]})
            if len(out) >= k:
                return out
    return out


def search_across_candidates(
    input: SynthesisInput,
    query: str,
    k: int = 5,
) -> list[dict[str, Any]]:
    """Return up to k candidates ranked by literal match count for ``query``.

    Scoring is literal (case-insensitive) occurrence count per candidate.
    Not ROUGE-L — but the signal that matters here is "which candidates
    mention X", and literal counting is both fast and deterministic. Upgrade
    to n-gram overlap or embeddings if selection quality proves weak.
    """
    if not query:
        return []
    query_lc = query.lower()
    scored: list[tuple[int, str, str]] = []  # (score, candidate_id, snippet)
    for c in input.candidates:
        content_lc = c.content.lower()
        count = content_lc.count(query_lc)
        if count == 0:
            continue
        # First-match snippet as evidence.
        idx = content_lc.find(query_lc)
        start = max(0, idx - _SNIPPET_WINDOW_CHARS // 2)
        end = min(len(c.content), idx + len(query) + _SNIPPET_WINDOW_CHARS // 2)
        snippet = c.content[start:end].strip()
        scored.append((count, c.candidate_id, snippet))
    scored.sort(key=lambda t: t[0], reverse=True)
    return [{"candidate_id": cid, "score": float(score), "snippet": snippet} for score, cid, snippet in scored[:k]]


def get_criteria_bundle(input: SynthesisInput) -> dict[str, Any]:
    """Return the neutral criteria contract as a serialisable dict."""
    crit = input.criteria
    return {
        "section_title": crit.section_title,
        "summary": crit.summary,
        "writing_rules": list(crit.writing_rules),
        "rubric_criteria": [{"category": cat, "text": text} for cat, text in crit.rubric_criteria],
        "expert_personas": list(crit.expert_personas),
    }


__all__ = [
    "get_candidate",
    "get_criteria_bundle",
    "get_source",
    "search_across_candidates",
    "search_source",
]
