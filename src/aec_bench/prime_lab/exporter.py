# ABOUTME: Exports selected aec-bench tasks into Prime Lab environment packages.
# ABOUTME: Generates verifiers-compatible package files while preserving task verifier assets.

from __future__ import annotations

import json
import re
import shutil
import textwrap
import tomllib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from aec_bench.prime_lab.classifier import (
    PrimeHarnessClassification,
    PrimeHarnessKind,
    classify_prime_harness,
)
from aec_bench.tasks.loader import load_task_definition

DEFAULT_PRIME_ENVIRONMENTS_DIR = Path("prime-rl/environments")


class PrimeExportHarnessMode(StrEnum):
    AUTO = "auto"
    SINGLE_TURN = "single_turn"
    STATEFUL_WORKSPACE = "stateful_workspace"


@dataclass(frozen=True)
class PrimeLabExportConfig:
    name: str
    tasks_root: Path
    task_ids: list[str]
    output_dir: Path = DEFAULT_PRIME_ENVIRONMENTS_DIR
    version: str = "0.1.0"
    description: str | None = None
    harness_mode: PrimeExportHarnessMode = PrimeExportHarnessMode.AUTO
    dataset_metadata: dict[str, str] | None = None


@dataclass(frozen=True)
class PrimeLabExportResult:
    package_dir: Path
    task_count: int


def export_prime_lab_environment(config: PrimeLabExportConfig) -> PrimeLabExportResult:
    """Create a Prime Lab environment package from selected task IDs."""
    package_name = normalise_environment_id(config.name)
    package_dir = config.output_dir / package_name
    package_module = package_dir / package_name
    tasks_dir = package_module / "tasks"

    if not config.task_ids:
        raise ValueError("at least one task_id is required")

    if package_dir.exists():
        shutil.rmtree(package_dir)
    tasks_dir.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, Any]] = []
    for task_id in sorted(config.task_ids):
        source_dir = (config.tasks_root / task_id).resolve()
        if not source_dir.exists():
            raise FileNotFoundError(f"task not found: {task_id}")

        task_def = load_task_definition(source_dir, config.tasks_root)
        harness = _resolve_harness_classification(config.harness_mode, task_def, source_dir)
        raw_toml = tomllib.loads((source_dir / "task.toml").read_text(encoding="utf-8"))
        verifier_timeout = int(raw_toml.get("verifier", {}).get("timeout_sec", 120))
        rollout_limits = _load_rollout_limits(source_dir, harness.kind)
        relative_dest = Path(*task_id.split("/"))
        shutil.copytree(
            source_dir,
            tasks_dir / relative_dest,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"),
        )
        _prepare_task_environment_files(tasks_dir / relative_dest)
        record = {
            "task_id": task_def.task_id,
            "domain": task_def.domain,
            "difficulty": task_def.difficulty.value,
            "tags": task_def.tags,
            "instruction": task_def.instruction,
            "verifier_timeout_seconds": verifier_timeout,
            "harness_kind": harness.kind.value,
            "harness_reasons": harness.reasons,
            "rollout_limits": rollout_limits,
        }
        if config.dataset_metadata is not None:
            record["dataset"] = config.dataset_metadata
        records.append(record)

    (package_module / "__init__.py").write_text(
        "\n".join(
            [
                f"from {package_name}.environment import load_environment",
                "",
                '__all__ = ["load_environment"]',
                "",
            ]
        ),
        encoding="utf-8",
    )
    (package_module / "environment.py").write_text(
        _render_environment_py(records),
        encoding="utf-8",
    )
    (package_dir / "pyproject.toml").write_text(
        _render_pyproject(package_name, config.version, config.description),
        encoding="utf-8",
    )
    (package_dir / "README.md").write_text(
        _render_readme(package_name, records),
        encoding="utf-8",
    )

    return PrimeLabExportResult(package_dir=package_dir, task_count=len(records))


