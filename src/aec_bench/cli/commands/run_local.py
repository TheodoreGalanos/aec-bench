# ABOUTME: Local RLM execution without Docker, Modal, or Harbor.
# ABOUTME: Sets up workspace, runs adapter in-process, verifies output, and auto-imports to ledger.

from __future__ import annotations

import datetime
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Annotated

import typer

from aec_bench.cli.output import StructuredError, console, emit
from aec_bench.contracts.canonical_refs import CanonicalRefSet, parse_canonical_refs
from aec_bench.evaluation.llm_reviewer import (
    ReviewerEndpointConfig,
    ReviewerRunConfig,
    ReviewerRunResult,
    load_reviewer_config,
    run_workspace_reviewer,
)
from aec_bench.evaluation.normalisation import NormalisationResult, normalise_output
from aec_bench.harness.local_runtime import (
    patch_workspace_paths,
    read_instruction,
    setup_workspace,
    setup_workspace_for_script,
    stage_verifier_assets,
    unstage_verifier_assets,
)

# Output files we expect the adapter to produce
_OUTPUT_FILES = [
    "output.md",
    "sections.json",
    "agent_result.json",
    ".scratchpad.json",
    "symbolic_state.json",
    "trajectory.jsonl",
    "conversation.jsonl",
    "model_reasoning.jsonl",
    "normalisation_report.json",
    "composition_trace.json",
    "grounding_report.json",
]


def load_canonical_refs(task_toml_path: Path) -> CanonicalRefSet:
    """Load canonical_refs from a task.toml's [canonical_refs] table.

    Returns empty CanonicalRefSet if the file or table is absent.
    """
    if not task_toml_path.exists():
        return CanonicalRefSet()
    try:
        import tomllib as _tomllib
    except ModuleNotFoundError:
        import tomli as _tomllib  # type: ignore[no-redef]
    data = _tomllib.loads(task_toml_path.read_text())
    refs_dict = data.get("canonical_refs", {})
    return parse_canonical_refs(refs_dict)


def apply_normalisation(
    output_md: Path,
    refs: CanonicalRefSet,
    report_path: Path,
) -> NormalisationResult:
    """Run canonical-ref normalisation on the agent's output.md.

    Overwrites output.md in place with the normalised text when
    substitutions are made. Writes an audit report to report_path
    only when substitutions occurred. Returns the NormalisationResult.
    """
    text = output_md.read_text()
    result = normalise_output(text, refs)
    if result.substitutions_count > 0:
        output_md.write_text(result.normalised)
        report_path.write_text(
            json.dumps(
                {
                    "substitutions_count": result.substitutions_count,
                    "audit_log": [
                        {
                            "matched_text": m.matched_text,
                            "canonical_value": m.canonical_value,
                            "distance": m.distance,
                            "count": m.count,
                        }
                        for m in result.audit_log
                    ],
                },
                indent=2,
            )
        )
    return result


# Verifier output files (under logs/verifier/)
_VERIFIER_FILES = [
    "logs/verifier/reward.json",
    "logs/verifier/details.json",
    "logs/verifier/feedback.md",
    "logs/verifier/retry.json",
]

_VERIFIER_SIDE_EFFECT_ARTIFACT_DIR = Path("logs/verifier/artifacts")
_REVIEWER_ARTIFACT_DIR = Path("logs/reviewer")
_VERIFIER_RETRY_PROMPT = "verifier_retry_prompt.md"
_VERIFIER_RETRY_TARGET_REWARD = 1.0
_VERIFIER_SIDE_EFFECT_SUFFIXES = (
    "_record.json",
    "_decision.json",
    "_readback_check.json",
    "_notice.json",
    "_report.json",
    "_marker.json",
)
_VERIFIER_SIDE_EFFECT_EXCLUDED_PREFIXES = (
    "expected_",
    "input_",
    "prior_",
    "source_",
)


