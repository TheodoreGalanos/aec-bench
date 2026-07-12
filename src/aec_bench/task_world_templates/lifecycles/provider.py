# ABOUTME: Defines the explicit package-scoped provider boundary for sealed holdout lifecycles.
# ABOUTME: Keeps private task discovery, identifiers, content, and failures outside public registries and exports.

from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Callable, Collection, Iterator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Protocol, TypeVar, cast, runtime_checkable

from aec_bench.meta_harness.evidence_lifecycle import evidence_lifecycle_package_identity
from aec_bench.meta_harness.evidence_lifecycle_state import (
    LifecycleOperationActionRecord,
    LifecycleOperationDisposition,
    LifecycleOperationOutcome,
)
from aec_bench.meta_harness.evidence_request_protocol import EvidenceLifecycleError
from aec_bench.meta_harness.lifecycle_operation_protocol import (
    LifecycleOperationPlan,
    LifecycleOperationPrerequisiteError,
    LifecycleOperationResolver,
    LifecycleOperationSourceContext,
    lifecycle_operation_source_identity,
)
from aec_bench.task_world_templates.contracts import (
    CompositeTaskWorldTemplate,
    EvidenceLifecycleSpec,
    LifecycleOperationSpec,
)

SEALED_LIFECYCLE_RECEIPT_FILENAME = "sealed-lifecycle.json"
_PROVIDER_PROTOCOL = {
    "schema_version": "1",
    "discovery": "forbidden",
    "mount_scope": "exact_package_context",
    "methods": [
        "materialize(output_dir)",
        "validate_package(package_dir)",
        "build_operation_resolver(package_dir,run_dir)",
        "verify(package_dir,run_dir)",
    ],
    "authority": "task_evidence_and_verification_only",
    "reward_owner": "host",
}
_T = TypeVar("_T")


class SealedLifecycleProviderError(EvidenceLifecycleError):
    """Report a stable non-disclosing provider-boundary failure code."""


@runtime_checkable
class SealedLifecycleProvider(Protocol):
    """Supply one already-selected private target without discovery or enumeration."""

    schema_version: str

    def materialize(self, output_dir: Path) -> Path: ...

    def validate_package(self, package_dir: Path) -> None: ...

    def build_operation_resolver(
        self,
        package_dir: Path,
        run_dir: Path,
    ) -> LifecycleOperationResolver: ...

    def verify(self, package_dir: Path, run_dir: Path) -> dict[str, Any]: ...


@dataclass(frozen=True)
class SealedLifecycleMount:
    """Bind one provider instance to one exact immutable package for one call context."""

    package_dir: Path
    package_sha256: str
    package_tree_sha256: str
    provider: SealedLifecycleProvider
    _public_template_ids: frozenset[str]

    @contextmanager
    def activate(self) -> Iterator[SealedLifecycleMount]:
        """Make this exact binding available only within the current execution context."""
        _validate_mount(self)
        token = _ACTIVE_SEALED_LIFECYCLE_MOUNT.set(self)
        try:
            yield self
        finally:
            _ACTIVE_SEALED_LIFECYCLE_MOUNT.reset(token)

    def build_operation_resolver(self, run_dir: Path) -> LifecycleOperationResolver:
        """Build a package-bound resolver while redacting provider failures."""
        _validate_mount(self)

        def build() -> LifecycleOperationResolver:
            resolver = self.provider.build_operation_resolver(self.package_dir, Path(run_dir))
            resolver_package = Path(resolver.package_dir)
            if resolver_package.is_symlink() or resolver_package.resolve() != self.package_dir:
                raise ValueError("resolver package mismatch")
            for method_name in ("current_source", "plan", "execute"):
                if not callable(getattr(resolver, method_name, None)):
                    raise TypeError("resolver method missing")
            return resolver

        resolver = _redacted_call("sealed_provider_resolver_failed", build)
        _validate_mount(self)
        return _SanitizedLifecycleOperationResolver(mount=self, resolver=resolver)

    def verify(self, run_dir: Path) -> dict[str, Any]:
        """Invoke private task verification without exposing provider exceptions."""
        _validate_mount(self)

        def invoke() -> dict[str, Any]:
            result = self.provider.verify(self.package_dir, Path(run_dir))
            if not isinstance(result, dict):
                raise TypeError("verifier result must be a mapping")
            return result

        result = _redacted_call("sealed_provider_verifier_failed", invoke)
        _validate_mount(self)
        return result


