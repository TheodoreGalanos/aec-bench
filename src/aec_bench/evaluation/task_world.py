# ABOUTME: Materialises task-world profiles and final run evidence for reviewer stages.
# ABOUTME: Loads explicit sidecars or derives conservative profiles from task directories.

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from aec_bench.contracts.task_world import MaterializedTaskWorldRun, TaskWorldProfile

TASK_WORLD_SIDECARS = (
    "world.yaml",
    "world.yml",
    "world.json",
    "logic_profile.yaml",
    "logic_profile.yml",
    "logic_profile.json",
)
_ROOT_JSON_ARTIFACT_SUFFIXES = (
    "_record.json",
    "_decision.json",
    "_readback_check.json",
    "_notice.json",
    "_report.json",
    "_marker.json",
)
_ROOT_JSON_EXCLUDED_PREFIXES = ("expected_", "input_", "prior_", "source_")
_MAX_TEXT_CHARS = 20_000


def load_task_world_profile(task_dir: Path) -> TaskWorldProfile | None:
    sidecar = _first_existing([task_dir / name for name in TASK_WORLD_SIDECARS])
    if sidecar is None:
        return None
    payload = _read_sidecar(sidecar)
    merged = _merge_world_payload(_default_profile_payload(task_dir), payload)
    return TaskWorldProfile.model_validate(merged)


def default_task_world_profile(task_dir: Path) -> TaskWorldProfile:
    return TaskWorldProfile.model_validate(_default_profile_payload(task_dir))


def resolve_task_world_profile(task_dir: Path) -> TaskWorldProfile:
    return load_task_world_profile(task_dir) or default_task_world_profile(task_dir)


def materialize_workspace_task_world_run(
    *,
    task_dir: Path,
    workspace_dir: Path,
) -> MaterializedTaskWorldRun:
    return MaterializedTaskWorldRun(
        world_profile=resolve_task_world_profile(task_dir),
        evidence=workspace_evidence(task_dir=task_dir, workspace_dir=workspace_dir),
    )


def materialize_harbor_task_world_run(
    *,
    repo_root: Path,
    trial_dir: Path,
) -> MaterializedTaskWorldRun:
    task_dir = repo_root / harbor_trial_task_path(trial_dir)
    return MaterializedTaskWorldRun(
        world_profile=resolve_task_world_profile(task_dir),
        evidence=harbor_trial_evidence(task_dir=task_dir, trial_dir=trial_dir),
    )


def workspace_evidence(*, task_dir: Path, workspace_dir: Path) -> dict[str, Any]:
    verifier_dir = workspace_dir / "logs" / "verifier"
    reward = _read_json(verifier_dir / "reward.json")
    details = _read_json(verifier_dir / "details.json")
    output_md = _read_text(workspace_dir / "output.md")
    return {
        "source": "workspace",
        "task": {
            "path": str(task_dir),
            "instruction": _read_text(task_dir / "instruction.md"),
        },
        "agent": {
            "output_md": output_md,
            "output_available": output_md is not None,
            "agent_result": _read_json(workspace_dir / "agent_result.json"),
        },
        "verifier": {
            "reward": reward,
            "reward_available": reward is not None,
            "details": details,
            "details_available": details is not None,
            "feedback": _read_text(verifier_dir / "feedback.md"),
            "retry": _read_json(verifier_dir / "retry.json"),
        },
        "trace": {
            "conversation_tail": _read_text_tail(workspace_dir / "conversation.jsonl"),
            "trajectory_tail": _read_text_tail(workspace_dir / "trajectory.jsonl"),
        },
        "artifacts": {
            "root_json": _root_json_artifacts(workspace_dir),
            "verifier_artifacts": _directory_listing(verifier_dir / "artifacts"),
        },
    }


def harbor_trial_evidence(*, task_dir: Path, trial_dir: Path) -> dict[str, Any]:
    reward = _read_json(trial_dir / "verifier" / "reward.json")
    details = _read_json(trial_dir / "verifier" / "details.json")
    output_md = _read_text(
        _first_existing(
            [
                trial_dir / "agent" / "output.md",
                trial_dir / "artifacts" / "agent" / "output.md",
            ]
        )
    )
    return {
        "source": "harbor_trial",
        "task": {
            "path": str(task_dir),
            "instruction": _read_text(task_dir / "instruction.md"),
        },
        "agent": {
            "output_md": output_md,
            "output_available": output_md is not None,
            "agent_result": _read_json(
                _first_existing(
                    [
                        trial_dir / "agent" / "agent_result.json",
                        trial_dir / "artifacts" / "agent" / "agent_result.json",
                    ]
                )
            ),
        },
        "verifier": {
            "reward": reward,
            "reward_available": reward is not None,
            "details": details,
            "details_available": details is not None,
            "feedback": _read_text(trial_dir / "verifier" / "feedback.md"),
        },
        "trace": {
            "conversation_tail": _read_text_tail(
                _first_existing(
                    [
                        trial_dir / "agent" / "conversation.jsonl",
                        trial_dir / "artifacts" / "agent" / "conversation.jsonl",
                    ]
                )
            ),
            "trajectory_tail": _read_text_tail(
                _first_existing(
                    [
                        trial_dir / "agent" / "trajectory.jsonl",
                        trial_dir / "artifacts" / "agent" / "trajectory.jsonl",
                    ]
                )
            ),
        },
        "artifacts": {
            "verifier_artifacts": _directory_listing(trial_dir / "verifier" / "artifacts"),
        },
    }