def _is_verifier_side_effect_artifact(path: Path) -> bool:
    """Return true for root-level JSON artifacts created by the agent or verifier."""
    if not path.is_file() or path.suffix != ".json":
        return False
    if path.name in _OUTPUT_FILES:
        return False
    if path.name.startswith(_VERIFIER_SIDE_EFFECT_EXCLUDED_PREFIXES):
        return False
    return path.name.endswith(_VERIFIER_SIDE_EFFECT_SUFFIXES)


def _read_optional_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _read_verifier_reward(workspace: Path) -> float | None:
    reward_path = workspace / "logs" / "verifier" / "reward.json"
    if not reward_path.exists():
        return None
    try:
        data = json.loads(reward_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    reward = data.get("reward")
    return float(reward) if isinstance(reward, int | float) else None


def _should_run_verifier_feedback_retry(
    workspace: str | Path,
    *,
    reward: float | None,
    target_reward: float = _VERIFIER_RETRY_TARGET_REWARD,
) -> bool:
    """Return true when a task opts into one verifier-feedback retry."""
    if reward is None or reward >= target_reward:
        return False
    return (Path(workspace) / _VERIFIER_RETRY_PROMPT).exists()


def _build_verifier_retry_instruction(
    *,
    workspace: Path,
    base_instruction: str,
    reward: float,
) -> str:
    """Build the second-pass instruction from verifier feedback and prior output."""
    verifier_dir = workspace / "logs" / "verifier"
    retry_instruction = _read_optional_text(workspace / "verifier_retry_instruction.md").strip()
    governing_instruction = retry_instruction or base_instruction.strip()
    retry_prompt = _read_optional_text(workspace / _VERIFIER_RETRY_PROMPT).strip()
    prior_output = _read_optional_text(workspace / "output.md").strip()
    feedback = _read_optional_text(verifier_dir / "feedback.md").strip()
    details = _read_optional_text(verifier_dir / "details.json").strip()

    parts = [
        governing_instruction,
        "---",
        "# Verifier Feedback Retry",
        retry_prompt,
        f"Previous verifier reward: `{reward:.4f}`.",
        "The previous `output.md` was:",
        "```markdown",
        prior_output,
        "```",
    ]
    if feedback:
        parts.extend(
            [
                "The verifier feedback was:",
                "```markdown",
                feedback,
                "```",
            ]
        )
    if details:
        parts.extend(
            [
                "The verifier detail scores were:",
                "```json",
                details,
                "```",
            ]
        )
    parts.append(
        "Repair the workspace now. You may overwrite `output.md` and any required side-effect files. "
        "Do not merely describe files that should be written."
    )
    return "\n\n".join(part for part in parts if part)


def _archive_verifier_retry_attempt(workspace: Path, attempt_name: str) -> Path:
    """Preserve first-attempt output and verifier files before retrying."""
    verifier_dir = workspace / "logs" / "verifier"
    archive_dir = verifier_dir / "attempts" / attempt_name
    archive_dir.mkdir(parents=True, exist_ok=True)

    for relative in [
        Path("output.md"),
        Path("agent_result.json"),
        Path("trajectory.jsonl"),
        Path("conversation.jsonl"),
        Path("logs/verifier/reward.json"),
        Path("logs/verifier/details.json"),
        Path("logs/verifier/feedback.md"),
    ]:
        src = workspace / relative
        if not src.exists():
            continue
        shutil.copy2(src, archive_dir / src.name)

    artifact_dir = archive_dir / "artifacts"
    for src in sorted(workspace.iterdir()):
        if not _is_verifier_side_effect_artifact(src):
            continue
        artifact_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, artifact_dir / src.name)

    return archive_dir


def _prepare_verifier_retry_workspace(workspace: Path, attempt_name: str) -> Path:
    """Archive a failed attempt and clear output.md for retry output."""
    archive_dir = _archive_verifier_retry_attempt(workspace, attempt_name)
    output_path = workspace / "output.md"
    if output_path.exists():
        output_path.unlink()
    return archive_dir


