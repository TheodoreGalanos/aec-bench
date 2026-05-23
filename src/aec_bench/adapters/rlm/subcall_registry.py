# ABOUTME: Registry that builds REPL-callable wrappers for typed sub-calls.
# ABOUTME: Captures client and model as closures so the agent calls extract(text=...) directly.

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from aec_bench.adapters.rlm.client import RlmClient
from aec_bench.adapters.rlm.config import SubcallConfig
from aec_bench.adapters.rlm.subcall_log import SubcallLog
from aec_bench.adapters.rlm.subcalls import (
    default_calculate,
    default_extract,
    default_reason,
    default_retrieve,
    default_review,
    default_summarise,
    default_verify,
)


def build_subcall_functions(
    *,
    configs: dict[str, SubcallConfig],
    client: RlmClient,
    model: str,
    token_callback: Callable[[int, int], None] | None = None,
    subcall_log: SubcallLog | None = None,
    template: Any | None = None,
) -> dict[str, Callable[..., Any]]:
    """Build REPL-callable wrapper functions for enabled sub-calls.

    Each wrapper captures the client and model as a closure, so the
    agent can call e.g. extract(text=..., fields=...) without knowing
    about clients or models.

    If *token_callback* is provided, it is called with
    ``(input_tokens, output_tokens)`` after each sub-call completes.
    If *subcall_log* is provided, each invocation is auto-recorded.
    """
    builders: dict[str, Callable[[], Callable[..., Any]]] = {
        "extract": lambda: _wrap_extract(client, model, token_callback, subcall_log, template),
        "calculate": lambda: _wrap_calculate(client, model, token_callback, subcall_log),
        "retrieve": lambda: _wrap_retrieve(client, model, token_callback, subcall_log),
        "verify": lambda: _wrap_verify(client, model, token_callback, subcall_log),
        "summarise": lambda: _wrap_summarise(client, model, token_callback, subcall_log),
        "reason": lambda: _wrap_reason(client, model, token_callback, subcall_log),
        "review": lambda: _wrap_review(client, model, token_callback, subcall_log),
    }

    functions: dict[str, Callable[..., Any]] = {}
    for name, config in configs.items():
        if config.enabled and name in builders:
            functions[name] = builders[name]()

    return functions


def _report_and_log(
    result: Any,
    callback: Callable[[int, int], None] | None,
    log: SubcallLog | None,
    subcall_type: str,
    args_summary: str,
) -> None:
    """Report tokens and log the sub-call invocation."""
    inp = getattr(result, "input_tokens", 0)
    out = getattr(result, "output_tokens", 0)
    if callback is not None and inp and out:
        callback(inp, out)
    if log is not None:
        # Build a compact result summary for the log
        result_summary: Any = None
        if hasattr(result, "values"):
            result_summary = result.values
        elif hasattr(result, "summary"):
            result_summary = result.summary
        elif hasattr(result, "results"):
            result_summary = result.results
        elif hasattr(result, "conclusion"):
            result_summary = result.conclusion
        elif hasattr(result, "passed"):
            result_summary = {"passed": result.passed, "explanation": getattr(result, "explanation", "")}
        log.record(
            subcall_type=subcall_type,
            args_summary=args_summary,
            result_summary=result_summary,
            input_tokens=inp,
            output_tokens=out,
        )