class _SanitizedLifecycleOperationResolver:
    def __init__(self, *, mount: SealedLifecycleMount, resolver: LifecycleOperationResolver) -> None:
        self.package_dir = mount.package_dir
        self.mount = mount
        self.resolver = resolver

    def current_source(
        self,
        actions: Sequence[LifecycleOperationActionRecord],
    ) -> LifecycleOperationSourceContext:
        _require_exact_active_mount(self.mount)

        def resolve() -> LifecycleOperationSourceContext:
            source = self.resolver.current_source(actions)
            _validate_source_context(source, self.package_dir)
            return source

        source = _redacted_call("sealed_provider_resolver_failed", resolve)
        _require_exact_active_mount(self.mount)
        return source

    def plan(
        self,
        operation: LifecycleOperationSpec,
        actions: Sequence[LifecycleOperationActionRecord],
    ) -> LifecycleOperationPlan:
        _require_exact_active_mount(self.mount)
        prerequisite_failed = False
        resolver_failed = False
        try:
            plan = self.resolver.plan(operation, actions)
            _validate_operation_plan(
                plan,
                operation=operation,
                actions=actions,
                package_dir=self.package_dir,
            )
        except LifecycleOperationPrerequisiteError:
            prerequisite_failed = True
        except Exception:
            resolver_failed = True
        if prerequisite_failed:
            raise LifecycleOperationPrerequisiteError("sealed_provider_prerequisites_incomplete")
        if resolver_failed:
            raise SealedLifecycleProviderError("sealed_provider_resolver_failed")
        _require_exact_active_mount(self.mount)
        return plan

    def execute(self, plan: LifecycleOperationPlan, artifact_dir: Path) -> None:
        _require_exact_active_mount(self.mount)

        def execute_and_validate() -> None:
            self.resolver.execute(plan, Path(artifact_dir))
            _validate_operation_artifacts(plan, Path(artifact_dir))

        _redacted_call(
            "sealed_provider_resolver_failed",
            execute_and_validate,
        )
        _require_exact_active_mount(self.mount)


_ACTIVE_SEALED_LIFECYCLE_MOUNT: ContextVar[SealedLifecycleMount | None] = ContextVar(
    "active_sealed_lifecycle_mount",
    default=None,
)


def sealed_lifecycle_provider_protocol_identity() -> dict[str, str]:
    """Return the stable public protocol version and hash without provider metadata."""
    encoded = json.dumps(_PROVIDER_PROTOCOL, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "schema_version": str(_PROVIDER_PROTOCOL["schema_version"]),
        "sha256": hashlib.sha256(encoded).hexdigest(),
    }


def is_sealed_lifecycle_package(package_dir: Path) -> bool:
    """Detect the generic host receipt without reading provider-controlled content."""
    receipt = Path(package_dir) / SEALED_LIFECYCLE_RECEIPT_FILENAME
    return receipt.exists() or receipt.is_symlink()


def active_sealed_lifecycle_mount(package_dir: Path) -> SealedLifecycleMount:
    """Return only the active binding for the exact sealed package path."""
    mount = _ACTIVE_SEALED_LIFECYCLE_MOUNT.get()
    package = Path(package_dir)
    if mount is None or package.is_symlink():
        raise SealedLifecycleProviderError("sealed_provider_not_mounted")
    try:
        matches = package.resolve() == mount.package_dir
    except OSError:
        matches = False
    if not matches:
        raise SealedLifecycleProviderError("sealed_provider_not_mounted")
    _validate_mount(mount)
    return mount


