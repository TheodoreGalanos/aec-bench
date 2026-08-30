# ABOUTME: Workspace class providing typed read/write access to an evolvable agent workspace.
# ABOUTME: Manages prompts, skills (SKILL.md format), snapshots, and git-based versioning.

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import cast

import yaml

from aec_bench.contracts.evolution import (
    SkillEntry,
    WorkspaceCandidateVersion,
    WorkspaceManifest,
    WorkspaceSnapshot,
)

# Regex for YAML frontmatter at the top of a SKILL.md file.
_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
_CANDIDATE_NOTES_REF = "aec-bench-evolution"


class WorkspaceError(Exception):
    """Raised when the workspace is invalid or a filesystem/git operation fails."""


@contextmanager
def scratch_workspace_from(
    source: Workspace,
    parent: WorkspaceSnapshot,
    child_candidate_id: str,
) -> Iterator[Workspace]:
    """Yield an isolated workspace materialised from one parent snapshot.

    Scratch variation receives only the workspace manifest and an optional
    workspace-specific evolution program. Prompt and skill files always come
    from ``parent`` so source history, reports, and other run state cannot leak
    into the variation. The temporary directory is outside the canonical
    workspace and is removed after the operator returns or raises.
    """
    if not child_candidate_id.strip():
        raise ValueError("child_candidate_id must not be blank")
    if child_candidate_id == parent.candidate_id:
        raise ValueError("child_candidate_id must differ from the parent candidate_id")

    with tempfile.TemporaryDirectory(prefix="aec-bench-scratch-") as scratch_dir:
        scratch_root = Path(scratch_dir)
        for relative_path in ("manifest.yaml", "program.md"):
            source_path = source.root / relative_path
            if source_path.is_file():
                shutil.copy2(source_path, scratch_root / relative_path)

        (scratch_root / "prompts").mkdir()
        (scratch_root / "prompts" / "system.md").write_text(parent.system_prompt, encoding="utf-8")
        scratch = Workspace(scratch_root)
        scratch.apply_snapshot(parent.model_copy(update={"candidate_id": child_candidate_id}))
        yield scratch