def _resolve_harness_classification(
    mode: PrimeExportHarnessMode,
    task_def: Any,
    source_dir: Path,
) -> PrimeHarnessClassification:
    if mode is PrimeExportHarnessMode.AUTO:
        return classify_prime_harness(task_def, source_dir)
    if mode is PrimeExportHarnessMode.SINGLE_TURN:
        return PrimeHarnessClassification(
            kind=PrimeHarnessKind.SINGLE_TURN,
            reasons=["forced by export harness mode"],
        )
    if mode is PrimeExportHarnessMode.STATEFUL_WORKSPACE:
        return PrimeHarnessClassification(
            kind=PrimeHarnessKind.STATEFUL_WORKSPACE,
            reasons=["forced by export harness mode"],
        )
    raise ValueError(f"unsupported Prime harness mode: {mode}")


def _load_rollout_limits(task_dir: Path, harness_kind: PrimeHarnessKind) -> dict[str, int]:
    policy_path = _rollout_policy_path(task_dir, harness_kind)
    if policy_path is None:
        return {}

    raw_policy = tomllib.loads(policy_path.read_text(encoding="utf-8"))
    guardrails = raw_policy.get("guardrails", {})
    limits: dict[str, int] = {}
    max_iterations = _positive_int(guardrails.get("max_iterations"))
    token_budget = _positive_int(guardrails.get("token_budget"))
    if max_iterations is not None:
        limits["max_turns"] = max_iterations
    if token_budget is not None:
        limits["token_budget"] = token_budget
    return limits


def _rollout_policy_path(task_dir: Path, harness_kind: PrimeHarnessKind) -> Path | None:
    if harness_kind is PrimeHarnessKind.LAMBDA_RLM_POLICY:
        return task_dir / "lambda-rlm.toml"
    if harness_kind is PrimeHarnessKind.RLM_POLICY:
        return task_dir / "rlm.toml"
    return None


def _positive_int(value: object) -> int | None:
    if not isinstance(value, int) or isinstance(value, bool):
        return None
    if value <= 0:
        return None
    return value


def _prepare_task_environment_files(task_dir: Path) -> None:
    environment_dir = task_dir / "environment"
    if not environment_dir.is_dir():
        return
    for helper in environment_dir.rglob("*.py"):
        source = helper.read_text(encoding="utf-8")
        sanitized = _escape_argparse_help_percent_literals(source)
        if sanitized != source:
            helper.write_text(sanitized, encoding="utf-8")


def _escape_argparse_help_percent_literals(source: str) -> str:
    lines = []
    for line in source.splitlines(keepends=True):
        if "parser.add_argument" not in line or "help=" not in line or "%" not in line:
            lines.append(line)
            continue
        lines.append(_escape_argparse_help_percent_literals_in_line(line))
    return "".join(lines)


def _escape_argparse_help_percent_literals_in_line(line: str) -> str:
    help_index = line.find("help=")
    if help_index < 0:
        return line
    literal_start = help_index + len("help=")
    while literal_start < len(line) and line[literal_start].isspace():
        literal_start += 1
    if literal_start >= len(line) or line[literal_start] not in {"'", '"'}:
        return line

    quote = line[literal_start]
    literal_end = literal_start + 1
    escaped = False
    while literal_end < len(line):
        char = line[literal_end]
        if char == "\\" and not escaped:
            escaped = True
            literal_end += 1
            continue
        if char == quote and not escaped:
            break
        escaped = False
        literal_end += 1
    if literal_end >= len(line):
        return line

    raw_value = line[literal_start + 1 : literal_end]
    escaped_value = _escape_argparse_percent_literals(raw_value)
    return line[: literal_start + 1] + escaped_value + line[literal_end:]


def _escape_argparse_percent_literals(value: str) -> str:
    pieces: list[str] = []
    index = 0
    while index < len(value):
        char = value[index]
        if char != "%":
            pieces.append(char)
            index += 1
            continue
        next_char = value[index + 1] if index + 1 < len(value) else ""
        if next_char == "%":
            pieces.append("%%")
            index += 2
            continue
        if next_char == "(":
            pieces.append("%")
            index += 1
            continue
        pieces.append("%%")
        index += 1
    return "".join(pieces)