def _require_exact_active_mount(mount: SealedLifecycleMount) -> None:
    if active_sealed_lifecycle_mount(mount.package_dir) is not mount:
        raise SealedLifecycleProviderError("sealed_provider_not_mounted")


def _redacted_call(code: str, operation: Callable[[], _T]) -> _T:
    try:
        return operation()
    except Exception:
        pass
    raise SealedLifecycleProviderError(code)


def _materialize_sealed_lifecycle(
    provider: SealedLifecycleProvider,
    output_dir: Path,
    *,
    public_template_ids: Collection[str],
) -> SealedLifecycleMount:
    _validate_provider_contract(provider)
    output = Path(output_dir)
    if output.exists() or output.is_symlink():
        raise SealedLifecycleProviderError("sealed_provider_output_not_empty")
    succeeded = False
    try:
        result = Path(
            _redacted_call(
                "sealed_provider_materialization_failed",
                lambda: provider.materialize(output),
            )
        )
        if output.is_symlink() or not output.is_dir() or result.resolve() != output.resolve():
            raise SealedLifecycleProviderError("sealed_provider_materialization_invalid")
        _validate_package_contract(
            provider,
            output,
            public_template_ids=frozenset(public_template_ids),
            require_receipt=False,
        )
        _write_receipt(output)
        mount = _bind_sealed_lifecycle(
            provider,
            output,
            public_template_ids=public_template_ids,
        )
        succeeded = True
        return mount
    finally:
        if not succeeded:
            _discard_generated_output(output)


def _bind_sealed_lifecycle(
    provider: SealedLifecycleProvider,
    package_dir: Path,
    *,
    public_template_ids: Collection[str],
) -> SealedLifecycleMount:
    _validate_provider_contract(provider)
    package = _canonical_package_dir(package_dir)
    identity = _validate_package_contract(
        provider,
        package,
        public_template_ids=frozenset(public_template_ids),
        require_receipt=True,
    )
    return SealedLifecycleMount(
        package_dir=package,
        package_sha256=identity["package_sha256"],
        package_tree_sha256=_sealed_package_tree_sha256(package),
        provider=provider,
        _public_template_ids=frozenset(public_template_ids),
    )


def _validate_mount(mount: SealedLifecycleMount) -> None:
    identity = _validate_package_contract(
        mount.provider,
        mount.package_dir,
        public_template_ids=mount._public_template_ids,
        require_receipt=True,
    )
    if identity["package_sha256"] != mount.package_sha256:
        raise SealedLifecycleProviderError("sealed_provider_package_changed")
    current_tree_sha256 = _redacted_call(
        "sealed_provider_package_invalid",
        lambda: _sealed_package_tree_sha256(mount.package_dir),
    )
    if current_tree_sha256 != mount.package_tree_sha256:
        raise SealedLifecycleProviderError("sealed_provider_package_changed")


def _validate_provider_contract(provider: object) -> None:
    methods = ("materialize", "validate_package", "build_operation_resolver", "verify")

    def inspect_contract() -> bool:
        valid = getattr(provider, "schema_version", None) == "1" and all(
            callable(getattr(provider, method, None)) for method in methods
        )
        return valid

    valid = _redacted_call("sealed_provider_contract_invalid", inspect_contract)
    if not valid:
        raise SealedLifecycleProviderError("sealed_provider_contract_invalid")