def _write_verifier_retry_summary(workspace: Path, payload: dict[str, object]) -> None:
    retry_path = workspace / "logs" / "verifier" / "retry.json"
    retry_path.parent.mkdir(parents=True, exist_ok=True)
    retry_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _run_adapter(
    *,
    adapter_kind: str,
    workspace: str,
    model: str,
    constitutional_model: str | None = None,
    instruction_override: str | None = None,
) -> dict[str, object]:
    """Execute a task using the adapter registry.

    Builds the adapter via LocalAdapterRegistry, executes it, and
    writes output files to the workspace. Returns the agent result dict.

    When *constitutional_model* is provided and the workspace rlm.toml has
    a [constitution] block, uses that model for constitutional inference
    instead of the default from rlm.toml.
    """
    from aec_bench.adapters.base import AdapterRequest
    from aec_bench.adapters.local_registry import LocalAdapterRegistry
    from aec_bench.adapters.transcript import TranscriptRole
    from aec_bench.trajectory.writer import TrajectoryWriter

    instruction = instruction_override if instruction_override is not None else read_instruction(workspace)
    if not instruction:
        StructuredError(
            message="No instruction file found in task directory",
            why="The workspace must contain an instruction.md (or similar .md file)",
            fix="Add an instruction.md file to the task directory",
        ).print()
        raise typer.Exit(1)

    # Build trajectory writer
    traj_path = str(Path(workspace) / "trajectory.jsonl")
    trajectory_writer = TrajectoryWriter(path=traj_path)

    # Build adapter via registry — constitutional_model is forwarded to _build_rlm
    registry = LocalAdapterRegistry()
    adapter = registry.build(
        adapter_kind=adapter_kind,
        model_name=model,
        workspace=workspace,
        trajectory_writer=trajectory_writer,
        constitutional_model=constitutional_model,
    )

    # Declare bash tool when using tool_loop adapter so it passes the allowlist check
    tools: list = []
    if adapter_kind == "tool_loop":
        from aec_bench.contracts.task_definition import ToolSpec

        tools = [
            ToolSpec(
                name="bash",
                source="builtin",
                description="Execute a bash command in the workspace",
            )
        ]

    # Execute
    result = adapter.execute(
        AdapterRequest(instruction=instruction, tools=tools),
    )

    # Write output.md from adapter result if not already written
    output_path = Path(workspace, "output.md")
    output_source = "adapter"
    if output_path.exists() and output_path.stat().st_size > 0:
        output_source = "direct_write"
    elif result.raw_output_text:
        output_path.write_text(result.raw_output_text)
        output_source = "raw_output"

    agent_result_data: dict[str, object] = {
        "status": result.agent_output.status.value,
        "model": model,
        "adapter": adapter_kind,
        "input_tokens": result.usage_input_tokens or 0,
        "output_tokens": result.usage_output_tokens or 0,
        "output_source": output_source,
    }

    Path(workspace, "agent_result.json").write_text(
        json.dumps(agent_result_data, indent=2),
    )

    # Write conversation.jsonl from the adapter's transcript
    conversation_path = Path(workspace, "conversation.jsonl")
    with conversation_path.open("w", encoding="utf-8") as f:
        for entry in result.transcript:
            f.write(
                json.dumps(
                    {
                        "role": entry.role.value if isinstance(entry.role, TranscriptRole) else str(entry.role),
                        "content": entry.content or "",
                    }
                )
                + "\n"
            )

    return agent_result_data


def _run_legacy_script(
    *,
    workspace: str,
    model: str,
    timeout: int,
) -> dict[str, object]:
    """Execute the RLM task using the legacy standalone script as a subprocess.

    This is the original execution path kept as a fallback for validation.
    """
    from aec_bench.agents.rlm_script import build_rlm_script

    env = dict(os.environ)
    instruction = read_instruction(workspace)
    if not instruction:
        console.print("[red]No instruction file found in task directory[/red]")
        raise typer.Exit(1)

    env["AGENT_INSTRUCTION"] = instruction
    env["AGENT_MODEL"] = model

    # Build the RLM script and patch /workspace/ paths for local execution
    script = build_rlm_script()
    normalised = workspace.rstrip("/")
    script = script.replace("/workspace/", f"{normalised}/")

    console.print(f"  Script: {len(script):,} chars")

    proc = subprocess.run(
        [sys.executable, "-c", script],
        cwd=workspace,
        env=env,
        timeout=timeout,
        capture_output=False,  # let stderr stream to terminal
    )

    if proc.returncode != 0:
        console.print(f"\n[yellow]Process exited with code {proc.returncode}[/yellow]")

    # Read results
    result_path = Path(workspace, "agent_result.json")
    if result_path.exists():
        return json.loads(result_path.read_text())
    return {}


