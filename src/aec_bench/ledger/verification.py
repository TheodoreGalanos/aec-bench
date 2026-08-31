# ABOUTME: Verifies structured portable evidence and every referenced exact artifact byte.
# ABOUTME: Keeps explicit integrity checks separate from metadata-only EvidenceIndex queries.

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import NamedTuple

from aec_bench.contracts.artifacts import ArtifactRef
from aec_bench.contracts.authority_evidence import AuthorityEvidenceRef
from aec_bench.contracts.resolved_run import ResolvedRunSpec
from aec_bench.contracts.run_plan import RunPlan
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.execution.models import AttemptReceipt, TrialFinalization
from aec_bench.ledger.artifact_repository import ArtifactRepository
from aec_bench.ledger.evidence_run_store import EvidenceRunState
from aec_bench.ledger.index import _is_run_metadata_path, _validate_record_path
from aec_bench.ledger.reader import _iter_trial_record_paths, _references


class EvidenceVerificationReport(NamedTuple):
    """Counts and errors from one explicit evidence verification pass."""

    records: int
    receipts: int
    finalizations: int
    artifacts: int
    errors: tuple[str, ...]


def verify_evidence(ledger_root: Path, *, run_id: str | None = None) -> EvidenceVerificationReport:
    """Verify selected records, portable run metadata, receipts, finalizations, and artifact bytes."""

    root = Path(ledger_root)
    errors: list[str] = []
    record_paths: list[tuple[Path, TrialRecord]] = []
    discovered_run_dirs = _discover_portable_run_dirs(root)
    run_id_hints = {run_dir: _portable_run_id_hint(run_dir) for run_dir in discovered_run_dirs}
    run_dirs = {run_dir for run_dir in discovered_run_dirs if run_id is None or run_id_hints[run_dir] == run_id}
    selector_found = bool(run_dirs)
    artifact_count = 0
    for path in _iter_trial_record_paths(root):
        if _is_run_metadata_path(root, path):
            continue
        portable_run_dir = path.parent.parent if path.parent.name == "trial-records" else None
        try:
            raw_payload = json.loads(path.read_bytes())
        except (OSError, ValueError, TypeError) as error:
            if run_id is None or (portable_run_dir is not None and portable_run_dir in run_dirs):
                errors.append(f"{path}: {error}")
            continue
        raw_run_id = raw_payload.get("run_id") if isinstance(raw_payload, dict) else None
        if run_id is not None:
            if portable_run_dir is not None:
                if portable_run_dir not in run_dirs:
                    if raw_run_id != run_id:
                        continue
                    run_dirs.add(portable_run_dir)
                    run_id_hints[portable_run_dir] = _portable_run_id_hint(portable_run_dir)
                    selector_found = True
            elif raw_run_id != run_id:
                continue
            if raw_run_id == run_id:
                selector_found = True
        try:
            record = TrialRecord.model_validate(raw_payload)
        except (OSError, ValueError, TypeError) as error:
            errors.append(f"{path}: {error}")
            continue
        try:
            _validate_record_path(root, path)
            expected_run_id = None if portable_run_dir is None else run_id_hints.get(portable_run_dir)
            if expected_run_id is not None and record.run_id != expected_run_id:
                raise ValueError("portable TrialRecord run_id does not match the run specification")
            read_trial_record(path, ledger_root=root)
            artifact_count += len({reference.artifact_id for reference in _references(record)})
            record_paths.append((path, record))
        except (OSError, ValueError, TypeError, RuntimeError) as error:
            errors.append(f"{path}: {error}")

    if run_id is not None and not selector_found:
        raise ValueError(f"no portable evidence or trial record matches run: {run_id}")

    receipts = 0
    finalizations = 0
    for run_dir in sorted(run_dirs):
        trial_records_dir = run_dir / "trial-records"
        _verify_run_metadata(run_dir, errors)
        artifact_roots = [trial_records_dir / "_artifacts", root / "_artifacts"]
        receipt_attempt_ids: set[str] = set()
        receipt_dir = run_dir / "receipts"
        for path in sorted(receipt_dir.glob("*.json")) if receipt_dir.is_dir() else ():
            try:
                _validate_evidence_path(root, path, "receipt")
                receipt = AttemptReceipt.model_validate_json(path.read_bytes())
                artifact_count += _verify_artifacts(
                    receipt.output_references,
                    receipt.authority_evidence,
                    artifact_roots,
                )
                receipt_attempt_ids.add(str(receipt.attempt_id))
                receipts += 1
            except (OSError, ValueError, TypeError, RuntimeError) as error:
                errors.append(f"{path}: {error}")
        finalization_dir = run_dir / "finalizations"
        for path in sorted(finalization_dir.glob("*.json")) if finalization_dir.is_dir() else ():
            try:
                _validate_evidence_path(root, path, "finalization")
                finalization = TrialFinalization.model_validate_json(path.read_bytes())
                record = _verify_finalization_reference(
                    root,
                    trial_records_dir,
                    finalization.trial_record_ref,
                )
                if record.trial_id != str(finalization.trial_id):
                    raise ValueError("finalization trial_id does not match its referenced TrialRecord")
                expected_run_id = run_id_hints[run_dir]
                if expected_run_id is not None and record.run_id != expected_run_id:
                    raise ValueError("finalization TrialRecord run_id does not match the run specification")
                if str(finalization.attempt_id) not in receipt_attempt_ids:
                    raise ValueError("finalization attempt_id does not match a receipt in the portable run")
                finalizations += 1
            except (OSError, ValueError, TypeError, RuntimeError) as error:
                errors.append(f"{path}: {error}")
    return EvidenceVerificationReport(len(record_paths), receipts, finalizations, artifact_count, tuple(errors))


