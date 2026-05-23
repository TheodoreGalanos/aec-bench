# ABOUTME: CLI entry point for verifier-driven remediation — aec-bench remediate <run-dir>.
# ABOUTME: Wires proposer + applier + verifier runner + loop into a single command.

from __future__ import annotations

import json
import re
import tempfile
from dataclasses import asdict
from pathlib import Path

import typer

try:
    import tomllib as _tomllib
except ModuleNotFoundError:
    import tomli as _tomllib  # type: ignore[no-redef]

from aec_bench.adapters.rlm.client import RlmClient, RlmMessage
from aec_bench.contracts.remediation import RemediationResult
from aec_bench.contracts.remediation_config import (
    RemediationTaskConfig,
    parse_remediation_config,
)
from aec_bench.remediation.applier import heading_derived_id, split_sections
from aec_bench.remediation.loop import (
    RemediationConfig,
    SectionSelectorFn,
    run_remediation_loop,
)
from aec_bench.remediation.proposer import propose_patch, propose_patch_annotated
from aec_bench.remediation.verifier_runner import run_verifier


def _load_task_config(task_dir: Path) -> RemediationTaskConfig:
    task_toml = task_dir / "task.toml"
    if not task_toml.exists():
        return RemediationTaskConfig()
    try:
        data = _tomllib.loads(task_toml.read_text())
    except Exception:
        return RemediationTaskConfig()
    return parse_remediation_config(data)


def _build_client(model: str) -> RlmClient:
    from aec_bench.adapters.rlm.providers import make_rlm_client

    return make_rlm_client(model, cache=True)