def _report_results(
    agent_result: dict[str, object],
    *,
    agent_seconds: float | None = None,
    verifier_seconds: float | None = None,
    reward: float | None = None,
) -> None:
    """Print agent result summary to the console."""
    if not agent_result:
        console.print("[yellow]No agent_result.json found[/yellow]")
        return

    console.print()
    console.print(f"[bold]Status:[/bold] {agent_result.get('status', 'unknown')}")
    console.print(
        f"[bold]Tokens:[/bold] {agent_result.get('input_tokens', 0):,} in / "
        f"{agent_result.get('output_tokens', 0):,} out"
    )
    turns = agent_result.get("turns_used")
    if turns:
        console.print(f"[bold]Turns:[/bold] {turns}")
    console.print(f"[bold]Output source:[/bold] {agent_result.get('output_source', 'unknown')}")
    compactions = agent_result.get("compaction_count")
    if compactions:
        console.print(f"[bold]Compactions:[/bold] {compactions}")
    cr = agent_result.get("cache_read_tokens", 0)
    cw = agent_result.get("cache_write_tokens", 0)
    if cr or cw:
        console.print(f"[bold]Cache:[/bold] {cr:,} read / {cw:,} write")
    if agent_seconds is not None:
        console.print(f"[bold]Agent time:[/bold] {agent_seconds:.1f}s")
    if verifier_seconds is not None:
        console.print(f"[bold]Verifier time:[/bold] {verifier_seconds:.1f}s")
    if reward is not None:
        console.print(f"[bold]Reward:[/bold] {reward:.4f}")


def _copy_output_files(
    workspace: str,
    out_path: Path,
) -> list[str]:
    """Copy output files from workspace to the results directory."""
    out_path.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for fname in _OUTPUT_FILES:
        src = Path(workspace, fname)
        if src.exists():
            shutil.copy2(src, out_path / fname)
            copied.append(fname)
    # Copy verifier output files (preserving subdirectory structure)
    for fname in _VERIFIER_FILES:
        src = Path(workspace, fname)
        if src.exists():
            dest = out_path / fname
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            copied.append(fname)
    attempts_src = Path(workspace) / "logs" / "verifier" / "attempts"
    if attempts_src.exists():
        attempts_dest = out_path / "logs" / "verifier" / "attempts"
        shutil.copytree(attempts_src, attempts_dest, dirs_exist_ok=True)
        for src in sorted(attempts_src.rglob("*")):
            if src.is_file():
                copied.append(str(src.relative_to(Path(workspace))))
    artifact_dir = out_path / _VERIFIER_SIDE_EFFECT_ARTIFACT_DIR
    for src in sorted(Path(workspace).iterdir()):
        if not _is_verifier_side_effect_artifact(src):
            continue
        dest = artifact_dir / src.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        copied.append(str(_VERIFIER_SIDE_EFFECT_ARTIFACT_DIR / src.name))
    reviewer_src = Path(workspace) / _REVIEWER_ARTIFACT_DIR
    if reviewer_src.exists():
        reviewer_dest = out_path / _REVIEWER_ARTIFACT_DIR
        shutil.copytree(reviewer_src, reviewer_dest, dirs_exist_ok=True)
        for src in sorted(reviewer_src.rglob("*")):
            if src.is_file():
                copied.append(str(src.relative_to(Path(workspace))))
    return copied


