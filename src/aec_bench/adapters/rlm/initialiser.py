# ABOUTME: Config-driven RLM adapter initialisation from rlm.toml and template files.
# ABOUTME: Reads config paths and assembles a fully-configured RlmAdapter.

from __future__ import annotations

from pathlib import Path
from typing import Any

from aec_bench.adapters.rlm.adapter import RlmAdapter
from aec_bench.adapters.rlm.client import RlmClient
from aec_bench.adapters.rlm.config import RlmConfig, parse_rlm_config
from aec_bench.contracts.constitution import ConstitutionManifest, parse_constitution
from aec_bench.templates.report.assets import load_report_assets
from aec_bench.templates.report.session import ReportSession
from aec_bench.templates.report.sources import contained_path


def build_rlm_adapter(
    *,
    rlm_config_path: Path | None,
    client: RlmClient,
    adapter_name: str,
    model_name: str,
    subcall_client: RlmClient | None = None,
    subcall_model: str | None = None,
    compaction_client: RlmClient | None = None,
    trajectory_writer: Any | None = None,
    workspace_path: str | None = None,
    external_system_prompt: str | None = None,
    advisor_client: RlmClient | None = None,
    constitutional_client: RlmClient | None = None,
    task_metadata: dict[str, Any] | None = None,
    configuration: dict[str, Any] | None = None,
    parsed_config: RlmConfig | None = None,
) -> RlmAdapter:
    """Bind a report template and explicit configuration in the actor workspace."""
    if rlm_config_path is None and workspace_path is None:
        raise ValueError("workspace_path is required without an RLM configuration file")
    config_root = rlm_config_path.parent if rlm_config_path else Path(workspace_path or ".")
    config = parsed_config or parse_rlm_config(
        rlm_config_path.read_text() if rlm_config_path else "", overrides=configuration
    )
    if constitutional_client is not None:
        raise ValueError("constitutional inference is unsupported in metered report execution")
    template = _load_report_template(
        config,
        config_root=config_root,
        workspace=Path(workspace_path) if workspace_path else config_root,
    )
    resolved_system_prompt, scratchpad_path = _resolve_workspace_surface(
        workspace_path=workspace_path,
        external_system_prompt=external_system_prompt,
    )
    constitution = _resolve_constitution(
        config,
        config_root=config_root,
    )

    return RlmAdapter(
        adapter_name=adapter_name,
        model_name=model_name,
        client=client,
        guardrails=config.guardrails,
        execution=config.execution,
        hints=config.hints or None,
        prohibited=config.prohibited or None,
        subcall_client=subcall_client,
        subcall_model=subcall_model or config.execution.subcall_model,
        subcall_configs=config.subcalls or None,
        template=template,
        compaction_client=compaction_client,
        trajectory_writer=trajectory_writer,
        scratchpad_path=scratchpad_path,
        external_system_prompt=resolved_system_prompt or "",
        workspace_path=workspace_path,
        advisor_client=advisor_client or subcall_client or client,
        advisor_config=config.advisor,
        constitution=constitution,
    )


def _load_report_template(
    config: RlmConfig,
    *,
    config_root: Path,
    workspace: Path | None = None,
) -> ReportSession | None:
    if not config.template_definition:
        return None
    template_path = config_root / config.template_definition
    return load_report_assets(
        template_path.resolve(),
        workspace=workspace or config_root,
        source_mapping=config.source_mapping,
        validation_rules=config.validation_rules,
    ).session


def _resolve_workspace_surface(
    *,
    workspace_path: str | None,
    external_system_prompt: str | None,
) -> tuple[str | None, str | None]:
    if workspace_path is None:
        return external_system_prompt, None
    workspace = Path(workspace_path)
    resolved_prompt = _workspace_system_prompt(
        workspace,
        external_system_prompt=external_system_prompt,
    )
    return (
        _append_workspace_notes(workspace, system_prompt=resolved_prompt),
        str(workspace / ".scratchpad.json"),
    )


def _workspace_system_prompt(
    workspace: Path,
    *,
    external_system_prompt: str | None,
) -> str | None:
    if external_system_prompt is not None:
        return external_system_prompt
    system_prompt_path = workspace / "system_prompt.md"
    if not system_prompt_path.exists():
        return None
    return system_prompt_path.read_text().strip()


def _append_workspace_notes(
    workspace: Path,
    *,
    system_prompt: str | None,
) -> str | None:
    notes_path = workspace / "notes.md"
    if not notes_path.exists():
        return system_prompt
    notes = notes_path.read_text().strip()
    if not notes or notes.startswith("<!--"):
        return system_prompt
    separator = "\n\n" if system_prompt else ""
    return (
        f"{system_prompt or ''}{separator}"
        "## Project-Specific Instructions\n\n"
        f"{notes}\n\n"
        "Apply these instructions throughout the report."
    )


def _resolve_constitution(
    config: RlmConfig,
    *,
    config_root: Path,
) -> ConstitutionManifest | None:
    if config.constitution_inline is not None:
        return config.constitution_inline
    if config.constitution_path is None:
        return None
    path = _resolve_constitution_path(
        Path(config.constitution_path),
        config_root=config_root,
    )
    return parse_constitution(path.read_text())


def _resolve_constitution_path(
    path: Path,
    *,
    config_root: Path,
) -> Path:
    return contained_path(config_root, path)
