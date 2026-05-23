# ABOUTME: Task validation engine for aec-bench task directories.
# ABOUTME: Runs structural, schema, instruction, promotion, and verifier fixture checks.

import json
import re
import subprocess
import tempfile
import tomllib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class ValidationFinding:
    severity: Severity
    check: str
    file: str
    message: str
    fix_hint: str

    def to_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity,
            "check": self.check,
            "file": self.file,
            "message": self.message,
            "fix_hint": self.fix_hint,
        }


@dataclass(frozen=True)
class ValidationReport:
    task_id: str
    findings: list[ValidationFinding]

    @property
    def passed(self) -> bool:
        return self.error_count == 0

    @property
    def error_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.WARNING)

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "passed": self.passed,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "findings": [f.to_dict() for f in self.findings],
        }


_VALID_DIFFICULTIES = {"easy", "medium", "hard"}
_PLACEHOLDER_RE = re.compile(r"\{\{[^}]+\}\}")
_WORKSPACE_RE = re.compile(r"/workspace/")


def _check_structure(task_dir: Path) -> list[ValidationFinding]:
    """Check that mandatory files are present and non-empty."""
    findings: list[ValidationFinding] = []

    # task.toml must exist
    task_toml = task_dir / "task.toml"
    if not task_toml.exists():
        findings.append(
            ValidationFinding(
                severity=Severity.ERROR,
                check="structure",
                file="task.toml",
                message="task.toml is missing",
                fix_hint=("Create a task.toml file with version, metadata, agent, verifier, and environment sections."),
            )
        )

    # instruction.md must exist and be non-empty
    instruction_md = task_dir / "instruction.md"
    if not instruction_md.exists():
        findings.append(
            ValidationFinding(
                severity=Severity.ERROR,
                check="structure",
                file="instruction.md",
                message="instruction.md is missing",
                fix_hint="Create an instruction.md file with the task description for the agent.",
            )
        )
    elif not instruction_md.read_text(encoding="utf-8").strip():
        findings.append(
            ValidationFinding(
                severity=Severity.ERROR,
                check="structure",
                file="instruction.md",
                message="instruction.md is empty",
                fix_hint="Add the task description to instruction.md.",
            )
        )

    # tests/verify.py or tests/test.sh must exist
    verify_py = task_dir / "tests" / "verify.py"
    test_sh = task_dir / "tests" / "test.sh"
    has_verify_py = verify_py.exists()
    has_test_sh = test_sh.exists()

    if not has_verify_py and not has_test_sh:
        findings.append(
            ValidationFinding(
                severity=Severity.ERROR,
                check="structure",
                file="tests/",
                message="No verifier found: tests/verify.py and tests/test.sh are both missing",
                fix_hint=("Create tests/verify.py to score agent output and tests/test.sh to invoke it."),
            )
        )
    elif has_verify_py and not has_test_sh:
        findings.append(
            ValidationFinding(
                severity=Severity.WARNING,
                check="structure",
                file="tests/test.sh",
                message="tests/test.sh is missing — Harbor requires a shell entry point",
                fix_hint="Add tests/test.sh that calls python3 /tests/verify.py.",
            )
        )

    return findings


