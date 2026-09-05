# ABOUTME: Tests portable lifecycle source identity and exact runtime dependency checks.
# ABOUTME: Proves relocation is safe while source and dependency changes remain rejected.

import tarfile
from importlib.metadata import version
from pathlib import Path

import pytest

from aec_bench.prime_lab import lifecycle_environment as runtime
from aec_bench.prime_lab.lifecycle_source import (
    lifecycle_runtime_requirements,
    read_runtime_requirements,
    snapshot_lifecycle_source,
)


def test_portable_source_validation_accepts_installed_layout_and_rejects_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package = Path(runtime.__file__).parents[1]
    manifest_root = tmp_path / "environment"
    snapshot = manifest_root / "provider-source.tar"
    identity = snapshot_lifecycle_source(
        package, snapshot, package_version=version("aec-bench"), requirements={"pydantic": version("pydantic")}
    )
    installed = tmp_path / "site-packages" / "aec_bench"
    with tarfile.open(snapshot) as archive:
        # This archive was produced above from trusted repository files.
        archive.extractall(installed.parent, filter="data")
    monkeypatch.setattr(runtime, "__file__", str(installed / "prime_lab" / "lifecycle_environment.py"))
    assert not (installed.parent / "pyproject.toml").exists()
    runtime._assert_source_provenance(identity, manifest_root=manifest_root)
    marker = installed / "prime_lab" / "unexpected.py"
    marker.write_text("CHANGED = True\n")
    with pytest.raises(ValueError, match="source identity"):
        runtime._assert_source_provenance(identity, manifest_root=manifest_root)
    marker.unlink()
    target = installed / "prime_lab" / "lifecycle_environment.py"
    target.write_text(target.read_text() + "\n# changed\n")
    with pytest.raises(ValueError, match="source identity"):
        runtime._assert_source_provenance(identity, manifest_root=manifest_root)


def test_runtime_dependency_drift_is_rejected(tmp_path: Path) -> None:
    snapshot = tmp_path / "provider-source.tar"
    snapshot_lifecycle_source(
        Path(runtime.__file__).parents[1], snapshot, package_version="0.1.0", requirements={"pydantic": "0.0.0"}
    )
    with pytest.raises(ValueError, match="dependency mismatch: pydantic"):
        read_runtime_requirements(snapshot)


def test_runtime_requirements_cover_active_prime_dependencies() -> None:
    requirements = lifecycle_runtime_requirements()
    assert {"prime", "verifiers", "datasets", "pydantic", "openai-agents"} <= requirements.keys()
    assert "aec-bench" not in requirements
    assert all(version(name) == selected for name, selected in requirements.items())
