# ABOUTME: Factory function for building a fully configured LambdaRlmAdapter.
# ABOUTME: Reads config, discovers source documents, parses template, and wires dependencies.

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from aec_bench.adapters.lambda_rlm.adapter import LambdaRlmAdapter
from aec_bench.adapters.lambda_rlm.config import (
    LambdaRlmConfig,
    parse_lambda_rlm_config,
    parse_template_meta,
)
from aec_bench.adapters.rlm.client import RlmClient
from aec_bench.adapters.rlm.template import ReportTemplate
from aec_bench.adapters.rlm.template_parser import parse_report_template_with_rubric
from aec_bench.contracts.constitution import ConstitutionManifest

# infer_constitutional_parameters and parse_constitution are imported lazily
# inside build_lambda_rlm_adapter to avoid a circular import: constitutional.py →
# rlm.client → ... → initialiser. Import occurs only when a constitution is
# actually configured.

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]

_log = logging.getLogger(__name__)

_TEXT_EXTENSIONS = {".md", ".txt", ".toml", ".csv", ".json"}


def discover_source_docs(workspace: str) -> dict[str, str]:
    """Discover and read source documents from workspace/documents/.

    Returns a dict keyed by document label (filename stem, or subdir/stem
    for nested files) with the file content as value.
    """
    docs_dir = Path(workspace) / "documents"
    if not docs_dir.is_dir():
        _log.warning("No documents/ directory found in %s", workspace)
        return {}

    result: dict[str, str] = {}
    for path in sorted(docs_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in _TEXT_EXTENSIONS:
            continue

        rel = path.relative_to(docs_dir)
        label = str(rel.with_suffix(""))
        try:
            result[label] = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            _log.warning("Skipping non-text file: %s", path)

    _log.info("Discovered %d source documents in %s", len(result), docs_dir)
    return result


def discover_boilerplate_fragments(
    template_path: Path,
    template_toml: str | None = None,
) -> dict[str, Any]:
    """Load compose-mode boilerplate fragments for compose-mode sections.

    Resolution order:
    1. ``[boilerplate] path`` declared in the template TOML (resolved relative
       to the template file's directory).
    2. Conventional fallback: ``<template_dir>/reference_data/sow_boilerplate.toml``.

    Returns the parsed nested dict; returns an empty dict when no file is found
    (compose sections referencing fragments will then fail loudly at render time,
    which is the intended behaviour).
    """
    # Try the explicit path declared in the template TOML first.
    if template_toml is not None:
        try:
            declared = tomllib.loads(template_toml).get("boilerplate", {}).get("path")
            if declared:
                candidate = Path(declared)
                if not candidate.is_absolute():
                    candidate = template_path.parent / candidate
                if candidate.exists():
                    return tomllib.loads(candidate.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass  # fall through to conventional lookup

    # Conventional fallback.
    boilerplate_path = template_path.parent / "reference_data" / "sow_boilerplate.toml"
    if not boilerplate_path.exists():
        return {}
    return tomllib.loads(boilerplate_path.read_text(encoding="utf-8"))


def _apply_source_mapping(
    schema: Any,
    mapping_path: Path,
) -> Any:
    """Overlay per-section input_mapping from a source_mapping.toml file.

    Reads the mapping file, and for each section that has a mapping entry,
    creates a new TreeSection with the updated input_mapping. Returns a
    new DependencyTreeSchema with the merged sections.
    """
    from dataclasses import replace

    from aec_bench.contracts.repl import DependencyTreeSchema

    mapping_data = tomllib.loads(mapping_path.read_text(encoding="utf-8"))
    section_mappings = mapping_data.get("sections", {})

    if not section_mappings:
        return schema

    updated_sections = []
    applied = 0
    for section in schema.sections:
        section_map = section_mappings.get(section.id)
        if section_map and "sources" in section_map:
            updated = replace(section, input_mapping=tuple(section_map["sources"]))
            updated_sections.append(updated)
            applied += 1
        else:
            updated_sections.append(section)

    _log.info(
        "Applied source_mapping.toml: %d/%d sections updated from %s",
        applied,
        len(updated_sections),
        mapping_path,
    )
    return DependencyTreeSchema(sections=updated_sections)


def _manifest_from_inline_dict(data: dict[str, Any]) -> ConstitutionManifest:
    """Build a ConstitutionManifest from an already-parsed inline dict.

    Used when lambda-rlm.toml has a [constitution.inline] sub-table, to avoid
    a TOML-string round-trip. Matches `parse_constitution` semantics: parses
    the principle list AND all five parameter tables when present. Unspecified
    parameter tables stay None and are populated by
    `infer_constitutional_parameters()` when a client is available.
    """
    from aec_bench.contracts.constitution import (
        ConstitutionalPrinciple,
        EarnedAutonomyParams,
        InformationMinimalityParams,
        ProgressObligationParams,
        SourceFidelityParams,
        StatePersistenceParams,
    )

    principles = [
        ConstitutionalPrinciple(
            name=p["name"],
            description=p["description"],
            evaluation_criteria=p["evaluation_criteria"],
            enabled=p.get("enabled", True),
        )
        for p in data.get("principles", [])
    ]

    im_data = data.get("information_minimality")
    information_minimality = (
        InformationMinimalityParams(
            default_threshold=im_data.get("default_threshold", 2000),
            search_threshold=im_data.get("search_threshold", 10_000),
            preview_length=im_data.get("preview_length", 200),
            truncation_strategy=im_data.get("truncation_strategy", "metadata"),
        )
        if im_data is not None
        else None
    )

    sp_data = data.get("state_persistence")
    state_persistence = (
        StatePersistenceParams(
            preserve_variables=sp_data.get("preserve_variables", True),
            preserve_scratchpad=sp_data.get("preserve_scratchpad", True),
            compaction_strategy=sp_data.get("compaction_strategy", "llm_summary"),
        )
        if sp_data is not None
        else None
    )

    po_data = data.get("progress_obligation")
    progress_obligation = (
        ProgressObligationParams(
            gentle_nudge_turns=po_data.get("gentle_nudge_turns", 10),
            strong_nudge_turns=po_data.get("strong_nudge_turns", 20),
            stall_threshold_turns=po_data.get("stall_threshold_turns", 3),
        )
        if po_data is not None
        else None
    )

    sf_data = data.get("source_fidelity")
    source_fidelity = (
        SourceFidelityParams(
            require_source_tracing=sf_data.get("require_source_tracing", True),
            tbd_placeholder=sf_data.get("tbd_placeholder", "[TBD]"),
            gap_framing=sf_data.get("gap_framing", "exclude"),
        )
        if sf_data is not None
        else None
    )

    ea_data = data.get("earned_autonomy")
    earned_autonomy = (
        EarnedAutonomyParams(
            initial_mode=ea_data.get("initial_mode", "constrained"),
            promotion_threshold=ea_data.get("promotion_threshold", 2),
            demotion_on_stall=ea_data.get("demotion_on_stall", True),
        )
        if ea_data is not None
        else None
    )

    return ConstitutionManifest(
        version=data.get("version", "0.1.0"),
        principles=principles,
        information_minimality=information_minimality,
        state_persistence=state_persistence,
        progress_obligation=progress_obligation,
        source_fidelity=source_fidelity,
        earned_autonomy=earned_autonomy,
    )


def build_lambda_rlm_adapter(
    *,
    config_path: Path | None,
    client: RlmClient,
    adapter_name: str,
    model_name: str,
    workspace: str,
    template_path: Path | None = None,
    trajectory_writer: Any | None = None,
    advisor_client: RlmClient | None = None,
    constitutional_client: RlmClient | None = None,
    task_metadata: dict[str, Any] | None = None,
) -> LambdaRlmAdapter:
    """Build a fully configured LambdaRlmAdapter from config files.

    Constitution resolution (when [constitution] is declared in lambda-rlm.toml):
      1. inline > path > None — inline sub-table wins; otherwise read the
         referenced TOML file (path relative to config_path.parent or workspace).
      2. If constitutional_client is provided, `infer_constitutional_parameters`
         is called with the base manifest + adapter capabilities + task_metadata;
         the returned manifest (with LLM-derived param values) is passed to the
         adapter.
      3. If no constitutional_client is provided, the base manifest is used
         verbatim — any inline param overrides the user wrote are preserved;
         missing param tables stay None and prompts fall back to defaults.
    """
    if config_path and config_path.exists():
        config = parse_lambda_rlm_config(config_path.read_text())
    else:
        config = LambdaRlmConfig()

    if template_path is None and config.template_definition:
        if config_path:
            template_path = config_path.parent / config.template_definition
        else:
            template_path = Path(workspace) / config.template_definition

    if template_path is None or not template_path.exists():
        msg = f"Report template not found: {template_path}"
        raise FileNotFoundError(msg)

    template_toml_text = template_path.read_text(encoding="utf-8")
    schema, rubric = parse_report_template_with_rubric(template_toml_text)
    template_meta = parse_template_meta(template_toml_text)

    # Overlay instance-specific source mapping if present
    mapping_path = template_path.parent / "source_mapping.toml"
    if mapping_path.exists():
        schema = _apply_source_mapping(schema, mapping_path)

    template = ReportTemplate(schema)

    source_docs = discover_source_docs(workspace)

    from aec_bench.adapters.lambda_rlm.sandbox import DocumentSandbox

    sandbox: DocumentSandbox | None = None
    if config.sandbox.enabled:
        sandbox = DocumentSandbox.from_documents(
            source_docs,
            extractor_overrides=config.sandbox.extractor_overrides,
        )

    boilerplate_fragments = discover_boilerplate_fragments(template_path, template_toml_text)

    # Build optional advisor client when configured.
    resolved_advisor_client: RlmClient | None = advisor_client
    if config.advisor and config.advisor.enabled and resolved_advisor_client is None:
        try:
            from aec_bench.adapters.rlm.providers import make_rlm_client
        except ImportError:
            _log.warning("Advisor requested but pydantic-ai is not installed; skipping.")
        else:
            resolved_advisor_client = make_rlm_client(config.advisor.model, cache=True)

    # Resolve constitution: inline > path > None. Inference fires only when a
    # constitutional_client is available AND a manifest is configured.
    constitution: ConstitutionManifest | None = None
    if config.constitution_inline is not None or config.constitution_path is not None:
        if config.constitution_inline is not None:
            base_manifest = _manifest_from_inline_dict(config.constitution_inline)
        else:
            # mypy: config.constitution_path is not None in this branch
            manifest_path = Path(config.constitution_path)  # type: ignore[arg-type]
            if not manifest_path.is_absolute():
                base = config_path.parent if config_path else Path(workspace)
                manifest_path = base / manifest_path
            # Lazy import — see top-of-module note about the circular dependency.
            from aec_bench.contracts.constitution import parse_constitution

            base_manifest = parse_constitution(manifest_path.read_text(encoding="utf-8"))

        if constitutional_client is not None:
            # Lazy import — see top-of-module note about the circular dependency.
            from aec_bench.adapters.constitutional import (
                infer_constitutional_parameters,
            )

            result = infer_constitutional_parameters(
                constitution=base_manifest,
                capabilities=LambdaRlmAdapter.declare_capabilities(),
                task_metadata=task_metadata or {},
                client=constitutional_client,
                model=config.constitution_model or model_name,
            )
            constitution = result.manifest
            _log.info(
                "Constitutional inference: %d principles, gap_framing=%s, preview_length=%s",
                len(constitution.principles),
                constitution.source_fidelity.gap_framing if constitution.source_fidelity else None,
                (constitution.information_minimality.preview_length if constitution.information_minimality else None),
            )
        else:
            constitution = base_manifest

    return LambdaRlmAdapter(
        adapter_name=adapter_name,
        model_name=model_name,
        client=client,
        template=template,
        source_docs=source_docs,
        config=config,
        workspace=workspace,
        trajectory_writer=trajectory_writer,
        advisor_client=resolved_advisor_client,
        advisor_config=config.advisor,
        constitution=constitution,
        rubric=rubric,
        boilerplate_fragments=boilerplate_fragments,
        template_meta=template_meta,
        sandbox=sandbox,
    )