def _check_schema(task_dir: Path) -> list[ValidationFinding]:
    """Parse task.toml and validate required fields."""
    findings: list[ValidationFinding] = []

    task_toml = task_dir / "task.toml"
    if not task_toml.exists():
        # Structure check already reports this — skip schema checks
        return findings

    try:
        raw = tomllib.loads(task_toml.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        findings.append(
            ValidationFinding(
                severity=Severity.ERROR,
                check="schema",
                file="task.toml",
                message=f"task.toml is not valid TOML: {exc}",
                fix_hint="Fix the TOML syntax error in task.toml.",
            )
        )
        return findings

    metadata = raw.get("metadata", {})

    # difficulty must be easy/medium/hard
    difficulty = metadata.get("difficulty", "")
    if difficulty not in _VALID_DIFFICULTIES:
        findings.append(
            ValidationFinding(
                severity=Severity.ERROR,
                check="schema",
                file="task.toml",
                message=f"Invalid difficulty '{difficulty}' — must be one of: easy, medium, hard",
                fix_hint="Set metadata.difficulty to easy, medium, or hard in task.toml.",
            )
        )

    # tags should exist (non-empty list)
    tags = metadata.get("tags")
    if not tags:
        findings.append(
            ValidationFinding(
                severity=Severity.WARNING,
                check="schema",
                file="task.toml",
                message="metadata.tags is empty or missing — tasks should have at least one tag",
                fix_hint=('Add a tags list under [metadata] in task.toml, e.g. tags = ["electrical"].'),
            )
        )

    # category should exist
    category = metadata.get("category")
    if not category:
        findings.append(
            ValidationFinding(
                severity=Severity.INFO,
                check="schema",
                file="task.toml",
                message="metadata.category is missing",
                fix_hint="",
            )
        )

    return findings


def _check_instruction(task_dir: Path) -> list[ValidationFinding]:
    """Check instruction.md content for unresolved placeholders and workspace references."""
    findings: list[ValidationFinding] = []

    instruction_md = task_dir / "instruction.md"
    if not instruction_md.exists():
        return findings

    text = instruction_md.read_text(encoding="utf-8")

    # No unresolved {{ ... }} placeholders
    placeholders = _PLACEHOLDER_RE.findall(text)
    if placeholders:
        unique = sorted(set(placeholders))
        findings.append(
            ValidationFinding(
                severity=Severity.ERROR,
                check="instruction",
                file="instruction.md",
                message=f"Unresolved template placeholders: {', '.join(unique)}",
                fix_hint=("Replace all {{ ... }} placeholders with concrete values before committing this task."),
            )
        )

    # Should reference /workspace/ output path
    if not _WORKSPACE_RE.search(text):
        findings.append(
            ValidationFinding(
                severity=Severity.WARNING,
                check="instruction",
                file="instruction.md",
                message="instruction.md does not reference a /workspace/ output path",
                fix_hint=("Add an explicit output path such as /workspace/output.md to the instruction."),
            )
        )

    return findings


def _check_promotion(task_dir: Path) -> list[ValidationFinding]:
    """Check environment assets needed for promotion to active use."""
    findings: list[ValidationFinding] = []

    dockerfile = task_dir / "environment" / "Dockerfile"
    if not dockerfile.exists():
        findings.append(
            ValidationFinding(
                severity=Severity.WARNING,
                check="promotion",
                file="environment/Dockerfile",
                message="environment/Dockerfile is missing",
                fix_hint=(
                    "Add environment/Dockerfile or run `aec-bench generate dockerfiles` "
                    "to generate it from the extensions declared in task.toml."
                ),
            )
        )

    return findings


def _check_verifier_fixtures(task_dir: Path) -> list[ValidationFinding]:
    """Run verify.py against golden fixture files if they exist."""
    findings: list[ValidationFinding] = []

    verify_py = task_dir / "tests" / "verify.py"
    if not verify_py.exists():
        return findings

    fixtures_dir = task_dir / "tests" / "fixtures"

    golden_pass = fixtures_dir / "golden_pass.md"
    if golden_pass.exists():
        score, run_error = _run_verifier(verify_py, golden_pass)
        if run_error:
            findings.append(
                ValidationFinding(
                    severity=Severity.ERROR,
                    check="verifier",
                    file="tests/verify.py",
                    message=f"Verifier crashed on golden_pass.md: {run_error}",
                    fix_hint=("Fix tests/verify.py so it runs without errors against the golden pass fixture."),
                )
            )
        elif score is None:
            findings.append(
                ValidationFinding(
                    severity=Severity.ERROR,
                    check="verifier",
                    file="tests/verify.py",
                    message="Verifier did not produce a valid reward.json for golden_pass.md",
                    fix_hint=('Ensure verify.py writes {"reward": <float>} to the path given by --output.'),
                )
            )
        elif score < 0.95:
            findings.append(
                ValidationFinding(
                    severity=Severity.ERROR,
                    check="golden_pass",
                    file="tests/fixtures/golden_pass.md",
                    message=f"golden_pass.md scored {score:.3f} — expected >= 0.95",
                    fix_hint=(
                        "The golden pass fixture should score >= 0.95. "
                        "Either improve golden_pass.md or fix the verifier scoring logic."
                    ),
                )
            )
        else:
            findings.append(
                ValidationFinding(
                    severity=Severity.INFO,
                    check="golden_pass",
                    file="tests/fixtures/golden_pass.md",
                    message=f"golden_pass.md scored {score:.3f} (>= 0.95)",
                    fix_hint="",
                )
            )

    golden_fail = fixtures_dir / "golden_fail.md"
    if golden_fail.exists():
        score, run_error = _run_verifier(verify_py, golden_fail)
        if run_error:
            findings.append(
                ValidationFinding(
                    severity=Severity.ERROR,
                    check="verifier",
                    file="tests/verify.py",
                    message=f"Verifier crashed on golden_fail.md: {run_error}",
                    fix_hint=("Fix tests/verify.py so it runs without errors against the golden fail fixture."),
                )
            )
        elif score is None:
            findings.append(
                ValidationFinding(
                    severity=Severity.ERROR,
                    check="verifier",
                    file="tests/verify.py",
                    message="Verifier did not produce a valid reward.json for golden_fail.md",
                    fix_hint=('Ensure verify.py writes {"reward": <float>} to the path given by --output.'),
                )
            )
        elif score > 0.5:
            findings.append(
                ValidationFinding(
                    severity=Severity.ERROR,
                    check="golden_fail",
                    file="tests/fixtures/golden_fail.md",
                    message=(f"golden_fail.md scored {score:.3f} — expected <= 0.5 (verifier is too lenient)"),
                    fix_hint=(
                        "The golden fail fixture should score <= 0.5. "
                        "Either improve golden_fail.md or tighten the verifier scoring logic."
                    ),
                )
            )
        else:
            findings.append(
                ValidationFinding(
                    severity=Severity.INFO,
                    check="golden_fail",
                    file="tests/fixtures/golden_fail.md",
                    message=f"golden_fail.md scored {score:.3f} (<= 0.5)",
                    fix_hint="",
                )
            )

    return findings


def _run_verifier(verify_py: Path, input_file: Path) -> tuple[float | None, str | None]:
    """Run verify.py against input_file and return (score, error_message)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        reward_path = Path(tmpdir) / "reward.json"
        try:
            result = subprocess.run(
                [
                    "python3",
                    str(verify_py),
                    "--input",
                    str(input_file),
                    "--output",
                    str(reward_path),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            return None, "Verifier timed out after 30 seconds"
        except Exception as exc:
            return None, str(exc)

        if result.returncode != 0:
            stderr_snippet = result.stderr[:200] if result.stderr else "(no stderr)"
            return None, f"exit code {result.returncode}: {stderr_snippet}"

        if not reward_path.exists():
            return None, None

        try:
            reward_data = json.loads(reward_path.read_text(encoding="utf-8"))
            score = float(reward_data["reward"])
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return None, None

    return score, None


def validate_task(task_dir: Path, *, tasks_root: Path) -> ValidationReport:
    """Run all validation checks on a task directory and return a ValidationReport."""
    task_id = task_dir.relative_to(tasks_root).as_posix()

    findings: list[ValidationFinding] = []
    findings.extend(_check_structure(task_dir))
    findings.extend(_check_schema(task_dir))
    findings.extend(_check_instruction(task_dir))
    findings.extend(_check_promotion(task_dir))
    findings.extend(_check_verifier_fixtures(task_dir))

    return ValidationReport(task_id=task_id, findings=findings)
