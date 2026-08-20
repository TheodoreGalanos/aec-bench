# ABOUTME: Workspace class providing typed read/write access to an evolvable agent workspace.
# ABOUTME: Manages prompts, skills (SKILL.md format), snapshots, and git-based versioning.

from __future__ import annotations

import json
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import cast

import yaml

from aec_bench.contracts.evolution import (
    SkillEntry,
    WorkspaceCandidateVersion,
    WorkspaceManifest,
    WorkspaceMigrationIssue,
    WorkspaceMigrationPlan,
    WorkspaceMigrationReport,
    WorkspaceSnapshot,
)

# Regex for YAML frontmatter at the top of a SKILL.md file.
_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
_SCORE_RE = re.compile(r"score\s+([0-9]+(?:\.[0-9]+)?)")
_CANDIDATE_NOTES_REF = "aec-bench-evolution"


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
        if "version" in raw:
            if "schema_version" in raw:
                raise WorkspaceError("workspace manifest cannot contain both version and schema_version")
            version = raw.pop("version")
            if version != "0.1.0":
                raise WorkspaceError(f"unsupported legacy workspace manifest version: {version!r}")
            raw["schema_version"] = 1
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
            skills=self.list_skills(),
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
        if self._legacy_labels():
            raise WorkspaceError("legacy evolution labels require an explicit workspace migration plan")

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
        if not candidates and self._legacy_labels():
            raise WorkspaceError("legacy evolution labels require an explicit workspace migration plan")
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

    def migrate_legacy_versions(self, plan: WorkspaceMigrationPlan) -> WorkspaceMigrationReport:
        """Register legacy labels only when source and lineage are explicit."""
        existing = {candidate.candidate_id: candidate for candidate in self._registered_candidates()}
        planned_ids = {item.candidate_id for item in plan.candidates}
        issues: list[WorkspaceMigrationIssue] = []
        resolved: list[WorkspaceCandidateVersion] = []
        resolved_revisions: set[str] = set()
        planned_labels = {item.label for item in plan.candidates}

        for label in self._legacy_labels():
            if label not in planned_labels:
                issues.append(
                    WorkspaceMigrationIssue(
                        label=label,
                        code="source_ambiguous",
                        message=f"legacy label {label!r} is not included in the migration plan",
                    )
                )

        for item in plan.candidates:
            revision = self._label_revision(item.label)
            if revision is None:
                issues.append(
                    WorkspaceMigrationIssue(
                        label=item.label,
                        code="label_missing",
                        message=f"legacy label {item.label!r} does not exist",
                    )
                )
                continue
            if item.expected_source_revision is None:
                issues.append(
                    WorkspaceMigrationIssue(
                        label=item.label,
                        code="source_ambiguous",
                        message=f"legacy label {item.label!r} has no expected source revision",
                    )
                )
                continue
            if revision != item.expected_source_revision:
                issues.append(
                    WorkspaceMigrationIssue(
                        label=item.label,
                        code="label_moved",
                        message=(
                            f"legacy label {item.label!r} resolves to {revision}, not {item.expected_source_revision}"
                        ),
                    )
                )
                continue
            if item.parent_candidate_id is not None and (
                item.parent_candidate_id not in existing and item.parent_candidate_id not in planned_ids
            ):
                issues.append(
                    WorkspaceMigrationIssue(
                        label=item.label,
                        code="lineage_missing",
                        message=f"parent candidate {item.parent_candidate_id!r} is not registered or planned",
                    )
                )
                continue

            current = existing.get(item.candidate_id)
            if current is not None:
                if (
                    current.source_revision != revision
                    or current.label != item.label
                    or current.parent_candidate_id != item.parent_candidate_id
                ):
                    issues.append(
                        WorkspaceMigrationIssue(
                            label=item.label,
                            code="candidate_conflict",
                            message=f"candidate_id {item.candidate_id!r} already identifies different metadata",
                        )
                    )
                    continue
                resolved.append(current)
                resolved_revisions.add(revision)
                continue
            if revision in resolved_revisions:
                issues.append(
                    WorkspaceMigrationIssue(
                        label=item.label,
                        code="source_ambiguous",
                        message=f"source revision {revision} is assigned to more than one candidate",
                    )
                )
                continue

            summary = self._git_output("show", "-s", "--format=%s", revision)
            score_match = _SCORE_RE.search(summary)
            resolved.append(
                WorkspaceCandidateVersion(
                    candidate_id=item.candidate_id,
                    source_revision=revision,
                    parent_candidate_id=item.parent_candidate_id,
                    summary=summary,
                    score=float(score_match.group(1)) if score_match else None,
                    label=item.label,
                )
            )
            resolved_revisions.add(revision)

        label_to_candidate_id = {
            candidate.label: candidate.candidate_id
            for candidate in (*existing.values(), *resolved)
            if candidate.label is not None
        }
        sidecar_updates, sidecar_issues = self._prepare_legacy_sidecar_migrations(label_to_candidate_id)
        issues.extend(sidecar_issues)
        if issues:
            return WorkspaceMigrationReport(issues=tuple(issues))

        for candidate in resolved:
            self._store_candidate(candidate)
        self._persist_current_manifest_schema()
        for path, payload in sidecar_updates:
            path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return WorkspaceMigrationReport(migrated_candidate_ids=tuple(item.candidate_id for item in resolved))

    def _prepare_legacy_sidecar_migrations(
        self,
        label_to_candidate_id: dict[str, str],
    ) -> tuple[list[tuple[Path, object]], list[WorkspaceMigrationIssue]]:
        updates: list[tuple[Path, object]] = []
        issues: list[WorkspaceMigrationIssue] = []

        archive_path = self._root / "archive.json"
        if archive_path.exists():
            archive = self._read_migration_json(archive_path, issues)
            changed = False
            if isinstance(archive, dict) and isinstance(archive.get("entries"), list):
                for index, entry in enumerate(archive["entries"]):
                    snapshot = entry.get("snapshot") if isinstance(entry, dict) else None
                    if isinstance(snapshot, dict) and "workspace_version" in snapshot:
                        changed |= self._replace_legacy_candidate_field(
                            snapshot,
                            label_to_candidate_id,
                            location=f"archive.json entry {index}",
                            issues=issues,
                        )
            elif archive is not None:
                issues.append(
                    WorkspaceMigrationIssue(
                        label="archive.json",
                        code="source_ambiguous",
                        message="archive.json does not contain an entries list",
                    )
                )
            if changed:
                updates.append((archive_path, archive))

        graveyard_path = self._root / "graveyard.json"
        if graveyard_path.exists():
            graveyard = self._read_migration_json(graveyard_path, issues)
            changed = False
            if isinstance(graveyard, list):
                for index, entry in enumerate(graveyard):
                    if isinstance(entry, dict) and "workspace_version" in entry:
                        changed |= self._replace_legacy_candidate_field(
                            entry,
                            label_to_candidate_id,
                            location=f"graveyard.json entry {index}",
                            issues=issues,
                        )
            elif graveyard is not None:
                issues.append(
                    WorkspaceMigrationIssue(
                        label="graveyard.json",
                        code="source_ambiguous",
                        message="graveyard.json is not a list",
                    )
                )
            if changed:
                updates.append((graveyard_path, graveyard))

        return updates, issues

    @staticmethod
    def _read_migration_json(path: Path, issues: list[WorkspaceMigrationIssue]) -> object | None:
        try:
            return cast(object, json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError) as exc:
            issues.append(
                WorkspaceMigrationIssue(
                    label=path.name,
                    code="source_ambiguous",
                    message=f"cannot read {path.name}: {exc}",
                )
            )
            return None

    @staticmethod
    def _replace_legacy_candidate_field(
        record: dict[str, object],
        label_to_candidate_id: dict[str, str],
        *,
        location: str,
        issues: list[WorkspaceMigrationIssue],
    ) -> bool:
        legacy_label = record.get("workspace_version")
        if not isinstance(legacy_label, str) or not legacy_label:
            issues.append(
                WorkspaceMigrationIssue(
                    label=location,
                    code="source_ambiguous",
                    message=f"{location} has an invalid workspace_version",
                )
            )
            return False
        candidate_id = label_to_candidate_id.get(legacy_label)
        if candidate_id is None:
            issues.append(
                WorkspaceMigrationIssue(
                    label=legacy_label,
                    code="source_ambiguous",
                    message=f"{location} references unplanned legacy label {legacy_label!r}",
                )
            )
            return False
        current = record.get("candidate_id")
        if current is not None and current != candidate_id:
            issues.append(
                WorkspaceMigrationIssue(
                    label=legacy_label,
                    code="candidate_conflict",
                    message=f"{location} contains conflicting candidate identity",
                )
            )
            return False
        record.pop("workspace_version")
        record["candidate_id"] = candidate_id
        return True

    def _persist_current_manifest_schema(self) -> None:
        manifest_path = self._root / "manifest.yaml"
        raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        if "version" not in raw:
            return
        raw.pop("version")
        raw["schema_version"] = self._manifest.schema_version
        manifest_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

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

    def _legacy_labels(self) -> tuple[str, ...]:
        raw = self._try_git_output("tag", "-l", "evo-*")
        if not raw:
            return ()
        registered_labels = {candidate.label for candidate in self._registered_candidates() if candidate.label}
        return tuple(label for label in raw.splitlines() if label not in registered_labels)

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