def _derived_to_canonical_map(run_dir: Path) -> dict[str, str]:
    """Build {heading_derived_id: canonical_id} from the proposer's sections.json.

    Returns {} when sections.json is missing or unreadable — callers fall back
    to the heading-derived ids (legacy behaviour, used by older runs and tests
    that don't write a sections.json).
    """
    sections_path = run_dir / "sections.json"
    if not sections_path.exists():
        return {}
    try:
        data = json.loads(sections_path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    mapping: dict[str, str] = {}
    for canonical_id, entry in data.items():
        content = entry.get("content", "") if isinstance(entry, dict) else ""
        derived = heading_derived_id(content)
        if derived is None:
            # Section content has no top-level heading (e.g. compose-mode
            # sections whose content starts with ## or plain text). Use the
            # canonical ID as both key and value so split_sections output that
            # matches the canonical ID passes the leak check.
            mapping[canonical_id] = canonical_id
        else:
            mapping[derived] = canonical_id
    return mapping


_SECTION_SELECTOR_SYSTEM_PROMPT = """\
You are matching verifier evidence to document section headings.

Given a piece of evidence about a defect and a list of available section IDs,
return a JSON array of section IDs that the evidence concerns. Pick only IDs
that clearly correspond to the evidence. If unsure, return an empty array.

Respond with ONLY the JSON array. No prose. Example: ["scope_of_works"]
"""


def _build_section_selector(selector_model: str, client: RlmClient) -> SectionSelectorFn:
    """Build a SectionSelectorFn that calls the Haiku model to pick sections.

    Returns an empty list on parse failures or when the model picks IDs not
    in the available_sections list (defensive filtering).
    """

    def select(evidence: str, available_sections: list[str]) -> list[str]:
        prompt = (
            f"Evidence: {evidence}\n\n"
            f"Available sections: {available_sections}\n\n"
            f"Return a JSON array of matching section IDs."
        )
        response = client.generate(
            model=selector_model,
            messages=[RlmMessage(role="user", content=prompt)],
            system_prompt=_SECTION_SELECTOR_SYSTEM_PROMPT,
        )
        text = response.output_text.strip()
        data: list = []
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                data = parsed
        except json.JSONDecodeError:
            match = re.search(r"\[.*\]", text, re.DOTALL)
            if match:
                try:
                    parsed = json.loads(match.group(0))
                    if isinstance(parsed, list):
                        data = parsed
                except json.JSONDecodeError:
                    data = []
        return [s for s in data if isinstance(s, str) and s in available_sections]

    return select


def _serialise_result(result: RemediationResult) -> dict:
    return {
        "stop_reason": result.stop_reason,
        "final_reward": result.final_reward,
        "total_patches_applied": result.total_patches_applied,
        "iterations": [asdict(it) for it in result.iterations],
        "hitl_items": [asdict(h) for h in result.hitl_items],
    }


def run_remediate(
    *,
    run_dir: Path,
    task_dir: Path,
    model: str,
    max_iterations: int,
    plateau_threshold: float,
    target_reward: float | None,
    interactive: bool,
    output_dir: Path | None,
    force: bool = False,
    selector_model: str | None = None,
) -> RemediationResult | None:
    """Programmatic entry — used by both the CLI wrapper and tests.

    Returns ``None`` when remediation is disabled for the task and ``force``
    is False.
    """
    task_config = _load_task_config(task_dir)
    if not task_config.enabled and not force:
        typer.echo("Remediation disabled for this task via [remediation] enabled = false. Use --force to override.")
        return None

    # Task-level overrides only apply when CLI flags are at their defaults.
    # Default max_iterations = 3, default target_reward = None.
    effective_max_iterations = (
        task_config.max_iterations if max_iterations == 3 and task_config.max_iterations is not None else max_iterations
    )
    effective_target_reward = (
        task_config.target_reward if target_reward is None and task_config.target_reward is not None else target_reward
    )

    client = _build_client(model)

    def proposer(**kwargs):
        if "annotated_section" in kwargs:
            return propose_patch_annotated(
                section_id=kwargs["section_id"],
                annotated_section=kwargs["annotated_section"],
                span_to_replace=kwargs["span_to_replace"],
                criterion=kwargs["criterion"],
                evidence=kwargs["evidence"],
                client=client,
                model=model,
            )
        return propose_patch(
            section_id=kwargs["section_id"],
            section_excerpt=kwargs["section_excerpt"],
            criterion=kwargs["criterion"],
            evidence=kwargs["evidence"],
            client=client,
            model=model,
        )

    def verifier(*, output_md_text, task_dir):
        with tempfile.TemporaryDirectory(prefix="aec-remediate-verify-") as tmp:
            return run_verifier(
                task_dir=task_dir,
                output_md_text=output_md_text,
                workspace_root=Path(tmp),
            )

    config = RemediationConfig(
        max_iterations=effective_max_iterations,
        plateau_threshold=plateau_threshold,
        target_reward=effective_target_reward,
    )

    iteration_cb = None
    if interactive:

        def iteration_cb(it):
            typer.echo(
                f"\nIteration {it.iteration}: reward {it.reward_before:.3f} → {it.reward_after:.3f} "
                f"({it.patches_applied} applied, {it.patches_rejected} rejected)"
            )
            choice = typer.prompt("Continue? [c/s]", default="c")
            return choice.lower().strip() not in ("s", "stop")

    section_selector: SectionSelectorFn | None = None
    if selector_model:
        selector_client = _build_client(selector_model)
        section_selector = _build_section_selector(selector_model, selector_client)

    result = run_remediation_loop(
        run_dir=run_dir,
        task_dir=task_dir,
        proposer=proposer,
        verifier=verifier,
        config=config,
        section_selector=section_selector,
        on_iteration=iteration_cb,
    )

    out = output_dir or (run_dir / "remediation")
    out.mkdir(parents=True, exist_ok=True)
    (out / "remediation_report.json").write_text(json.dumps(_serialise_result(result), indent=2))
    (out / "hitl_items.json").write_text(json.dumps([asdict(h) for h in result.hitl_items], indent=2))
    (out / "output.final.md").write_text(result.final_output_text)

    # Emit structured sections for the patched output, mirroring the shape that
    # the adapter's sections.json uses — {section_id: {"content": text}}.
    # Section IDs MUST come from the proposer's sections.json (canonical), not
    # from re-deriving them off heading text — otherwise the export overlay
    # lands the remediated content under a stranger key and the original
    # (un-remediated) content is what reaches the reader.
    sections_offsets = split_sections(result.final_output_text)
    derived_to_canonical = _derived_to_canonical_map(run_dir)
    sections_final: dict[str, dict[str, str]] = {}
    for sid, (start, end) in sections_offsets.items():
        if not sid:
            continue  # empty-heading catch-all
        canonical = derived_to_canonical.get(sid, sid)
        sections_final[canonical] = {"content": result.final_output_text[start:end]}
    if derived_to_canonical:
        canonical_ids = set(derived_to_canonical.values())
        leaked = set(sections_final) - canonical_ids
        assert not leaked, f"sections.final.json keys must be ⊆ sections.json keys; non-canonical: {sorted(leaked)}"
    (out / "sections.final.json").write_text(json.dumps(sections_final, indent=2))

    return result


def remediate(
    run_dir: Path = typer.Argument(..., help="Path to a completed run directory"),
    task_dir: Path = typer.Option(
        None,
        "--task-dir",
        help="Task directory (containing tests/verify.py). Defaults to run_dir.parent.parent.",
    ),
    model: str = typer.Option(
        "au.anthropic.claude-sonnet-4-6",
        "--model",
        "-m",
        help="LLM for patch proposals",
    ),
    max_iterations: int = typer.Option(3, "--max-iterations", help="Max remediation iterations"),
    plateau_threshold: float = typer.Option(
        0.02,
        "--plateau-threshold",
        help="Stop when |Δreward| below this between iterations",
    ),
    target_reward: float | None = typer.Option(None, "--target-reward", help="Stop when reward >= this value"),
    interactive: bool = typer.Option(
        False,
        "--interactive",
        help="Pause between iterations for continue/stop confirmation",
    ),
    output_dir: Path | None = typer.Option(
        None,
        "--output-dir",
        help="Where to write artifacts (default: <run_dir>/remediation)",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Run remediation even when task config disables it",
    ),
    selector_model: str = typer.Option(
        "au.anthropic.claude-haiku-4-5-20251001-v1:0",
        "--selector-model",
        help="Model for section selector fallback. Pass empty string to disable.",
    ),
) -> None:
    """Run verifier-driven remediation on a completed run."""
    task = task_dir or run_dir.parent.parent
    result = run_remediate(
        run_dir=run_dir,
        task_dir=task,
        model=model,
        max_iterations=max_iterations,
        plateau_threshold=plateau_threshold,
        target_reward=target_reward,
        interactive=interactive,
        output_dir=output_dir,
        force=force,
        selector_model=selector_model or None,
    )
    if result is None:
        return
    typer.echo(f"Stop reason: {result.stop_reason}")
    typer.echo(f"Final reward: {result.final_reward:.4f}")
    typer.echo(f"Patches applied: {result.total_patches_applied}")
    typer.echo(f"HITL items: {len(result.hitl_items)}")
