# ABOUTME: Factory function for building a fully configured LambdaRlmAdapter.
# ABOUTME: Reads config, discovers source documents, parses template, and wires dependencies.

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from aec_bench.adapters.lambda_rlm.adapter import LambdaRlmAdapter
from aec_bench.adapters.lambda_rlm.config import (
    parse_lambda_rlm_config,
    parse_template_meta,
)
from aec_bench.adapters.rlm.client import RlmClient
from aec_bench.contracts.constitution import ConstitutionManifest, parse_constitution_data
from aec_bench.templates.report.assets import load_report_assets
from aec_bench.templates.report.sources import contained_path

_log = logging.getLogger(__name__)


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
    configuration: dict[str, Any] | None = None,
) -> LambdaRlmAdapter:
    """Bind validated public report assets and explicit condition parameters."""
    if config_path and config_path.exists():
        config = parse_lambda_rlm_config(config_path.read_text(), overrides=configuration)
    else:
        config = parse_lambda_rlm_config("", overrides=configuration)

    if template_path is None and config.template_definition:
        if config_path:
            template_path = config_path.parent / config.template_definition
        else:
            template_path = Path(workspace) / config.template_definition

    if template_path is None or not template_path.exists():
        msg = f"Report template not found: {template_path}"
        raise FileNotFoundError(msg)

    template_path = contained_path(Path(workspace), template_path)
    template_toml_text = template_path.read_text(encoding="utf-8")
    assets = load_report_assets(
        template_path.resolve(),
        workspace=Path(workspace),
        source_mapping=config.source_mapping,
        validation_rules=config.validation_rules,
    )
    template = assets.session
    rubric = template.rubric
    source_docs = assets.source_docs
    template_meta = parse_template_meta(template_toml_text)

    from aec_bench.adapters.lambda_rlm.sandbox import DocumentSandbox

    sandbox: DocumentSandbox | None = None
    if config.sandbox.enabled:
        sandbox = DocumentSandbox.from_documents(
            source_docs,
            extractor_overrides=config.sandbox.extractor_overrides,
        )

    boilerplate_fragments = assets.boilerplate

    if constitutional_client is not None:
        raise ValueError("constitutional inference is unsupported in metered report execution")
    resolved_advisor_client = advisor_client

    # Resolve fixed parameters; no model inference takes place during setup.
    constitution: ConstitutionManifest | None = None
    if config.constitution_inline is not None or config.constitution_path is not None:
        if config.constitution_inline is not None:
            base_manifest = parse_constitution_data(config.constitution_inline)
        else:
            # mypy: config.constitution_path is not None in this branch
            manifest_path = Path(config.constitution_path)  # type: ignore[arg-type]
            if not manifest_path.is_absolute():
                base = config_path.parent if config_path else Path(workspace)
                manifest_path = base / manifest_path
            manifest_path = contained_path(Path(workspace), manifest_path)
            from aec_bench.contracts.constitution import parse_constitution

            base_manifest = parse_constitution(manifest_path.read_text(encoding="utf-8"))

        unsupported = ("state_persistence", "progress_obligation", "earned_autonomy")
        if any(getattr(base_manifest, name) is not None for name in unsupported):
            raise ValueError("lambda-RLM cannot apply state persistence, progress, or autonomy parameters")
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