def normalise_environment_id(name: str) -> str:
    """Convert a display name into a Prime/verifiers-compatible env id."""
    package_name = re.sub(r"[^A-Za-z0-9_]+", "_", name.strip().replace("-", "_")).strip("_")
    if not package_name:
        raise ValueError("package name cannot be empty")
    if package_name[0].isdigit():
        package_name = f"aec_{package_name}"
    return package_name


def _render_pyproject(name: str, version: str, description: str | None) -> str:
    package_description = description or "AEC-Bench tasks exported as a Prime Lab environment"
    return textwrap.dedent(
        f"""\
        [project]
        name = "{name}"
        version = "{version}"
        description = "{package_description}"
        readme = "README.md"
        requires-python = ">=3.10"
        tags = ["aec-bench", "aec", "benchmark"]
        dependencies = ["datasets>=4.0", "verifiers>=0.1.10"]

        [build-system]
        requires = ["hatchling"]
        build-backend = "hatchling.build"

        [tool.hatch.build.targets.wheel]
        packages = ["{name}"]

        [tool.hatch.build.targets.wheel.force-include]
        "{name}/tasks" = "{name}/tasks"
        """
    )


def _render_readme(name: str, records: list[dict[str, Any]]) -> str:
    task_lines = "\n".join(f"- `{record['task_id']}`" for record in records)
    if _requires_stateful_workspace(records):
        environment_summary = (
            "It exposes selected aec-bench tasks as a `verifiers.StatefulToolEnv`. "
            "Each rollout receives workspace tools, can inspect or write files inside "
            "a rollout-local task workspace, and scores `output.md` with the original "
            "task `tests/verify.py` script."
        )
    else:
        environment_summary = (
            "It exposes selected aec-bench tasks as a `verifiers.SingleTurnEnv`. "
            "Each rollout sends the task instruction as the prompt, writes the model "
            "completion to a temporary `output.md`, and scores it with the original "
            "task `tests/verify.py` script."
        )
    return textwrap.dedent(
        f"""\
        # {name}

        This Prime Lab environment was exported from aec-bench.

        {environment_summary}

        ## Tasks

        {task_lines}

        ## Local smoke test

        ```bash
        uv pip install -e .
        uv run vf-eval {name}
        ```

        ## Prime Lab

        ```bash
        prime env install {name} --path prime-rl/environments
        prime env push
        prime eval run <owner>/{name} -m <model> -n 20 -r 1 --max-tokens 2048
        prime train run configs/lab/{name}.toml
        ```
        """
    )


def _render_environment_py(records: list[dict[str, Any]]) -> str:
    if _requires_stateful_workspace(records):
        return _render_stateful_environment_py(records)
    return _render_single_turn_environment_py(records)


def _requires_stateful_workspace(records: list[dict[str, Any]]) -> bool:
    stateful_kinds = {
        PrimeHarnessKind.STATEFUL_WORKSPACE.value,
        PrimeHarnessKind.RLM_POLICY.value,
        PrimeHarnessKind.LAMBDA_RLM_POLICY.value,
    }
    return any(record.get("harness_kind") in stateful_kinds for record in records)