def _validate_package_contract(
    provider: SealedLifecycleProvider,
    package_dir: Path,
    *,
    public_template_ids: frozenset[str],
    require_receipt: bool,
) -> dict[str, str]:
    package = _canonical_package_dir(package_dir)
    package_invalid = False
    try:
        if require_receipt:
            _read_validated_receipt(package)
        template = CompositeTaskWorldTemplate.model_validate(_read_json(package / "template.json"))
        lifecycle = EvidenceLifecycleSpec.model_validate(_read_json(package / "lifecycle.json"))
        if template.evidence_lifecycle != lifecycle:
            raise ValueError("lifecycle mismatch")
        if template.template_id in public_template_ids:
            raise SealedLifecycleProviderError("sealed_provider_public_template_collision")
        identity_before_validation = evidence_lifecycle_package_identity(package)
        tree_before_validation = _sealed_package_tree_sha256(package)
    except SealedLifecycleProviderError:
        raise
    except Exception:
        package_invalid = True
    if package_invalid:
        raise SealedLifecycleProviderError("sealed_provider_package_invalid")
    _redacted_call(
        "sealed_provider_validation_failed",
        lambda: provider.validate_package(package),
    )
    identity_after_validation, tree_after_validation = _redacted_call(
        "sealed_provider_package_invalid",
        lambda: (
            evidence_lifecycle_package_identity(package),
            _sealed_package_tree_sha256(package),
        ),
    )
    if identity_after_validation != identity_before_validation or tree_after_validation != tree_before_validation:
        raise SealedLifecycleProviderError("sealed_provider_validation_mutated_package")
    return identity_after_validation


def _canonical_package_dir(package_dir: Path) -> Path:
    package = Path(package_dir)
    if package.is_symlink() or not package.is_dir():
        raise SealedLifecycleProviderError("sealed_provider_package_invalid")
    return _redacted_call(
        "sealed_provider_package_invalid",
        lambda: package.resolve(strict=True),
    )


def _validate_source_context(source: LifecycleOperationSourceContext, package_dir: Path) -> None:
    if not isinstance(source, LifecycleOperationSourceContext):
        raise TypeError("resolver source context is invalid")
    source_package = Path(source.package_dir)
    if source_package.is_symlink():
        raise ValueError("resolver source package is symlinked")
    resolved = source_package.resolve()
    if resolved != package_dir and package_dir not in resolved.parents:
        raise ValueError("resolver source package escapes the mounted package")
    physical_sha256, visible_sha256 = lifecycle_operation_source_identity(
        source_state=source.source_state,
        revision_id=source.revision_id,
    )
    if source.physical_source_state_sha256 != physical_sha256 or source.visible_source_state_sha256 != visible_sha256:
        raise ValueError("resolver source identity mismatch")


def _validate_operation_plan(
    plan: object,
    *,
    operation: LifecycleOperationSpec,
    actions: Sequence[LifecycleOperationActionRecord],
    package_dir: Path,
) -> None:
    if not isinstance(plan, LifecycleOperationPlan):
        raise TypeError("resolver plan is invalid")
    if plan.operation_id != operation.operation_id or plan.operation_kind != operation.kind:
        raise ValueError("resolver plan identity mismatch")
    if plan.disposition not in {
        LifecycleOperationDisposition.COMPUTED,
        LifecycleOperationDisposition.ACTIVATED,
    }:
        raise ValueError("resolver plan disposition is invalid")
    _validate_source_context(plan.source_before, package_dir)
    _validate_source_context(plan.source_after, package_dir)
    if not _is_sha256(plan.input_projection_sha256):
        raise ValueError("resolver plan projection identity is invalid")
    if not isinstance(plan.prerequisite_action_ids, tuple):
        raise ValueError("resolver plan prerequisite identity is invalid")
    if len(plan.prerequisite_action_ids) != len(set(plan.prerequisite_action_ids)):
        raise ValueError("resolver plan prerequisite identity is invalid")
    known_action_ids = {action.action_id for action in actions if action.outcome is LifecycleOperationOutcome.COMPLETED}
    if any(
        not isinstance(action_id, str) or action_id not in known_action_ids
        for action_id in plan.prerequisite_action_ids
    ):
        raise ValueError("resolver plan prerequisite identity is invalid")
    visible_paths = plan.model_visible_artifact_paths
    if not isinstance(visible_paths, tuple) or not visible_paths or len(visible_paths) != len(set(visible_paths)):
        raise ValueError("resolver plan visible artifact contract is invalid")
    for raw_path in visible_paths:
        if not isinstance(raw_path, str):
            raise ValueError("resolver plan visible artifact contract is invalid")
        path = PurePosixPath(raw_path)
        if "\\" in raw_path or path.is_absolute() or ".." in path.parts or path.as_posix() != raw_path:
            raise ValueError("resolver plan visible artifact contract is invalid")
    if not isinstance(plan.payload, dict):
        raise ValueError("resolver plan payload is invalid")
    json.dumps(plan.payload, allow_nan=False, sort_keys=True, separators=(",", ":"))


