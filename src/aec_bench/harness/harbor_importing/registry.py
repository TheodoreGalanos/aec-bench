# ABOUTME: Selects allowlisted Harbor import evidence extensions by declared execution kind.
# ABOUTME: Lazily imports policy modules so ordinary Harbor imports remain proposal-independent.

from __future__ import annotations

from importlib import import_module
from types import MappingProxyType
from typing import cast

from aec_bench.harness.harbor_importing.contracts import (
    HarborImportError,
    ImportedExecutionEvidence,
    ImportEvidenceContext,
    ImportEvidenceExtension,
    ImportEvidenceIntent,
)

_BUILTIN_EXTENSION_PATHS = MappingProxyType(
    {
        "proposal_session": (
            "aec_bench.harness.harbor_importing.proposal",
            "PROPOSAL_IMPORT_EVIDENCE_EXTENSION",
        ),
    }
)


def execution_kind_from_context(context: ImportEvidenceContext) -> str | None:
    """Resolve the declared execution kind without interpreting its policy."""

    value = context.harbor_result.config.agent.kwargs.get("adapter")
    return value if isinstance(value, str) and value else None


def resolve_import_evidence_extension(
    execution_kind: str | None,
) -> ImportEvidenceExtension | None:
    """Resolve one built-in extension from the fixed execution-kind allowlist."""

    if execution_kind is None:
        return None
    target = _BUILTIN_EXTENSION_PATHS.get(execution_kind)
    if target is None:
        return None
    module_name, attribute_name = target
    module = import_module(module_name)
    extension = cast(
        ImportEvidenceExtension | None,
        getattr(module, attribute_name, None),
    )
    if extension is None or extension.execution_kind != execution_kind:
        raise HarborImportError(
            f"Harbor import evidence extension is invalid for execution kind: {execution_kind}",
        )
    return extension


def load_import_evidence(
    *,
    context: ImportEvidenceContext,
    intent: ImportEvidenceIntent,
) -> ImportedExecutionEvidence | None:
    """Load evidence only when the declared execution kind has an extension."""

    extension = resolve_import_evidence_extension(
        execution_kind_from_context(context),
    )
    if extension is None:
        return None
    return extension.load(context=context, intent=intent)


__all__ = (
    "execution_kind_from_context",
    "load_import_evidence",
    "resolve_import_evidence_extension",
)