def harbor_trial_task_path(trial_dir: Path) -> Path:
    payload = _read_json(trial_dir / "result.json")
    if not isinstance(payload, dict):
        msg = f"expected JSON object in {trial_dir / 'result.json'}"
        raise RuntimeError(msg)
    config = payload.get("config", {})
    if not isinstance(config, dict):
        raise RuntimeError("Harbor result missing config object")
    task = config.get("task", {})
    if not isinstance(task, dict):
        raise RuntimeError("Harbor result missing config.task object")
    path = task.get("path")
    if not isinstance(path, str) or not path:
        raise RuntimeError("Harbor result missing config.task.path")
    return Path(path)


def _default_profile_payload(task_dir: Path) -> dict[str, Any]:
    task_id = _task_id(task_dir)
    instruction = _read_text(task_dir / "instruction.md")
    return {
        "world_id": f"aec_bench.{task_id}",
        "name": f"AEC-Bench task world: {task_dir.name}",
        "task_unit": _task_unit(instruction),
        "logic_profile": {
            "closure_gates": [
                {
                    "id": "verifier_reward_available",
                    "proposition": "Verifier reward artifact is present after execution.",
                    "evidence_key": "verifier.reward_available",
                    "expected": True,
                    "authority": "verifier_artifact",
                    "failure_effect": "review_blocked",
                },
                {
                    "id": "verifier_details_available",
                    "proposition": "Verifier details artifact is present after execution.",
                    "evidence_key": "verifier.details_available",
                    "expected": True,
                    "authority": "verifier_artifact",
                    "failure_effect": "review_blocked",
                },
            ],
            "construction_gates": [
                {
                    "id": "completion_claim_has_output_and_verifier_evidence",
                    "proposition": "A completion claim has output and verifier witness evidence.",
                    "construction_required": [
                        "agent.output_md",
                        "verifier.reward",
                        "verifier.details",
                    ],
                    "failure_effect": "claim_unproven",
                }
            ],
            "containment_gates": [
                {
                    "id": "verifier_artifact_disagreement",
                    "contradiction": "Verifier result and preserved artifacts appear to disagree.",
                    "when": {
                        "key": "contradictions.verifier_artifact_disagreement",
                        "exists": True,
                    },
                    "record_key": "contradictions.verifier_artifact_disagreement",
                    "required_record": [
                        "sources",
                        "affected_claims",
                        "allowed_next_actions",
                    ],
                    "failure_effect": "event_candidate",
                }
            ],
            "event_triggers": [
                {
                    "id": "reviewer_verifier_language_gap",
                    "classification": "verifier_language_gap",
                    "repair_targets": ["verifier", "world_schema", "evidence_profile"],
                }
            ],
            "agentic_review": {
                "required": True,
                "review_modes": [
                    "verifier_result",
                    "output_artifacts",
                    "trace",
                    "source_authority",
                    "rubric_scores",
                    "contradiction_ledger",
                ],
                "guidance": (
                    "Inspect verifier results, preserved artifacts, traces, source authority, "
                    "rubric evidence, and contradictions without rewriting verifier reward."
                ),
            },
        },
        "operation_profile": {
            "subset_axes": ["task_instruction", "artifact_visibility"],
            "difference_axes": ["verifier_details", "artifact_channel", "trace_channel"],
            "projection_axes": ["verifier_authority", "artifact_evidence", "trace_evidence"],
            "product_axes": ["task_family", "verifier_family", "evidence_profile"],
            "extension_policy": (
                "Promote unclassifiable reviewer findings into schema, verifier, "
                "evidence, governance, or generator repair candidates."
            ),
        },
    }


def _merge_world_payload(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge_world_payload(result[key], value)
        else:
            result[key] = value
    return result


def _read_sidecar(path: Path) -> dict[str, Any]:
    if path.suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
    else:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        msg = f"task-world sidecar must contain a mapping: {path}"
        raise RuntimeError(msg)
    if "logic_profile" not in payload and path.name.startswith("logic_profile"):
        payload = {"logic_profile": payload}
    return payload


def _task_id(task_dir: Path) -> str:
    parts = task_dir.parts
    if "tasks" in parts:
        index = len(parts) - 1 - list(reversed(parts)).index("tasks")
        return ".".join(parts[index + 1 :])
    if task_dir.parent.name:
        return f"{task_dir.parent.name}.{task_dir.name}"
    return task_dir.name


def _task_unit(instruction: str | None) -> str:
    if not instruction:
        return "Complete the benchmark task and preserve verifier-visible evidence."
    first_line = next((line.strip() for line in instruction.splitlines() if line.strip()), "")
    return first_line[:240] or "Complete the benchmark task and preserve verifier-visible evidence."


def _root_json_artifacts(workspace_dir: Path) -> dict[str, Any]:
    artifacts: dict[str, Any] = {}
    for path in sorted(workspace_dir.iterdir()):
        if not _is_root_json_artifact(path):
            continue
        artifacts[path.name] = _read_json(path)
    return artifacts


def _is_root_json_artifact(path: Path) -> bool:
    if not path.is_file() or path.suffix != ".json":
        return False
    if path.name.startswith(_ROOT_JSON_EXCLUDED_PREFIXES):
        return False
    return path.name.endswith(_ROOT_JSON_ARTIFACT_SUFFIXES)


def _directory_listing(path: Path) -> list[str]:
    if not path.exists() or not path.is_dir():
        return []
    return sorted(child.relative_to(path).as_posix() for child in path.rglob("*") if child.is_file())


def _read_json(path: Path | None) -> Any:
    if path is None or not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _read_text(path: Path | None) -> str | None:
    if path is None or not path.exists():
        return None
    return path.read_text(encoding="utf-8", errors="replace")[:_MAX_TEXT_CHARS]


def _read_text_tail(path: Path | None) -> str | None:
    if path is None or not path.exists():
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    return text[-_MAX_TEXT_CHARS:]


def _first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None
