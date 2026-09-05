# ABOUTME: Binds lifecycle adapters to portable source bytes and resolved runtime dependencies.
# ABOUTME: Uses the same archive representation in source checkouts and installed wheels.

from __future__ import annotations

import hashlib
import io
import json
import tarfile
from importlib import metadata
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from aec_bench.contracts.artifacts import ArtifactRef
from aec_bench.contracts.provider_provenance import ProviderAdapterIdentity
from aec_bench.providers.source_identity import write_deterministic_source_snapshot

REQUIREMENTS_MEMBER = "runtime-requirements.json"


def lifecycle_runtime_requirements() -> dict[str, str]:
    """Resolve the installed AEC-Bench Prime dependency closure, including active extras."""
    pending = [("aec-bench", frozenset({"prime"}))]
    visited: set[tuple[str, frozenset[str]]] = set()
    versions: dict[str, str] = {}
    while pending:
        name, extras = pending.pop()
        name = canonicalize_name(name)
        if (name, extras) in visited:
            continue
        visited.add((name, extras))
        distribution = metadata.distribution(name)
        if name != "aec-bench":
            versions[name] = distribution.version
        for raw in distribution.requires or ():
            requirement = Requirement(raw)
            if requirement.marker is not None and not any(
                requirement.marker.evaluate({"extra": extra}) for extra in {"", *extras}
            ):
                continue
            if requirement.url is not None:
                raise ValueError(f"Prime runtime dependency requires an installable version: {requirement.name}")
            installed = metadata.version(requirement.name)
            if not requirement.specifier.contains(installed, prereleases=True):
                raise ValueError(f"installed Prime dependency does not satisfy {requirement}")
            pending.append((requirement.name, frozenset(requirement.extras)))
    return dict(sorted(versions.items()))


def snapshot_lifecycle_source(
    package_root: Path, destination: Path, *, package_version: str, requirements: dict[str, str]
) -> ProviderAdapterIdentity:
    """Retain distribution bytes without absolute paths or checkout metadata."""
    paths = (
        package_root / "prime_lab",
        package_root / "lifecycles",
        package_root / "contracts" / "provider_provenance.py",
        package_root / "providers" / "source_identity.py",
    )
    write_deterministic_source_snapshot(root=package_root.parent, source_paths=paths, destination=destination)
    content = (json.dumps(requirements, sort_keys=True, indent=2) + "\n").encode()
    with tarfile.open(destination, "a") as archive:
        member = tarfile.TarInfo(REQUIREMENTS_MEMBER)
        member.size = len(content)
        member.mode = 0o644
        archive.addfile(member, io.BytesIO(content))
    data = destination.read_bytes()
    return ProviderAdapterIdentity(
        adapter_id="aec-bench/prime-lifecycle",
        package_version=package_version,
        source_snapshot=ArtifactRef(
            artifact_id="provider-source.tar",
            sha256=hashlib.sha256(data).hexdigest(),
            size_bytes=len(data),
            media_type="application/x-tar",
        ),
    )


def read_runtime_requirements(snapshot: Path) -> dict[str, str] | None:
    """Read portable archives; older checkout-bound snapshots have no dependency member."""
    with tarfile.open(snapshot) as archive:
        names = archive.getnames()
        if REQUIREMENTS_MEMBER not in names:
            return None
        if names.count(REQUIREMENTS_MEMBER) != 1:
            raise ValueError("duplicate Prime runtime requirements")
        member = archive.getmember(REQUIREMENTS_MEMBER)
        if not member.isfile() or member.size > 1_000_000:
            raise ValueError("invalid Prime runtime requirements member")
        stream = archive.extractfile(member)
        assert stream is not None
        requirements = json.load(stream)
    if not isinstance(requirements, dict) or not requirements:
        raise ValueError("Prime runtime requirements must be a non-empty version map")
    for name, version in requirements.items():
        if not isinstance(name, str) or not isinstance(version, str):
            raise ValueError("Prime runtime requirements must contain package names and versions")
        requirement = Requirement(f"{name}=={version}")
        if requirement.url is not None or str(requirement.specifier) != f"=={version}":
            raise ValueError("Prime runtime requirements must use exact versions")
        installed = metadata.version(name)
        if installed != version:
            raise ValueError(f"Prime runtime dependency mismatch: {name} requires {version}, installed {installed}")
    return requirements