def _verify_run_metadata(run_dir: Path, errors: list[str]) -> None:
    models = (("resolved-run-spec.json", ResolvedRunSpec), ("state.json", EvidenceRunState))
    parsed: dict[str, object] = {}
    for name, model_type in models:
        path = run_dir / name
        if not path.is_file():
            errors.append(f"{path}: required portable run metadata is missing")
            continue
        try:
            if path.is_symlink():
                raise ValueError("portable run metadata must not be a symlink")
            parsed[name] = model_type.model_validate_json(path.read_bytes())
        except (OSError, ValueError, TypeError) as error:
            errors.append(f"{path}: {error}")
    spec = parsed.get("resolved-run-spec.json")
    state = parsed.get("state.json")
    plan_path = run_dir / "run-plan.json"
    plan: object | None = None
    if plan_path.is_file():
        try:
            if plan_path.is_symlink():
                raise ValueError("portable run metadata must not be a symlink")
            plan = RunPlan.model_validate_json(plan_path.read_bytes())
            parsed["run-plan.json"] = plan
        except (OSError, ValueError, TypeError) as error:
            errors.append(f"{plan_path}: {error}")
    elif isinstance(state, EvidenceRunState) and (state.state != "draft" or state.plan_identity is not None):
        errors.append(f"{plan_path}: required portable run plan is missing")
    if isinstance(spec, ResolvedRunSpec) and isinstance(plan, RunPlan) and spec.run_identity != plan.run_identity:
        errors.append(f"{run_dir}: resolved run spec and run plan have different run identities")
    if (
        isinstance(spec, ResolvedRunSpec)
        and isinstance(state, EvidenceRunState)
        and spec.run_identity != state.run_identity
    ):
        errors.append(f"{run_dir}: resolved run spec and state have different run identities")
    if isinstance(plan, RunPlan) and isinstance(state, EvidenceRunState) and state.plan_identity != plan.plan_identity:
        errors.append(f"{run_dir}: run state and run plan have different plan identities")
    if isinstance(plan, RunPlan) and isinstance(state, EvidenceRunState):
        expected_plan_state = "draft" if state.state == "draft" else "ready"
        if plan.state != expected_plan_state:
            errors.append(f"{run_dir}: run state and run plan have incompatible states")