def _render_single_turn_environment_py(records: list[dict[str, Any]]) -> str:
    task_json = json.dumps(records, indent=2)
    return f"""# ABOUTME: Prime Lab environment generated from selected aec-bench tasks.
# ABOUTME: Loads task prompts and scores completions via bundled aec-bench verifiers.

from __future__ import annotations

import json
import random
import shutil
import subprocess
import sys
import tempfile
from importlib.resources import files
from pathlib import Path
from typing import Any

import verifiers as vf
from datasets import Dataset

TASKS = {task_json}


def load_environment(
    split: str = "train",
    difficulty: str | list[str] | None = None,
    num_examples: int | None = None,
    seed: int | None = None,
    harness: str | None = None,
) -> vf.Environment:
    del harness
    tasks = _select_tasks(
        split=split,
        difficulty=difficulty,
        num_examples=num_examples,
        seed=seed,
    )
    dataset = _dataset_from_tasks(tasks, workspace=False)
    rubric = vf.Rubric(funcs=[aec_bench_reward])
    return vf.SingleTurnEnv(dataset=dataset, eval_dataset=dataset, rubric=rubric)


def _select_tasks(
    split: str,
    difficulty: str | list[str] | None,
    num_examples: int | None,
    seed: int | None,
) -> list[dict[str, Any]]:
    selected = list(TASKS)
    if difficulty is not None:
        allowed = {{difficulty}} if isinstance(difficulty, str) else set(difficulty)
        selected = [task for task in selected if task.get("difficulty") in allowed]
    selected = _split_tasks(selected, split)
    if seed is not None:
        rng = random.Random(seed)
        rng.shuffle(selected)
    if num_examples is not None and num_examples >= 0:
        selected = selected[:num_examples]
    return selected


def _split_tasks(tasks: list[dict[str, Any]], split: str) -> list[dict[str, Any]]:
    normalized = (split or "train").strip().lower().replace("_", "-")
    if normalized in {{"all", "any", "full"}}:
        return list(tasks)
    if len(tasks) < 5:
        return list(tasks)
    boundary = max(1, min(len(tasks) - 1, int(len(tasks) * 0.8)))
    if normalized == "train":
        return list(tasks[:boundary])
    if normalized in {{"eval", "validation", "val", "test"}}:
        return list(tasks[boundary:])
    raise ValueError(f"unsupported split: {{split}}")


def _dataset_from_tasks(tasks: list[dict[str, Any]], *, workspace: bool) -> Dataset:
    def _prompt_content(task: dict[str, Any]) -> str:
        if workspace:
            return _workspace_instruction(task)
        return task["instruction"]

    return Dataset.from_list(
        [
            {{
                "prompt": [
                    {{
                        "role": "user",
                        "content": _prompt_content(task),
                    }}
                ],
                "answer": task["task_id"],
                "info": json.dumps(task),
            }}
            for task in tasks
        ]
    )


async def aec_bench_reward(
    completion: list[dict[str, Any]], info: dict[str, Any] | str
) -> float:
    task_info = json.loads(info) if isinstance(info, str) else info
    response = _completion_text(completion)
    task_id = task_info["task_id"]
    timeout_seconds = int(task_info.get("verifier_timeout_seconds", 120))

    task_resource = files(__package__).joinpath("tasks", *task_id.split("/"))
    with tempfile.TemporaryDirectory(prefix="aec-prime-") as temp_dir:
        temp_path = Path(temp_dir)
        task_dir = temp_path / "task"
        workspace = temp_path / "workspace"
        _copy_resource_tree(task_resource, task_dir)
        shutil.copytree(task_dir, workspace)

        output_path = workspace / "output.md"
        reward_path = temp_path / "reward.json"
        output_path.write_text(response, encoding="utf-8")

        verifier = workspace / "tests" / "verify.py"
        if not verifier.exists():
            return 0.0

        process = subprocess.run(
            [
                sys.executable,
                str(verifier),
                "--input",
                str(output_path),
                "--output",
                str(reward_path),
            ],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        if process.returncode != 0 or not reward_path.exists():
            return 0.0
        payload = json.loads(reward_path.read_text(encoding="utf-8"))
        return float(payload.get("reward", 0.0))


def _completion_text(completion: list[dict[str, Any]]) -> str:
    if not completion:
        return ""
    content = completion[-1].get("content", "")
    if isinstance(content, str):
        return content
    return json.dumps(content)


def _workspace_instruction(task: dict[str, Any]) -> str:
    return task["instruction"]


def _copy_resource_tree(source: Any, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for child in source.iterdir():
        child_destination = destination / child.name
        if child.is_dir():
            _copy_resource_tree(child, child_destination)
        else:
            child_destination.write_bytes(child.read_bytes())
"""