def _wrap_extract(
    client: RlmClient,
    model: str,
    cb: Callable[[int, int], None] | None,
    log: SubcallLog | None = None,
    template: Any | None = None,
) -> Callable[..., Any]:
    def extract(
        text: str = "",
        fields: list[str] | None = None,
        *,
        context: str | None = None,
        section: str | None = None,
        **kw: Any,
    ) -> Any:
        """Extract structured data from text.

        Accepts both positional and keyword args:
          extract(doc, ["f1", "f2"])
          extract(text=doc, fields=["f1"], section="introduction")

        When *section* is provided and a template is loaded, uses
        goal-directed extraction with writing guidance and dependency
        context — matching lambda-RLM quality.
        """
        actual_text = kw.get("text", text) if not text else text
        actual_fields = kw.get("fields", fields) if fields is None else fields
        if not actual_text:
            from aec_bench.adapters.rlm.subcalls import ExtractResult

            return ExtractResult(values={}, error="extract() requires a text argument")
        if not actual_fields and not section:
            from aec_bench.adapters.rlm.subcalls import ExtractResult

            return ExtractResult(values={}, error="extract() requires fields or section argument")

        # Goal-directed extraction when section context is available
        section_context = None
        if section and template is not None:
            section_context = template.get_extraction_context(section)

        result = default_extract(
            text=actual_text,
            fields=actual_fields,
            client=client,
            model=model,
            context=context,
            section_context=section_context,
        )
        section_label = f" section={section}" if section else ""
        _report_and_log(result, cb, log, "extract", f"fields={actual_fields}{section_label}")
        return result

    return extract


def _wrap_calculate(
    client: RlmClient,
    model: str,
    cb: Callable[[int, int], None] | None,
    log: SubcallLog | None = None,
) -> Callable[..., Any]:
    def calculate(
        *,
        expression: str,
        parameters: dict[str, Any],
        tool: str | None = None,
    ) -> Any:
        result = default_calculate(
            expression=expression,
            parameters=parameters,
            client=client,
            model=model,
            tool=tool,
        )
        _report_and_log(result, cb, log, "calculate", f"expression={expression!r}")
        return result

    return calculate


def _wrap_retrieve(
    client: RlmClient,
    model: str,
    cb: Callable[[int, int], None] | None,
    log: SubcallLog | None = None,
) -> Callable[..., Any]:
    def retrieve(
        *,
        query: str,
        source: str | None = None,
        max_results: int = 5,
    ) -> Any:
        result = default_retrieve(
            query=query,
            client=client,
            model=model,
            source=source,
            max_results=max_results,
        )
        _report_and_log(result, cb, log, "retrieve", f"query={query!r}")
        return result

    return retrieve


def _wrap_verify(
    client: RlmClient,
    model: str,
    cb: Callable[[int, int], None] | None,
    log: SubcallLog | None = None,
) -> Callable[..., Any]:
    def verify(
        *,
        value: Any,
        criterion: str,
        standard: str | None = None,
    ) -> Any:
        result = default_verify(
            value=value,
            criterion=criterion,
            client=client,
            model=model,
            standard=standard,
        )
        _report_and_log(result, cb, log, "verify", f"criterion={criterion!r}")
        return result

    return verify


def _wrap_summarise(
    client: RlmClient,
    model: str,
    cb: Callable[[int, int], None] | None,
    log: SubcallLog | None = None,
) -> Callable[..., Any]:
    def summarise(
        *,
        content: str | list[str],
        focus: str | None = None,
        max_length: int = 500,
    ) -> Any:
        result = default_summarise(
            content=content,
            client=client,
            model=model,
            focus=focus,
            max_length=max_length,
        )
        _report_and_log(result, cb, log, "summarise", f"focus={focus!r}")
        return result

    return summarise


def _wrap_reason(
    client: RlmClient,
    model: str,
    cb: Callable[[int, int], None] | None,
    log: SubcallLog | None = None,
) -> Callable[..., Any]:
    def reason(
        *,
        question: str,
        context: str | None = None,
        options: list[str] | None = None,
    ) -> Any:
        result = default_reason(
            question=question,
            client=client,
            model=model,
            context=context,
            options=options,
        )
        _report_and_log(result, cb, log, "reason", f"question={question!r}")
        return result

    return reason


def _wrap_review(
    client: RlmClient,
    model: str,
    cb: Callable[[int, int], None] | None,
    log: SubcallLog | None = None,
) -> Callable[..., Any]:
    def review(
        *,
        section_content: str,
        writing_guidance: list[str],
        extracted_data: dict[str, Any] | None = None,
    ) -> Any:
        result = default_review(
            section_content=section_content,
            writing_guidance=writing_guidance,
            extracted_data=extracted_data,
            client=client,
            model=model,
        )
        _report_and_log(result, cb, log, "review", f"status={result.status}")
        return result

    return review