def _run_verifier(*, workspace: str, output_file: str) -> float | None:
    """Run the task verifier and return elapsed seconds, or None if no verifier.

    Looks for ``tests/verify.py`` (preferred) or ``tests/test.sh`` (fallback)
    in the workspace directory.  Creates the reward output directory and
    executes the verifier with a 120-second timeout.
    """
    ws = Path(workspace)
    verify_py = ws / "tests" / "verify.py"
    test_sh = ws / "tests" / "test.sh"

    if not verify_py.exists() and not test_sh.exists():
        return None

    # Ensure the reward output directory exists
    reward_dir = ws / "logs" / "verifier"
    reward_dir.mkdir(parents=True, exist_ok=True)
    reward_file = reward_dir / "reward.json"

    env = {**os.environ, "PYTHONPATH": workspace}

    start = time.monotonic()

    if verify_py.exists():
        proc = subprocess.run(
            [
                sys.executable,
                str(verify_py),
                "--input",
                output_file,
                "--output",
                str(reward_file),
            ],
            cwd=workspace,
            env=env,
            timeout=120,
            capture_output=True,
        )
        if proc.returncode == 0 and not reward_file.exists():
            proc = subprocess.run(
                [sys.executable, str(verify_py), workspace],
                cwd=workspace,
                env=env,
                timeout=120,
                capture_output=True,
            )
        if proc.returncode != 0:
            console.print(f"[yellow]Verifier exited with code {proc.returncode}[/yellow]")
            if proc.stderr:
                console.print(proc.stderr.decode("utf-8", errors="replace")[:500])
    else:
        proc = subprocess.run(
            ["bash", str(test_sh)],
            cwd=workspace,
            env=env,
            timeout=120,
            capture_output=True,
        )
        if proc.returncode != 0:
            console.print(f"[yellow]Verifier exited with code {proc.returncode}[/yellow]")
            if proc.stderr:
                console.print(proc.stderr.decode("utf-8", errors="replace")[:500])

    elapsed = time.monotonic() - start
    return elapsed


def _auto_import(
    *,
    workspace: str,
    task_dir: Path,
    model: str,
    adapter: str,
    agent_seconds: float,
    verifier_seconds: float | None,
) -> None:
    """Build a TrialRecord from the workspace and write it to the ledger.

    Derives task_id from the task directory path relative to the tasks root,
    following the same convention as the ``import-local`` CLI command.
    """
    from aec_bench.cli.commands.config import resolve_path
    from aec_bench.contracts.trial_record import TimingRecord
    from aec_bench.harness.local_import import (
        build_trial_record_from_workspace,
        find_tasks_root,
    )
    from aec_bench.ledger.writer import write_trial_record

    tasks_root = find_tasks_root(task_dir)
    try:
        task_id = task_dir.relative_to(tasks_root).as_posix().replace("/", "__")
    except ValueError:
        task_id = task_dir.name

    task_slug = task_dir.name
    trial_id = f"local-{task_slug}-{int(time.time())}"
    experiment_id = "local"

    instruction = read_instruction(workspace)

    timing = TimingRecord(
        total_seconds=agent_seconds + (verifier_seconds or 0.0),
        agent_seconds=agent_seconds,
        verification_seconds=verifier_seconds,
    )

    record = build_trial_record_from_workspace(
        workspace_dir=Path(workspace),
        trial_id=trial_id,
        experiment_id=experiment_id,
        task_id=task_id,
        model=model,
        adapter=adapter,
        instruction=instruction,
        timing=timing,
    )

    ledger_root = resolve_path("ledger_root")
    record_path = write_trial_record(ledger_root=ledger_root, record=record)
    console.print(f"\n[bold]Imported to ledger:[/bold] {record_path}")
    console.print(f"  View at: http://127.0.0.1:8710/viewer/{experiment_id}/{trial_id}")