def _validate_operation_artifacts(plan: LifecycleOperationPlan, artifact_dir: Path) -> None:
    if artifact_dir.is_symlink() or not artifact_dir.is_dir():
        raise ValueError("resolver artifact root is invalid")
    files: set[str] = set()
    for path in artifact_dir.rglob("*"):
        if path.is_symlink():
            raise ValueError("resolver artifact tree is invalid")
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError("resolver artifact tree is invalid")
        files.add(path.relative_to(artifact_dir).as_posix())
    if not files or not set(plan.model_visible_artifact_paths).issubset(files):
        raise ValueError("resolver artifact tree is incomplete")


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _sealed_package_tree_sha256(package_dir: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(Path(package_dir).rglob("*"), key=lambda item: item.relative_to(package_dir).as_posix()):
        if path.is_symlink():
            raise ValueError("sealed package tree contains a symlink")
        relative = path.relative_to(package_dir).as_posix().encode("utf-8")
        if path.is_dir():
            kind = b"directory"
        elif path.is_file():
            kind = b"file"
        else:
            raise ValueError("sealed package tree contains a special entry")
        digest.update(len(kind).to_bytes(8, "big"))
        digest.update(kind)
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        if kind == b"file":
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(64 * 1024), b""):
                    digest.update(chunk)
    return digest.hexdigest()


def _expected_receipt() -> dict[str, str]:
    return {
        "provider_protocol_sha256": sealed_lifecycle_provider_protocol_identity()["sha256"],
        "public_export": "forbidden",
        "public_registry": "forbidden",
        "schema_version": "1",
        "visibility": "holdout",
    }


def _write_receipt(package_dir: Path) -> None:
    receipt = package_dir / SEALED_LIFECYCLE_RECEIPT_FILENAME
    if receipt.exists() or receipt.is_symlink():
        raise SealedLifecycleProviderError("sealed_provider_receipt_invalid")

    def write() -> None:
        receipt.write_text(json.dumps(_expected_receipt(), indent=2, sort_keys=True) + "\n", encoding="utf-8")

    _redacted_call("sealed_provider_receipt_invalid", write)


def _read_validated_receipt(package_dir: Path) -> dict[str, str]:
    receipt = package_dir / SEALED_LIFECYCLE_RECEIPT_FILENAME
    if receipt.is_symlink() or not receipt.is_file():
        raise SealedLifecycleProviderError("sealed_provider_receipt_invalid")
    payload = _redacted_call(
        "sealed_provider_receipt_invalid",
        lambda: json.loads(receipt.read_text(encoding="utf-8")),
    )
    if payload != _expected_receipt():
        raise SealedLifecycleProviderError("sealed_provider_receipt_invalid")
    return cast(dict[str, str], payload)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("expected JSON object")
    return payload


def _discard_generated_output(output: Path) -> None:
    try:
        if output.is_symlink():
            output.unlink(missing_ok=True)
        elif output.is_dir():
            shutil.rmtree(output)
        elif output.exists():
            output.unlink()
    except OSError:
        pass