def _render_stateful_environment_py(records: list[dict[str, Any]]) -> str:
    task_json = json.dumps(records, indent=2)
    return f"""# ABOUTME: Prime Lab stateful environment generated from selected aec-bench tasks.
# ABOUTME: Provides rollout-local workspace tools and scores with bundled verifiers.

from __future__ import annotations

import json
import random
import shlex
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any

import verifiers as vf
from datasets import Dataset

TASKS = {task_json}


@dataclass(frozen=True)
class WorkspaceCommandResult:
    exit_code: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class WorkspaceCommandSet:
    root: Path
    max_output_chars: int = 20_000
    timeout_seconds: int = 30

    def read_file(self, path: str) -> str:
        return self._resolve(path).read_text(encoding="utf-8")

    def write_file(self, path: str, content: str) -> str:
        target = self._resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target.relative_to(self._root()).as_posix()

    def list_files(self, path: str = ".") -> list[str]:
        base = self._resolve(path)
        if base.is_file():
            return [base.relative_to(self._root()).as_posix()]
        return sorted(
            child.relative_to(self._root()).as_posix()
            for child in base.rglob("*")
            if child.is_file()
        )

    def run_command(
        self,
        command: str | list[str],
        cwd: str | None = None,
    ) -> WorkspaceCommandResult:
        if not command:
            raise ValueError("command cannot be empty")
        command_args = _workspace_command_args(command, self._root())
        run_cwd = self._resolve(cwd or ".")
        process = subprocess.run(
            command_args,
            cwd=run_cwd,
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
            check=False,
        )
        return WorkspaceCommandResult(
            exit_code=process.returncode,
            stdout=self._truncate(process.stdout),
            stderr=self._truncate(process.stderr),
        )

    def submit_answer(self, content: str, path: str = "output.md") -> str:
        return self.write_file(path, content)

    def _root(self) -> Path:
        root = self.root.resolve()
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _resolve(self, path: str) -> Path:
        root = self._root()
        candidate = (root / _workspace_relative_path(path)).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"path is outside workspace: {{path}}") from exc
        return candidate

    def _truncate(self, text: str) -> str:
        if len(text) <= self.max_output_chars:
            return text
        return text[: self.max_output_chars] + "\\n...[truncated]"


def _workspace_relative_path(path: str) -> str:
    if path == "/workspace":
        return "."
    if path.startswith("/workspace/"):
        return path.removeprefix("/workspace/")
    return path


def _workspace_command_args(command: str | list[str], root: Path) -> list[str]:
    raw_args = shlex.split(command) if isinstance(command, str) else command
    return [_workspace_command_arg(arg, root) for arg in raw_args]


def _workspace_command_arg(arg: str, root: Path) -> str:
    if arg == "/workspace":
        return str(root)
    if arg.startswith("/workspace/"):
        return str((root / arg.removeprefix("/workspace/")).resolve())
    return arg


def _expose_environment_files(workspace: Path) -> None:
    environment_dir = workspace / "environment"
    if not environment_dir.is_dir():
        return
    for source in environment_dir.iterdir():
        target = workspace / source.name
        if target.exists():
            continue
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)


def read_file(path: str, workspace: WorkspaceCommandSet) -> str:
    \"\"\"Read a UTF-8 text file from the rollout workspace.\"\"\"
    return workspace.read_file(path)


def write_file(
    path: str,
    content: str,
    workspace: WorkspaceCommandSet,
) -> str:
    \"\"\"Write a UTF-8 text file inside the rollout workspace.\"\"\"
    return workspace.write_file(path, content)


def list_files(path: str = ".", workspace: WorkspaceCommandSet | None = None) -> list[str]:
    \"\"\"List files below a workspace path.\"\"\"
    assert workspace is not None
    return workspace.list_files(path)


def run_command(
    command: str | list[str], workspace: WorkspaceCommandSet, cwd: str | None = None
) -> dict[str, str | int]:
    \"\"\"Run a shell-style string or argument-vector command inside the rollout workspace.\"\"\"
    result = workspace.run_command(command, cwd=cwd)
    return {{"exit_code": result.exit_code, "stdout": result.stdout, "stderr": result.stderr}}


def submit_answer(
    content: str,
    workspace: WorkspaceCommandSet,
    state: dict[str, Any],
    path: str = "output.md",
) -> str:
    \"\"\"Submit the final answer file for verifier scoring.\"\"\"
    written_path = workspace.submit_answer(content, path=path)
    state["final_env_response"] = [
        _user_message(f"Submitted final answer to {{written_path}}.")
    ]
    return f"submitted {{written_path}}"


def _user_message(content: str) -> Any:
    user_message = getattr(vf, "UserMessage", None)
    if user_message is not None:
        return user_message(content=content)
    return {{"role": "user", "content": content}}


class AecBenchStatefulWorkspaceEnv(vf.StatefulToolEnv):
    def __init__(self, tasks: list[dict[str, Any]], **kwargs: Any) -> None:
        super().__init__(tools=[], max_turns=_environment_max_turns(tasks), **kwargs)
        self.add_tool(read_file, args_to_skip=["workspace"])
        self.add_tool(write_file, args_to_skip=["workspace"])
        self.add_tool(list_files, args_to_skip=["workspace"])
        self.add_tool(run_command, args_to_skip=["workspace"])
        self.add_tool(submit_answer, args_to_skip=["workspace", "state"])

    async def setup_state(self, state: vf.State) -> vf.State:
        info = state.get("info", {{}})
        task_id = info["task_id"]
        tempdir = tempfile.TemporaryDirectory(prefix="aec-prime-stateful-")
        workspace = Path(tempdir.name) / "workspace"
        task_resource = files(__package__).joinpath("tasks", *task_id.split("/"))
        _copy_resource_tree(task_resource, workspace)
        _expose_environment_files(workspace)
        state["aec_tempdir"] = tempdir
        state["workspace_path"] = str(workspace)
        state["workspace"] = WorkspaceCommandSet(workspace)
        return state

    def update_tool_args(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        messages: vf.Messages,
        state: vf.State,
        **kwargs: Any,
    ) -> dict[str, Any]:
        del messages, kwargs
        tool_args["workspace"] = state["workspace"]
        if "state" in self.skipped_args.get(tool_name, []):
            tool_args["state"] = state
        return tool_args

def load_environment(
    split: str = "train",
    difficulty: str | list[str] | None = None,
    num_examples: int | None = None,
    seed: int | None = None,
    harness: str | None = None,
) -> vf.Environment:
    del harness
    tasks = _select_tasks(
        split=split,
        difficulty=difficulty,
        num_examples=num_examples,
        seed=seed,
    )
    dataset = _dataset_from_tasks(tasks, workspace=True)
    rubric = vf.Rubric(funcs=[aec_bench_reward])
    return AecBenchStatefulWorkspaceEnv(
        tasks=tasks,
        dataset=dataset,
        eval_dataset=dataset,
        rubric=rubric,
    )


def _select_tasks(
    split: str,
    difficulty: str | list[str] | None,
    num_examples: int | None,
    seed: int | None,
) -> list[dict[str, Any]]:
    selected = list(TASKS)
    if difficulty is not None:
        allowed = {{difficulty}} if isinstance(difficulty, str) else set(difficulty)
        selected = [task for task in selected if task.get("difficulty") in allowed]
    selected = _split_tasks(selected, split)
    if seed is not None:
        rng = random.Random(seed)
        rng.shuffle(selected)
    if num_examples is not None and num_examples >= 0:
        selected = selected[:num_examples]
    return selected


def _split_tasks(tasks: list[dict[str, Any]], split: str) -> list[dict[str, Any]]:
    normalized = (split or "train").strip().lower().replace("_", "-")
    if normalized in {{"all", "any", "full"}}:
        return list(tasks)
    if len(tasks) < 5:
        return list(tasks)
    boundary = max(1, min(len(tasks) - 1, int(len(tasks) * 0.8)))
    if normalized == "train":
        return list(tasks[:boundary])
    if normalized in {{"eval", "validation", "val", "test"}}:
        return list(tasks[boundary:])
    raise ValueError(f"unsupported split: {{split}}")


def _dataset_from_tasks(tasks: list[dict[str, Any]], *, workspace: bool) -> Dataset:
    def _prompt_content(task: dict[str, Any]) -> str:
        if workspace:
            return _workspace_instruction(task)
        return task["instruction"]

    return Dataset.from_list(
        [
            {{
                "prompt": [
                    {{
                        "role": "user",
                        "content": _prompt_content(task),
                    }}
                ],
                "answer": task["task_id"],
                "info": json.dumps(task),
            }}
            for task in tasks
        ]
    )


def _environment_max_turns(tasks: list[dict[str, Any]]) -> int:
    return max(
        [
            int(task.get("rollout_limits", {{}}).get("max_turns", 10))
            for task in tasks
        ],
        default=10,
    )


def _workspace_instruction(task: dict[str, Any]) -> str:
    instruction = task["instruction"]
    limits = task.get("rollout_limits", {{}})
    limit_note = ""
    if limits:
        limit_bits = []
        if "max_turns" in limits:
            limit_bits.append(f"max tool turns: {{limits['max_turns']}}")
        if "token_budget" in limits:
            limit_bits.append(f"source token budget: {{limits['token_budget']}}")
        limit_note = " Source policy guardrails: " + ", ".join(limit_bits) + "."
    return (
        instruction.rstrip()
        + "\\n\\n"
        + "Prime Lab workspace tools are available. Use read_file/list_files/run_command "
        + "when inspection or computation is useful. Use write_file for drafts or supporting "
        + "files only. run_command command accepts either a JSON list of argv strings, such "
        + "as [\\\"python3\\\", \\\"/workspace/helper.py\\\"], or a shell-style string. Files "
        + "from /workspace/environment are also exposed at /workspace for task prompts that "
        + "reference helper scripts directly. When the final solution is complete, call "
        + "submit_answer with the full contents for output.md; submit_answer ends the rollout "
        + "and sends the file to the aec-bench verifier."
        + limit_note
    )


async def aec_bench_reward(
    completion: list[dict[str, Any]],
    info: dict[str, Any] | str,
    state: vf.State | None = None,
) -> float:
    task_info = json.loads(info) if isinstance(info, str) else info
    timeout_seconds = int(task_info.get("verifier_timeout_seconds", 120))

    if state is not None and state.get("workspace_path"):
        workspace = Path(state["workspace_path"])
        tempdir = state.get("aec_tempdir")
        try:
            output_path = workspace / "output.md"
            if not output_path.exists():
                output_path.write_text(_completion_text(completion), encoding="utf-8")
            return _score_workspace(workspace, timeout_seconds)
        finally:
            if tempdir is not None:
                tempdir.cleanup()

    response = _completion_text(completion)
    task_id = task_info["task_id"]
    task_resource = files(__package__).joinpath("tasks", *task_id.split("/"))
    with tempfile.TemporaryDirectory(prefix="aec-prime-") as temp_dir:
        temp_path = Path(temp_dir)
        workspace = temp_path / "workspace"
        _copy_resource_tree(task_resource, workspace)
        (workspace / "output.md").write_text(response, encoding="utf-8")
        return _score_workspace(workspace, timeout_seconds)


def _score_workspace(workspace: Path, timeout_seconds: int) -> float:
    reward_path = workspace.parent / "reward.json"
    verifier = workspace / "tests" / "verify.py"
    if not verifier.exists():
        return 0.0
    process = subprocess.run(
        [
            sys.executable,
            str(verifier),
            "--input",
            str(workspace / "output.md"),
            "--output",
            str(reward_path),
        ],
        cwd=workspace,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    if process.returncode != 0 or not reward_path.exists():
        return 0.0
    payload = json.loads(reward_path.read_text(encoding="utf-8"))
    return float(payload.get("reward", 0.0))


def _completion_text(completion: list[dict[str, Any]]) -> str:
    if not completion:
        return ""
    content = completion[-1].get("content", "")
    if isinstance(content, str):
        return content
    return json.dumps(content)


def _copy_resource_tree(source: Any, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for child in source.iterdir():
        child_destination = destination / child.name
        if child.is_dir():
            _copy_resource_tree(child, child_destination)
        else:
            child_destination.write_bytes(child.read_bytes())
"""