def run_local(
    task_path: str = typer.Argument(help="Path to task directory"),
    model: str = typer.Option(..., "--model", "-m", help="Model name (e.g. us.anthropic.claude-sonnet-4-6)"),
    adapter: str = typer.Option(
        "rlm",
        "--adapter",
        "--harness",
        "-a",
        help="Agent harness: rlm, direct, tool_loop, pydantic_ai, lambda-rlm (default: rlm)",
    ),
    output_dir: str | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory (default: task_path/_local_runs/<timestamp>)",
    ),
    timeout: int = typer.Option(1800, "--timeout", "-t", help="Timeout in seconds (default: 30 minutes)"),
    keep_workspace: bool = typer.Option(False, "--keep-workspace", help="Don't delete temp workspace after run"),
    legacy_script: bool = typer.Option(
        False,
        "--legacy-script",
        help="Use the legacy standalone script instead of the library adapter",
    ),
    no_verify: Annotated[bool, typer.Option("--no-verify", help="Skip verifier execution after the agent run")] = False,
    no_import: Annotated[bool, typer.Option("--no-import", help="Skip auto-import of results into the ledger")] = False,
    no_normalise: Annotated[
        bool,
        typer.Option(
            "--no-normalise",
            help="Skip canonical-reference normalisation of agent output before verifier.",
        ),
    ] = False,
    constitutional_model: str | None = typer.Option(
        None,
        "--constitutional-model",
        help=(
            "Model for constitutional inference (overrides rlm.toml [constitution].model). "
            "Only used when rlm.toml has a [constitution] section."
        ),
    ),
    reviewer: bool = typer.Option(False, "--reviewer", help="Run the post-verifier LLM reviewer stage"),
    reviewer_model: str | None = typer.Option(None, "--reviewer-model", help="Single reviewer model name"),
    reviewer_models_config: Path | None = typer.Option(
        None,
        "--reviewer-models-config",
        help="JSON/YAML reviewer model endpoint config",
    ),
    fail_on_reviewer_error: bool = typer.Option(
        False,
        "--fail-on-reviewer-error",
        help="Fail the run when the reviewer stage cannot complete",
    ),
) -> None:
    """Run a task locally without Docker or Harbor.

    Sets up a temp workspace, copies task files, and runs the adapter
    in-process. Uses pydantic-ai for LLM provider support.

    Examples:
      aec-bench run-local tasks/electrical/voltage-drop -m gpt-4.1-mini --adapter direct
    """
    task_dir = Path(task_path).resolve()
    if not task_dir.is_dir():
        StructuredError(
            message=f"Task directory not found: {task_dir}",
            why="The path does not exist or is not a directory",
            fix="Check the path and try again",
            try_steps=[
                "ls tasks/",
                "aec-bench task list",
            ],
        ).print()
        raise typer.Exit(1)

    # Check pydantic-ai is installed — it's an optional dependency
    try:
        import pydantic_ai  # noqa: F401
    except ImportError as exc:
        StructuredError(
            message="pydantic-ai is not installed",
            why="pydantic-ai is an optional dependency required for local execution",
            fix="Install it with uv",
            try_steps=["uv pip install 'pydantic-ai>=0.1'"],
        ).print()
        raise typer.Exit(1) from exc

    console.print(f"[bold]Setting up local workspace for {task_dir.name}...[/bold]")

    # Legacy script path needs extra workspace setup (path patching, etc.)
    if legacy_script:
        workspace = setup_workspace_for_script(str(task_dir))
    else:
        workspace = setup_workspace(str(task_dir))
        patch_workspace_paths(workspace)

    console.print(f"  Workspace: {workspace}")
    console.print(f"  Model: {model}")
    console.print(f"  Adapter: {adapter}")
    if legacy_script:
        console.print("  Mode: [dim]legacy-script[/dim]")
    console.print()
    reviewer_result: ReviewerRunResult | None = None
    reviewer_config = _reviewer_config_from_cli(
        enabled=reviewer,
        model=reviewer_model,
        models_config=reviewer_models_config,
        fail_on_error=fail_on_reviewer_error,
    )

    try:
        console.print("[bold]Running agent...[/bold]")
        console.print("\u2500" * 60)

        # Enable adapter logging so the user sees progress in the terminal
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(name)s %(message)s",
            datefmt="%H:%M:%S",
            stream=sys.stderr,
        )

        agent_start = time.monotonic()

        if legacy_script:
            agent_result = _run_legacy_script(
                workspace=workspace,
                model=model,
                timeout=timeout,
            )
        else:
            agent_result = _run_adapter(
                adapter_kind=adapter,
                workspace=workspace,
                model=model,
                constitutional_model=constitutional_model,
            )

        agent_seconds = time.monotonic() - agent_start

        console.print("\u2500" * 60)

        # Normalise agent output against canonical refs from task.toml.
        # Runs AFTER adapter writes output.md, BEFORE verifier consumes it.
        if not no_normalise:
            refs = load_canonical_refs(task_dir / "task.toml")
            if refs.refs:
                report_path = Path(workspace) / "normalisation_report.json"
                norm_result = apply_normalisation(Path(workspace) / "output.md", refs, report_path)
                if norm_result.substitutions_count > 0:
                    print(
                        f"Normalised {norm_result.substitutions_count} reference(s); audit log: {report_path}",
                        file=sys.stderr,
                    )

        # Run verifier unless skipped
        verifier_seconds: float | None = None
        reward: float | None = None
        output_file = str(Path(workspace) / "output.md")

        if not no_verify:
            stage_verifier_assets(task_dir, workspace)
            console.print("[bold]Running verifier...[/bold]")
            verifier_seconds = _run_verifier(
                workspace=workspace,
                output_file=output_file,
            )
            if verifier_seconds is None:
                console.print("[dim]No verifier found, skipping[/dim]")
            else:
                reward = _read_verifier_reward(Path(workspace))
                console.print(f"[green]Verifier completed in {verifier_seconds:.1f}s[/green]")

        if (
            not legacy_script
            and not no_verify
            and verifier_seconds is not None
            and _should_run_verifier_feedback_retry(Path(workspace), reward=reward)
        ):
            assert reward is not None
            console.print("[bold]Running verifier-feedback retry...[/bold]")
            _prepare_verifier_retry_workspace(Path(workspace), "attempt-01")
            unstage_verifier_assets(workspace)
            base_instruction = read_instruction(workspace)
            retry_instruction = _build_verifier_retry_instruction(
                workspace=Path(workspace),
                base_instruction=base_instruction,
                reward=reward,
            )
            initial_reward = reward

            retry_agent_start = time.monotonic()
            agent_result = _run_adapter(
                adapter_kind=adapter,
                workspace=workspace,
                model=model,
                constitutional_model=constitutional_model,
                instruction_override=retry_instruction,
            )
            retry_agent_seconds = time.monotonic() - retry_agent_start
            agent_seconds += retry_agent_seconds

            if not no_normalise:
                refs = load_canonical_refs(task_dir / "task.toml")
                if refs.refs:
                    report_path = Path(workspace) / "normalisation_report.json"
                    norm_result = apply_normalisation(Path(workspace) / "output.md", refs, report_path)
                    if norm_result.substitutions_count > 0:
                        print(
                            f"Normalised {norm_result.substitutions_count} reference(s); audit log: {report_path}",
                            file=sys.stderr,
                        )

            stage_verifier_assets(task_dir, workspace)
            retry_verifier_seconds = _run_verifier(
                workspace=workspace,
                output_file=str(Path(workspace) / "output.md"),
            )
            if retry_verifier_seconds is not None:
                verifier_seconds += retry_verifier_seconds
            reward = _read_verifier_reward(Path(workspace))
            retry_summary = {
                "performed": True,
                "initial_reward": initial_reward,
                "final_reward": reward,
                "retry_agent_seconds": retry_agent_seconds,
                "retry_verifier_seconds": retry_verifier_seconds,
            }
            _write_verifier_retry_summary(Path(workspace), retry_summary)
            agent_result.update(
                {
                    "verifier_retry_performed": True,
                    "initial_reward": initial_reward,
                    "final_reward": reward,
                }
            )
            Path(workspace, "agent_result.json").write_text(
                json.dumps(agent_result, indent=2),
                encoding="utf-8",
            )

        if reviewer_config is not None and reviewer_config.enabled:
            console.print("[bold]Running LLM reviewer...[/bold]")
            reviewer_result = run_workspace_reviewer(
                task_dir=task_dir,
                workspace_dir=Path(workspace),
                config=reviewer_config,
            )
            if reviewer_result.status == "complete":
                console.print("[green]LLM reviewer completed[/green]")
            else:
                console.print(f"[yellow]LLM reviewer status: {reviewer_result.status}[/yellow]")

        _report_results(
            agent_result,
            agent_seconds=agent_seconds,
            verifier_seconds=verifier_seconds,
            reward=reward,
        )

        # Determine output directory
        if output_dir:
            out_path = Path(output_dir)
        else:
            timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            out_path = task_dir / "_local_runs" / timestamp

        copied = _copy_output_files(workspace, out_path)
        if copied:
            console.print(f"\n[bold]Results copied to:[/bold] {out_path}")
            for f in copied:
                size = (out_path / f).stat().st_size
                console.print(f"  {f} ({size:,} bytes)")

        # Auto-import to ledger unless skipped
        if not no_import:
            try:
                _auto_import(
                    workspace=workspace,
                    task_dir=task_dir,
                    model=model,
                    adapter=adapter,
                    agent_seconds=agent_seconds,
                    verifier_seconds=verifier_seconds,
                )
            except Exception as exc:
                console.print(f"[yellow]Auto-import failed: {exc}[/yellow]")

        emit(
            "run-local",
            {
                "status": agent_result.get("status", "unknown"),
                "adapter": adapter,
                "mode": "legacy-script" if legacy_script else "adapter",
                "output_dir": str(out_path),
                "files": copied,
                "agent_seconds": agent_seconds,
                "verifier_seconds": verifier_seconds,
                "reward": reward,
                "reviewer_status": reviewer_result.status if reviewer_result is not None else None,
            },
        )

    except KeyboardInterrupt:
        agent_seconds = time.monotonic() - agent_start
        console.print("\n" + "\u2500" * 60)
        console.print("[yellow]Interrupted — saving partial results...[/yellow]")

        # Determine output directory for partial results
        if output_dir:
            out_path = Path(output_dir)
        else:
            timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            out_path = task_dir / "_local_runs" / f"{timestamp}-partial"

        copied = _copy_output_files(workspace, out_path)
        if copied:
            console.print(f"[bold]Partial results saved to:[/bold] {out_path}")
            for f in copied:
                size = (out_path / f).stat().st_size
                console.print(f"  {f} ({size:,} bytes)")
        else:
            console.print("[dim]No output files to save[/dim]")

        console.print(f"[bold]Agent time before interrupt:[/bold] {agent_seconds:.1f}s")
        raise typer.Exit(130) from None

    except subprocess.TimeoutExpired as exc:
        console.print(f"\n[red]Timeout after {timeout}s[/red]")
        raise typer.Exit(1) from exc

    finally:
        if keep_workspace:
            console.print(f"\n[dim]Workspace kept at: {workspace}[/dim]")
        else:
            shutil.rmtree(workspace, ignore_errors=True)


def _reviewer_config_from_cli(
    *,
    enabled: bool,
    model: str | None,
    models_config: Path | None,
    fail_on_error: bool,
) -> ReviewerRunConfig | None:
    if models_config is not None:
        config = load_reviewer_config(models_config)
        return config.model_copy(update={"enabled": True, "fail_on_error": fail_on_error or config.fail_on_error})
    if model is not None:
        return ReviewerRunConfig(
            enabled=True,
            fail_on_error=fail_on_error,
            models=[
                ReviewerEndpointConfig(
                    name=model,
                    model=model,
                )
            ],
        )
    if enabled:
        return ReviewerRunConfig(enabled=True, fail_on_error=fail_on_error)
    return None