class Workspace:
    """Typed access to an evolvable agent workspace directory with git versioning."""

    def __init__(self, root: Path) -> None:
        self._root = root
        manifest_path = root / "manifest.yaml"
        if not manifest_path.exists():
            raise WorkspaceError(f"manifest.yaml not found in {root}")
        raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        self._manifest = WorkspaceManifest(**raw)
        system_md = root / "prompts" / "system.md"
        if not system_md.exists():
            raise WorkspaceError(f"prompts/system.md not found in {root}")

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def root(self) -> Path:
        return self._root

    @property
    def manifest(self) -> WorkspaceManifest:
        return self._manifest

    # ------------------------------------------------------------------
    # Prompts
    # ------------------------------------------------------------------

    def read_prompt(self) -> str:
        return (self._root / "prompts" / "system.md").read_text(encoding="utf-8")

    def write_prompt(self, content: str) -> None:
        (self._root / "prompts" / "system.md").write_text(content, encoding="utf-8")

    # ------------------------------------------------------------------
    # Skills
    # ------------------------------------------------------------------

    def list_skills(self) -> list[SkillEntry]:
        skills_dir = self._root / "skills"
        if not skills_dir.exists():
            return []
        entries: list[SkillEntry] = []
        for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
            entry = self._parse_skill_file(skill_md)
            if entry is not None:
                entries.append(entry)
        return entries

    def read_skill(self, name: str) -> SkillEntry | None:
        skill_md = self._root / "skills" / name / "SKILL.md"
        if not skill_md.exists():
            return None
        return self._parse_skill_file(skill_md)

    def write_skill(self, skill: SkillEntry) -> None:
        skill_dir = self._root / "skills" / skill.name
        skill_dir.mkdir(parents=True, exist_ok=True)
        frontmatter: dict[str, str | None] = {
            "name": skill.name,
            "description": skill.description,
            "discipline": skill.discipline,
        }
        # Remove None-valued keys so the YAML stays clean
        frontmatter = {k: v for k, v in frontmatter.items() if v is not None}
        fm_text = yaml.dump(frontmatter, default_flow_style=False).rstrip()
        content = f"---\n{fm_text}\n---\n{skill.body}"
        (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")

    def delete_skill(self, name: str) -> None:
        skill_dir = self._root / "skills" / name
        if skill_dir.exists():
            shutil.rmtree(skill_dir)

    def apply_snapshot(self, snapshot: WorkspaceSnapshot) -> None:
        """Replace the workspace's prompt and skills with those from a snapshot.

        Clears all existing skills and writes the snapshot's skills and prompt.
        Used by the evolution loop to switch to a selected parent from the archive
        before evolving on top of it.
        """
        # Clear existing skills
        for skill in self.list_skills():
            self.delete_skill(skill.name)

        # Write snapshot's prompt and skills
        self.write_prompt(snapshot.system_prompt)
        for skill in snapshot.skills:
            self.write_skill(skill)

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def export_snapshot(self, candidate_id: str) -> WorkspaceSnapshot:
        return WorkspaceSnapshot(
            system_prompt=self.read_prompt(),
            skills=tuple(self.list_skills()),
            candidate_id=candidate_id,
        )

    # ------------------------------------------------------------------
    # Git versioning
    # ------------------------------------------------------------------

    def init_versioning(self) -> WorkspaceCandidateVersion:
        """Initialise Git source and register the baseline candidate.

        The ``evo-0`` label is immutable and is not the candidate identity.
        """
        self._git("init")
        self._git("config", "user.email", "evolution@aec-bench.local")
        self._git("config", "user.name", "aec-bench evolution")

        candidates = self.list_candidates()
        baseline = next((candidate for candidate in candidates if candidate.candidate_id == "baseline"), None)
        if baseline is not None:
            return baseline
        if candidates:
            raise WorkspaceError("evolution workspace has candidates but no baseline candidate")
        self._git("add", "-A")
        self._git("commit", "--allow-empty", "-m", "evo-0: initial workspace")
        candidate = WorkspaceCandidateVersion(
            candidate_id="baseline",
            source_revision=self._git_output("rev-parse", "HEAD"),
            parent_candidate_id=None,
            summary="initial workspace",
            score=None,
            label="evo-0",
        )
        self._store_candidate(candidate)
        self._create_immutable_label(candidate.label, candidate.source_revision)
        return candidate

    def commit_candidate(
        self,
        candidate_id: str,
        summary: str,
        score: float | None = None,
        parent_candidate_id: str | None = None,
        label: str | None = None,
    ) -> WorkspaceCandidateVersion:
        """Commit workspace source and register one explicit candidate relationship."""
        existing = self.get_candidate(candidate_id)
        if existing is not None:
            requested = existing.model_copy(
                update={
                    "parent_candidate_id": parent_candidate_id,
                    "summary": summary,
                    "score": score,
                    "label": label,
                }
            )
            if requested != existing:
                raise WorkspaceError(f"candidate_id {candidate_id!r} already identifies different metadata")
            return existing

        if parent_candidate_id is not None and self.get_candidate(parent_candidate_id) is None:
            raise WorkspaceError(f"parent candidate {parent_candidate_id!r} does not exist")
        if label is not None and self._label_revision(label) is not None:
            raise WorkspaceError(f"label {label!r} already identifies another candidate")

        self._git("add", "-A")
        self._git("commit", "--allow-empty", "-m", summary)
        candidate = WorkspaceCandidateVersion(
            candidate_id=candidate_id,
            source_revision=self._git_output("rev-parse", "HEAD"),
            parent_candidate_id=parent_candidate_id,
            summary=summary,
            score=score,
            label=label,
        )
        self._store_candidate(candidate)
        if label is not None:
            self._create_immutable_label(label, candidate.source_revision)
        return candidate

    def rollback_to_candidate(self, candidate_id: str) -> None:
        """Restore candidate source as a new commit without changing its original source."""
        candidate = self.require_candidate(candidate_id)
        self._git("checkout", candidate.source_revision, "--", ".")
        self._git("add", "-A")
        self._git("commit", "--allow-empty", "-m", f"rollback to candidate {candidate_id}")

    def list_candidates(self, run_id: str | None = None) -> list[WorkspaceCandidateVersion]:
        """Return registered candidates in explicit lineage order.

        A run filter selects explicit candidate IDs, not label order.
        """
        candidates = list(self._registered_candidates())
        if run_id is None:
            return candidates
        return [
            candidate
            for candidate in candidates
            if candidate.candidate_id == "baseline" or candidate.candidate_id.startswith(f"{run_id}:")
        ]

    def get_candidate(self, candidate_id: str) -> WorkspaceCandidateVersion | None:
        """Return one candidate by domain ID."""
        return next(
            (candidate for candidate in self.list_candidates() if candidate.candidate_id == candidate_id),
            None,
        )

    def require_candidate(self, candidate_id: str) -> WorkspaceCandidateVersion:
        """Return one candidate or reject the unknown domain ID."""
        candidate = self.get_candidate(candidate_id)
        if candidate is None:
            raise WorkspaceError(f"candidate {candidate_id!r} does not exist")
        return candidate

    def resolve_candidate(self, candidate_or_label: str) -> WorkspaceCandidateVersion:
        """Resolve an exact candidate ID or its optional human label."""
        candidate = self.get_candidate(candidate_or_label)
        if candidate is not None:
            return candidate
        matches = [item for item in self.list_candidates() if item.label == candidate_or_label]
        if len(matches) == 1:
            return matches[0]
        raise WorkspaceError(f"candidate or label {candidate_or_label!r} does not exist")

    def candidate_commit_time(self, candidate_id: str) -> datetime:
        """Derive the stable Git commit time for display."""
        candidate = self.require_candidate(candidate_id)
        value = self._git_output("show", "-s", "--format=%cI", candidate.source_revision)
        return datetime.fromisoformat(value)

    def get_diff(self, from_candidate_id: str, to_candidate_id: str) -> str:
        """Return a source diff between two candidate IDs."""
        from_revision = self.require_candidate(from_candidate_id).source_revision
        to_revision = self.require_candidate(to_candidate_id).source_revision
        return self._git_output("diff", from_revision, to_revision)

    def _candidate_at_revision(self, revision: str) -> WorkspaceCandidateVersion | None:
        payload = self._try_git_output("notes", f"--ref={_CANDIDATE_NOTES_REF}", "show", revision)
        if payload is None:
            return None
        try:
            data = cast(object, json.loads(payload))
            if not isinstance(data, dict):
                raise TypeError("candidate metadata must be a JSON object")
            candidate = WorkspaceCandidateVersion.model_validate({**data, "source_revision": revision})
        except (ValueError, TypeError) as exc:
            raise WorkspaceError(f"invalid candidate metadata at {revision}: {exc}") from exc
        if candidate.label is not None:
            label_revision = self._label_revision(candidate.label)
            if label_revision != revision:
                actual = label_revision or "missing"
                raise WorkspaceError(f"immutable label {candidate.label!r} moved: expected {revision}, found {actual}")
        return candidate

    def _store_candidate(self, candidate: WorkspaceCandidateVersion) -> None:
        current = self._candidate_at_revision(candidate.source_revision)
        if current is not None:
            if current != candidate:
                raise WorkspaceError(f"source revision {candidate.source_revision} already has candidate metadata")
            return
        payload = json.dumps(
            candidate.model_dump(mode="json", exclude={"source_revision"}),
            sort_keys=True,
            separators=(",", ":"),
        )
        self._git(
            "notes",
            f"--ref={_CANDIDATE_NOTES_REF}",
            "add",
            "-m",
            payload,
            candidate.source_revision,
        )

    def _create_immutable_label(self, label: str | None, revision: str) -> None:
        if label is None:
            return
        current = self._label_revision(label)
        if current == revision:
            return
        if current is not None:
            raise WorkspaceError(f"label {label!r} already identifies {current}")
        self._git("tag", label, revision)

    def _label_revision(self, label: str) -> str | None:
        return self._try_git_output("rev-parse", "--verify", f"{label}^{{commit}}")

    def _registered_candidates(self) -> tuple[WorkspaceCandidateVersion, ...]:
        notes = self._try_git_output("notes", f"--ref={_CANDIDATE_NOTES_REF}", "list")
        if not notes:
            return ()
        candidates = [
            candidate
            for line in notes.splitlines()
            if (candidate := self._candidate_at_revision(line.rsplit(" ", 1)[-1])) is not None
        ]
        by_id = {candidate.candidate_id: candidate for candidate in candidates}
        if len(by_id) != len(candidates):
            raise WorkspaceError("candidate metadata contains duplicate candidate_id values")

        for candidate in candidates:
            if candidate.parent_candidate_id is not None and candidate.parent_candidate_id not in by_id:
                raise WorkspaceError(
                    f"candidate {candidate.candidate_id!r} has unknown parent {candidate.parent_candidate_id!r}"
                )

        ordered: list[WorkspaceCandidateVersion] = []
        emitted: set[str] = set()
        pending = dict(by_id)
        while pending:
            ready = [
                candidate
                for candidate in pending.values()
                if candidate.parent_candidate_id is None or candidate.parent_candidate_id in emitted
            ]
            if not ready:
                raise WorkspaceError("candidate metadata contains a lineage cycle")
            ready.sort(
                key=lambda candidate: (
                    self._git_output("show", "-s", "--format=%cI", candidate.source_revision),
                    candidate.source_revision,
                    candidate.candidate_id,
                )
            )
            for candidate in ready:
                ordered.append(candidate)
                emitted.add(candidate.candidate_id)
                pending.pop(candidate.candidate_id)
        return tuple(ordered)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _git(self, *args: str) -> None:
        result = subprocess.run(
            ["git", *args],
            cwd=self._root,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise WorkspaceError(f"git {' '.join(args)} failed: {result.stderr.strip()}")

    def _git_output(self, *args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=self._root,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise WorkspaceError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
        return result.stdout.strip()

    def _try_git_output(self, *args: str) -> str | None:
        result = subprocess.run(
            ["git", *args],
            cwd=self._root,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return None
        return result.stdout.strip()

    def _parse_skill_file(self, path: Path) -> SkillEntry | None:
        """Parse a SKILL.md file with YAML frontmatter and return a SkillEntry."""
        text = path.read_text(encoding="utf-8")
        match = _FRONTMATTER_RE.match(text)
        if match is None:
            return None
        frontmatter_text = match.group(1)
        body = text[match.end() :].lstrip("\n")
        meta = yaml.safe_load(frontmatter_text)
        if not isinstance(meta, dict):
            return None
        return SkillEntry(
            name=meta.get("name", path.parent.name),
            description=meta.get("description", ""),
            discipline=meta.get("discipline"),
            body=body,
        )
