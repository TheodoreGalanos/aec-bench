# ABOUTME: Workspace class providing typed read/write access to an evolvable agent workspace.
# ABOUTME: Manages prompts, skills (SKILL.md format), snapshots, and git-based versioning.

from __future__ import annotations

import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import yaml

from aec_bench.contracts.evolution import (
    SkillEntry,
    WorkspaceManifest,
    WorkspaceSnapshot,
    WorkspaceVersion,
)

# Regex for YAML frontmatter at the top of a SKILL.md file.
_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)


class WorkspaceError(Exception):
    """Raised when the workspace is invalid or a filesystem/git operation fails."""


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
        Used by the orchestrator to switch to a selected parent from the archive
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

    def export_snapshot(self, workspace_version: str) -> WorkspaceSnapshot:
        return WorkspaceSnapshot(
            system_prompt=self.read_prompt(),
            skills=self.list_skills(),
            workspace_version=workspace_version,
        )

    # ------------------------------------------------------------------
    # Git versioning
    # ------------------------------------------------------------------

    def init_versioning(self) -> WorkspaceVersion:
        """Initialise a git repo in the workspace, commit everything, and tag evo-0.

        Idempotent: if evo-0 already exists, returns the existing version
        without modifying the repository.
        """
        self._git("init")
        self._git("config", "user.email", "evolution@aec-bench.local")
        self._git("config", "user.name", "aec-bench evolution")

        # Check if evo-0 already exists (re-run scenario)
        try:
            sha = self._git_output("rev-list", "-1", "evo-0")
            return WorkspaceVersion(
                tag="evo-0",
                parent_tag=None,
                sha=sha,
                timestamp=datetime.now(tz=UTC),
                summary="initial workspace",
                score_at_tag=None,
            )
        except WorkspaceError:
            pass

        self._git("add", "-A")
        self._git("commit", "--allow-empty", "-m", "evo-0: initial workspace")
        self._git("tag", "evo-0")
        sha = self._git_output("rev-parse", "HEAD")
        return WorkspaceVersion(
            tag="evo-0",
            parent_tag=None,
            sha=sha,
            timestamp=datetime.now(tz=UTC),
            summary="initial workspace",
            score_at_tag=None,
        )

    def commit_and_tag(
        self,
        tag: str,
        summary: str,
        score: float | None = None,
        parent_tag: str | None = None,
    ) -> WorkspaceVersion:
        """Stage all changes, commit (allows empty), and force-set tag."""
        self._git("add", "-A")
        self._git("commit", "--allow-empty", "-m", f"{tag}: {summary}")
        self._git("tag", "-f", tag)
        sha = self._git_output("rev-parse", "HEAD")
        return WorkspaceVersion(
            tag=tag,
            parent_tag=parent_tag,
            sha=sha,
            timestamp=datetime.now(tz=UTC),
            summary=summary,
            score_at_tag=score,
        )

    def rollback_to_tag(self, tag: str) -> None:
        """Restore workspace files to the state at *tag* as a NEW commit (non-destructive)."""
        self._git("checkout", tag, "--", ".")
        self._git("add", "-A")
        self._git("commit", "--allow-empty", "-m", f"rollback to {tag}")

    def list_versions(self, run_id: str | None = None) -> list[WorkspaceVersion]:
        """Return evo-* tags ordered by version number.

        When *run_id* is provided, only returns tags for that run plus evo-0.
        Otherwise returns all tags (backwards compatible).
        """
        raw = self._git_output("tag", "-l", "evo-*")
        if not raw:
            return []
        tags = [t for t in raw.splitlines() if t.strip()]

        if run_id:
            prefix = f"evo-{run_id}-"
            tags = [t for t in tags if t.startswith(prefix) or t == "evo-0"]

        versions: list[WorkspaceVersion] = []
        for t in tags:
            sha = self._git_output("rev-list", "-1", t)
            # Read the commit subject for the tagged commit as the summary.
            summary = self._git_output("log", "-1", "--format=%s", sha) or t
            versions.append(
                WorkspaceVersion(
                    tag=t,
                    parent_tag=None,
                    sha=sha,
                    timestamp=datetime.now(tz=UTC),
                    summary=summary,
                )
            )

        # Sort by cycle number (last segment after final hyphen)
        def _sort_key(v: WorkspaceVersion) -> int:
            try:
                return int(v.tag.split("-")[-1])
            except ValueError:
                return 0

        return sorted(versions, key=_sort_key)

    def get_diff(self, from_tag: str, to_tag: str) -> str:
        """Return a unified diff between two evo tags."""
        return self._git_output("diff", from_tag, to_tag)

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