def _verify_artifacts(
    output_references: tuple[ArtifactRef, ...],
    authority_evidence: tuple[AuthorityEvidenceRef, ...],
    roots: list[Path],
) -> int:
    references = [*output_references, *(item.artifact for item in authority_evidence)]
    if not references:
        return 0
    repositories = [ArtifactRepository(root) for root in roots if root.is_dir()]
    if not repositories:
        raise FileNotFoundError("portable artifact repository is missing")
    verified = 0
    for reference in references:
        if not any(_read_reference(repository, reference) for repository in repositories):
            raise FileNotFoundError(f"artifact reference cannot be verified: {reference.artifact_id}")
        verified += 1
    return verified


def _discover_portable_run_dirs(root: Path) -> tuple[Path, ...]:
    """Find portable run packages even when their trial records are unreadable."""

    if not root.is_dir():
        return ()
    discovered: set[Path] = set()
    for trial_records_dir in root.rglob("trial-records"):
        if not trial_records_dir.is_dir():
            continue
        try:
            _validate_evidence_path(root, trial_records_dir, "portable run")
        except ValueError:
            continue
        discovered.add(trial_records_dir.parent)
    for name in ("resolved-run-spec.json", "run-plan.json", "state.json"):
        for metadata_path in root.rglob(name):
            run_dir = metadata_path.parent
            if not metadata_path.is_file():
                continue
            if name == "state.json" and not any(
                sibling.exists()
                for sibling in (
                    run_dir / "resolved-run-spec.json",
                    run_dir / "run-plan.json",
                    run_dir / "trial-records",
                )
            ):
                continue
            try:
                _validate_evidence_path(root, metadata_path, "portable run metadata")
            except ValueError:
                continue
            discovered.add(run_dir)
    return tuple(sorted(discovered))


def _portable_run_id_hint(run_dir: Path) -> str | None:
    """Return a trusted run identity hint from portable metadata or raw records."""

    for name, model_type in (
        ("resolved-run-spec.json", ResolvedRunSpec),
        ("run-plan.json", RunPlan),
        ("state.json", EvidenceRunState),
    ):
        path = run_dir / name
        try:
            model = model_type.model_validate_json(path.read_bytes())
        except (OSError, ValueError, TypeError):
            continue
        return str(model.run_identity.id)
    records_dir = run_dir / "trial-records"
    for path in sorted(records_dir.glob("*.json")) if records_dir.is_dir() else ():
        try:
            payload = json.loads(path.read_bytes())
        except (OSError, ValueError, TypeError):
            continue
        if isinstance(payload, dict):
            raw_run_id = payload.get("run_id")
            if isinstance(raw_run_id, str):
                return raw_run_id
    return None


def _read_reference(repository: ArtifactRepository, reference: ArtifactRef) -> bool:
    try:
        repository.read_bytes(reference)
    except (OSError, RuntimeError, ValueError):
        return False
    return True


def _verify_finalization_reference(root: Path, trial_records_dir: Path, reference: str) -> TrialRecord:
    relative = PurePosixPath(reference)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("finalization record reference must be a safe relative path")
    path = root.joinpath(*relative.parts)
    _validate_record_path(root, path)
    if not path.is_file():
        raise FileNotFoundError(f"finalization record reference is unavailable: {reference}")
    if path.parent != trial_records_dir:
        raise ValueError("finalization record reference must target its portable run trial-records directory")
    return read_trial_record(path, ledger_root=root)


def _validate_evidence_path(root: Path, path: Path, label: str) -> None:
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"{label} path must be below the ledger root")
    current = root
    for part in path.relative_to(root).parts:
        current /= part
        if current.is_symlink():
            raise ValueError(f"{label} path must not contain symlinks")


def read_trial_record(path: Path, *, ledger_root: Path) -> TrialRecord:
    """Read one record through the existing full reference-verifying ledger path."""

    from aec_bench.ledger.reader import read_trial_record as _read_trial_record

    return _read_trial_record(path, ledger_root=ledger_root)


__all__ = ("EvidenceVerificationReport", "verify_evidence")
