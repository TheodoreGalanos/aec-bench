# ABOUTME: Template-aware parallel section generation using the dependency graph.
# ABOUTME: Identifies unlocked sections, generates content concurrently, fills sequentially.

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from aec_bench.adapters.rlm.parallel import ParallelError, parallel
from aec_bench.adapters.rlm.template import ReportTemplate

# Type alias for the generator callable the agent provides.
# Signature: (section_id, dependency_context, writing_guidance) -> content_dict
SectionGenerator = Callable[[str, dict[str, Any], list[str]], dict[str, Any]]


def fill_parallel(
    *,
    template: ReportTemplate,
    generator: SectionGenerator,
    section_ids: list[str] | None = None,
    max_workers: int = 4,
) -> list[Any]:
    """Fill template sections in parallel using a generator function.

    Identifies which sections are unlocked (all dependencies met),
    runs the generator concurrently for each, then fills sections
    sequentially with the results.

    The *generator* callable receives ``(section_id, context, guidance)``
    where *context* is the filled data from dependency sections and
    *guidance* is the expert decomposition hints.  It should return a
    dict of field values to fill the section with.

    If *section_ids* is provided, only those sections are considered
    (still filtered to only unlocked ones).

    Usage from REPL::

        def gen(section_id, context, guidance):
            prompt = f"Write {section_id}. Guidance: {guidance}. Data: {context}"
            return {"content": llm_query(prompt)}

        fill_parallel(template=report, generator=gen)

    Returns a list of fill results (or ``ParallelError`` for failures).
    """
    status = template.get_status()
    unlocked = set(status.unlocked)

    if section_ids is not None:
        targets = [sid for sid in section_ids if sid in unlocked]
    else:
        targets = list(unlocked)

    if not targets:
        return []

    # Build closures that capture each section's context and guidance.
    # These run concurrently — only reading from the template, not writing.
    def _make_generator(sid: str) -> Callable[[], dict[str, Any]]:
        context = template.get_section_context(sid)
        guidance = template.get_writing_guidance(sid)
        return lambda: generator(sid, context, guidance)

    callables = [_make_generator(sid) for sid in targets]

    # Generate content in parallel
    generated = parallel(callables, max_workers=max_workers)

    # Fill sections sequentially (safe — mutates template state)
    results: list[Any] = []
    for sid, content in zip(targets, generated, strict=False):
        if isinstance(content, ParallelError):
            results.append(content)
        else:
            result = template.fill_section(sid, content)
            results.append(result)

    return results
