# ABOUTME: Coordinates durable chosen-point rollout groups through a registered task branch port.
# ABOUTME: Exposes only group creation, inspection, status, and child run resolution.

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from aec_bench.contracts.continual_world import (
    ContinualRolloutChildReceipt,
    ContinualRolloutChildRequest,
    ContinualRolloutChildRunRef,
    ContinualRolloutGroupRequest,
    ContinualRolloutGroupState,
    ContinualRolloutGroupStatus,
    ContinualRolloutLineage,
)
from aec_bench.task_world_templates.continual.branch_port import (
    ContinualWorldBranchMaterialization,
    ContinualWorldBranchPort,
    VerifiedContinualWorldBranchOrigin,
)
from aec_bench.task_world_templates.continual.definition import ContinualWorldDefinition
from aec_bench.task_world_templates.continual.rollout_repository import (
    ContinualRolloutError,
    ContinualRolloutRepository,
)


class ContinualRolloutControl:
    """Task-neutral durable coordinator for isolated child world creation."""

    def __init__(
        self,
        definition: ContinualWorldDefinition,
        branch_port: ContinualWorldBranchPort,
        *,
        parent_run_root: Path,
        rollout_repository_root: Path,
        authorised_principal_ids: tuple[str, ...],
        package_root: Path | None = None,
    ) -> None:
        if not authorised_principal_ids or any(not principal.strip() for principal in authorised_principal_ids):
            raise ValueError("continual rollout control requires one authorised host principal")
        if len(authorised_principal_ids) != len(set(authorised_principal_ids)):
            raise ValueError("continual rollout host principals must be distinct")
        self._definition = definition
        self._branch_port = branch_port
        self._parent_run_root = Path(parent_run_root)
        self._package_root = Path(package_root) if package_root is not None else None
        disjoint_roots = (self._parent_run_root,) + ((self._package_root,) if self._package_root is not None else ())
        self._repository = ContinualRolloutRepository(
            rollout_repository_root,
            disjoint_roots=disjoint_roots,
        )
        self._authorised_principal_ids = frozenset(authorised_principal_ids)

    def create_group(self, request: ContinualRolloutGroupRequest) -> ContinualRolloutLineage:
        """Create or exactly recover all ordered children in one rollout group."""
        selected, profile_value = self._validated_request(request)
        self._repository.validate_storage_identities(
            selected.group_id,
            tuple(child.child_id for child in selected.children),
        )
        origin = self._verify_origin(profile_value, selected)
        with self._repository.locked(selected.group_id):
            self._repository.publish_group_request(selected)
            if self._repository.lineage_exists(selected.group_id):
                lineage = self._load_complete_lineage(selected)
                self._verify_persisted_children(
                    selected,
                    profile_value,
                    lineage.children,
                    expected_ancestor_world_branch_ids=origin.ancestor_world_branch_ids,
                )
                return lineage
            for child in selected.children:
                self._repository.publish_child_request(selected.group_id, child)

        candidates = tuple(
            self._materialize_or_load_child(
                profile_value=profile_value,
                request=selected,
                child=child,
                origin=origin,
            )
            for child in selected.children
        )

        with self._repository.locked(selected.group_id):
            self._repository.publish_group_request(selected)
            self._require_persisted_child_requests(selected)
            receipts = tuple(
                self._publish_or_load_child_receipt(
                    profile_value=profile_value,
                    request=selected,
                    child=child,
                    candidate=candidate,
                    expected_ancestor_world_branch_ids=origin.ancestor_world_branch_ids,
                )
                for child, candidate in zip(selected.children, candidates, strict=True)
            )
            lineage = ContinualRolloutLineage(
                request_id=selected.request_id,
                group_id=selected.group_id,
                task_world_id=selected.task_world_id,
                world_build=selected.world_build,
                profile_ref=selected.profile_ref,
                request_content_sha256=selected.content_sha256,
                parent_manifest_content_sha256=selected.parent_manifest_content_sha256,
                parent_snapshot=selected.parent_snapshot,
                origin_verification_content_sha256=selected.origin_verification_content_sha256,
                children=receipts,
            )
            self._repository.publish_lineage(lineage)
            return self._load_complete_lineage(selected)

    def inspect_group(self, group_id: str) -> ContinualRolloutLineage:
        """Load the complete immutable lineage for one ready group."""
        with self._repository.locked(group_id):
            request, _ = self._validated_request(self._repository.load_group_request(group_id))
            return self._load_complete_lineage(request)

    def group_status(self, group_id: str) -> ContinualRolloutGroupStatus:
        """Return ordered durable progress for one complete or interrupted group."""
        with self._repository.locked(group_id):
            request, _ = self._validated_request(self._repository.load_group_request(group_id))
            requested = tuple(child.child_id for child in request.children)
            created_items: list[str] = []
            lineage_exists = self._repository.lineage_exists(request.group_id)
            for child in request.children:
                child_request_exists = self._repository.child_request_exists(
                    request.group_id,
                    child.child_id,
                )
                child_receipt_exists = self._repository.child_receipt_exists(
                    request.group_id,
                    child.child_id,
                )
                if not child_request_exists:
                    if lineage_exists or child_receipt_exists:
                        raise ContinualRolloutError(
                            "child-request-integrity",
                            child.child_id,
                        )
                    continue
                stored_child = self._repository.load_child_request(request.group_id, child.child_id)
                if stored_child != child:
                    raise ContinualRolloutError("child-request-integrity", child.child_id)
                if not child_receipt_exists:
                    if lineage_exists:
                        raise ContinualRolloutError(
                            "child-receipt-integrity",
                            child.child_id,
                        )
                    continue
                receipt = self._repository.load_child_receipt(request.group_id, child.child_id)
                self._require_receipt_matches_child(receipt, request, child)
                created_items.append(child.child_id)
            created = tuple(created_items)
            ready = lineage_exists and created == requested
            if ready:
                self._load_complete_lineage(request)
            return ContinualRolloutGroupStatus(
                group_id=request.group_id,
                request_id=request.request_id,
                state=ContinualRolloutGroupState.READY if ready else ContinualRolloutGroupState.PREPARING,
                requested_child_ids=requested,
                created_child_ids=created,
            )

    def child_run_ref(self, group_id: str, child_id: str) -> ContinualRolloutChildRunRef:
        """Resolve one materialized child without exposing sibling or actor settings."""
        with self._repository.locked(group_id):
            request, profile_value = self._validated_request(
                self._repository.load_group_request(group_id),
            )
            lineage = self._load_complete_lineage(request)
            try:
                child_index = tuple(child.child_id for child in request.children).index(child_id)
            except ValueError as exc:
                raise ContinualRolloutError("child-not-found", child_id) from exc
            child = request.children[child_index]
            receipt = lineage.children[child_index]
            self._require_receipt_matches_child(receipt, request, child)
            self._verify_child(
                profile_value,
                request,
                child,
                self._repository.child_world_root(group_id, child_id),
                receipt,
            )
            return ContinualRolloutChildRunRef(
                group_id=group_id,
                child_id=child_id,
                task_world_id=request.task_world_id,
                run_id=receipt.initial_snapshot.run_id,
                episode_id=receipt.initial_snapshot.episode_id,
                world_branch_id=receipt.initial_snapshot.world_branch_id,
                initial_snapshot=receipt.initial_snapshot,
                child_manifest_content_sha256=receipt.child_manifest_content_sha256,
            )

    def _load_complete_lineage(
        self,
        request: ContinualRolloutGroupRequest,
    ) -> ContinualRolloutLineage:
        if not self._repository.lineage_exists(request.group_id):
            raise ContinualRolloutError("group-not-ready", request.group_id)
        lineage = self._repository.load_lineage(request.group_id)
        self._require_lineage_matches_request(lineage, request)
        requested_ids = tuple(child.child_id for child in request.children)
        if tuple(receipt.child_id for receipt in lineage.children) != requested_ids:
            raise ContinualRolloutError("lineage-integrity", "child order differs from the request")
        self._require_persisted_child_requests(request)
        for child, lineage_receipt in zip(request.children, lineage.children, strict=True):
            stored_receipt = self._repository.load_child_receipt(request.group_id, child.child_id)
            if stored_receipt != lineage_receipt:
                raise ContinualRolloutError("child-receipt-integrity", child.child_id)
            self._require_receipt_matches_child(stored_receipt, request, child)
        return lineage

    def _validated_request(
        self,
        request: ContinualRolloutGroupRequest,
    ) -> tuple[ContinualRolloutGroupRequest, object]:
        try:
            selected = ContinualRolloutGroupRequest.model_validate(request.model_dump(mode="json"))
        except ValidationError as exc:
            raise ContinualRolloutError("request-integrity", str(exc)) from exc
        if selected.authority_id not in self._authorised_principal_ids:
            raise ContinualRolloutError("authority", "rollout authority is not authorised")
        if selected.world_build != self._definition.ref:
            raise ContinualRolloutError("definition", "rollout definition reference does not match")
        if selected.task_world_id != self._definition.ref.task_world_id:
            raise ContinualRolloutError("task-world", "rollout task world does not match")
        try:
            profile_value = self._definition.load_profile(selected.profile_ref).value
        except (KeyError, ValueError) as exc:
            raise ContinualRolloutError("profile", str(exc)) from exc
        return selected, profile_value

    def _verify_origin(
        self,
        profile_value: object,
        request: ContinualRolloutGroupRequest,
    ) -> VerifiedContinualWorldBranchOrigin:
        try:
            origin = self._branch_port.verify_origin(
                profile_value=profile_value,
                package_root=self._package_root,
                parent_run_root=self._parent_run_root,
                request=request,
            )
        except ContinualRolloutError:
            raise
        except (OSError, RuntimeError, ValueError) as exc:
            raise ContinualRolloutError("origin-verification", str(exc)) from exc
        if (
            origin.parent_snapshot != request.parent_snapshot
            or origin.parent_manifest_content_sha256 != request.parent_manifest_content_sha256
            or origin.origin_verification_content_sha256 != request.origin_verification_content_sha256
        ):
            raise ContinualRolloutError("origin-verification", "branch port returned another origin")
        if not origin.ancestor_world_branch_ids:
            raise ContinualRolloutError("origin-verification", "branch ancestry is empty")
        if len(origin.ancestor_world_branch_ids) != len(set(origin.ancestor_world_branch_ids)):
            raise ContinualRolloutError("origin-verification", "branch ancestry contains a cycle")
        if origin.ancestor_world_branch_ids[-1] != request.parent_snapshot.world_branch_id:
            raise ContinualRolloutError("origin-verification", "branch ancestry does not end at the parent")
        return origin

    def _materialize_or_load_child(
        self,
        *,
        profile_value: object,
        request: ContinualRolloutGroupRequest,
        child: ContinualRolloutChildRequest,
        origin: VerifiedContinualWorldBranchOrigin,
    ) -> ContinualRolloutChildReceipt:
        with self._repository.materializing_child(request.group_id, child.child_id):
            return self._materialize_or_load_child_serially(
                profile_value=profile_value,
                request=request,
                child=child,
                origin=origin,
            )

    def _materialize_or_load_child_serially(
        self,
        *,
        profile_value: object,
        request: ContinualRolloutGroupRequest,
        child: ContinualRolloutChildRequest,
        origin: VerifiedContinualWorldBranchOrigin,
    ) -> ContinualRolloutChildReceipt:
        child_root = self._repository.child_world_root(request.group_id, child.child_id)
        if self._repository.child_receipt_exists(request.group_id, child.child_id):
            receipt = self._repository.load_child_receipt(request.group_id, child.child_id)
            self._require_receipt_matches_child(receipt, request, child)
            self._require_receipt_ancestry(receipt, origin.ancestor_world_branch_ids)
            self._verify_child(profile_value, request, child, child_root, receipt)
            return receipt
        try:
            materialization = self._branch_port.materialize_child(
                profile_value=profile_value,
                package_root=self._package_root,
                parent_run_root=self._parent_run_root,
                child_run_root=child_root,
                request=request,
                child=child,
                origin=origin,
            )
        except ContinualRolloutError:
            raise
        except (OSError, RuntimeError, ValueError) as exc:
            raise ContinualRolloutError("child-materialization", str(exc)) from exc
        if materialization.ancestor_world_branch_ids != origin.ancestor_world_branch_ids:
            raise ContinualRolloutError(
                "child-lineage",
                "branch port returned ancestry that differs from the verified origin",
            )
        receipt = self._receipt_from_materialization(request, child, materialization)
        self._require_receipt_matches_child(receipt, request, child)
        self._require_receipt_ancestry(receipt, origin.ancestor_world_branch_ids)
        self._verify_child(profile_value, request, child, child_root, receipt)
        return receipt

    def _publish_or_load_child_receipt(
        self,
        *,
        profile_value: object,
        request: ContinualRolloutGroupRequest,
        child: ContinualRolloutChildRequest,
        candidate: ContinualRolloutChildReceipt,
        expected_ancestor_world_branch_ids: tuple[str, ...],
    ) -> ContinualRolloutChildReceipt:
        self._require_receipt_matches_child(candidate, request, child)
        self._require_receipt_ancestry(candidate, expected_ancestor_world_branch_ids)
        if self._repository.child_receipt_exists(request.group_id, child.child_id):
            receipt = self._repository.load_child_receipt(request.group_id, child.child_id)
        else:
            self._verify_child(
                profile_value,
                request,
                child,
                self._repository.child_world_root(request.group_id, child.child_id),
                candidate,
            )
            self._repository.publish_child_receipt(candidate)
            receipt = self._repository.load_child_receipt(request.group_id, child.child_id)
        self._require_receipt_matches_child(receipt, request, child)
        self._require_receipt_ancestry(receipt, expected_ancestor_world_branch_ids)
        self._verify_child(
            profile_value,
            request,
            child,
            self._repository.child_world_root(request.group_id, child.child_id),
            receipt,
        )
        return receipt

    def _require_persisted_child_requests(
        self,
        request: ContinualRolloutGroupRequest,
    ) -> None:
        for child in request.children:
            if not self._repository.child_request_exists(request.group_id, child.child_id):
                raise ContinualRolloutError("child-request-integrity", child.child_id)
            stored_child = self._repository.load_child_request(request.group_id, child.child_id)
            if stored_child != child:
                raise ContinualRolloutError("child-request-integrity", child.child_id)

    def _verify_child(
        self,
        profile_value: object,
        request: ContinualRolloutGroupRequest,
        child: ContinualRolloutChildRequest,
        child_root: Path,
        receipt: ContinualRolloutChildReceipt,
    ) -> None:
        try:
            self._branch_port.verify_child(
                profile_value=profile_value,
                package_root=self._package_root,
                parent_run_root=self._parent_run_root,
                child_run_root=child_root,
                request=request,
                child=child,
                receipt=receipt,
            )
        except ContinualRolloutError:
            raise
        except (OSError, RuntimeError, ValueError) as exc:
            raise ContinualRolloutError("child-verification", str(exc)) from exc

    @staticmethod
    def _receipt_from_materialization(
        request: ContinualRolloutGroupRequest,
        child: ContinualRolloutChildRequest,
        materialization: ContinualWorldBranchMaterialization,
    ) -> ContinualRolloutChildReceipt:
        return ContinualRolloutChildReceipt(
            group_id=request.group_id,
            child_id=child.child_id,
            child_request_content_sha256=child.content_sha256,
            parent_snapshot=request.parent_snapshot,
            initial_snapshot=materialization.initial_snapshot,
            child_manifest_content_sha256=materialization.child_manifest_content_sha256,
            task_branch_receipt_content_sha256=materialization.task_branch_receipt_content_sha256,
            ancestor_world_branch_ids=materialization.ancestor_world_branch_ids,
        )

    def _verify_persisted_children(
        self,
        request: ContinualRolloutGroupRequest,
        profile_value: object,
        receipts: tuple[ContinualRolloutChildReceipt, ...],
        *,
        expected_ancestor_world_branch_ids: tuple[str, ...],
    ) -> None:
        if tuple(receipt.child_id for receipt in receipts) != tuple(child.child_id for child in request.children):
            raise ContinualRolloutError("lineage-integrity", "child order differs from the request")
        for child, receipt in zip(request.children, receipts, strict=True):
            self._require_receipt_matches_child(receipt, request, child)
            self._require_receipt_ancestry(receipt, expected_ancestor_world_branch_ids)
            self._verify_child(
                profile_value,
                request,
                child,
                self._repository.child_world_root(request.group_id, child.child_id),
                receipt,
            )

    @staticmethod
    def _require_receipt_matches_child(
        receipt: ContinualRolloutChildReceipt,
        request: ContinualRolloutGroupRequest,
        child: ContinualRolloutChildRequest,
    ) -> None:
        if (
            receipt.group_id != request.group_id
            or receipt.child_id != child.child_id
            or receipt.child_request_content_sha256 != child.content_sha256
            or receipt.parent_snapshot != request.parent_snapshot
            or (
                receipt.initial_snapshot.run_id,
                receipt.initial_snapshot.episode_id,
                receipt.initial_snapshot.world_branch_id,
            )
            != (child.run_id, child.episode_id, child.world_branch_id)
        ):
            raise ContinualRolloutError("child-receipt-integrity", child.child_id)

    @staticmethod
    def _require_lineage_matches_request(
        lineage: ContinualRolloutLineage,
        request: ContinualRolloutGroupRequest,
    ) -> None:
        if (
            lineage.request_id != request.request_id
            or lineage.group_id != request.group_id
            or lineage.task_world_id != request.task_world_id
            or lineage.world_build != request.world_build
            or lineage.profile_ref != request.profile_ref
            or lineage.request_content_sha256 != request.content_sha256
            or lineage.parent_manifest_content_sha256 != request.parent_manifest_content_sha256
            or lineage.parent_snapshot != request.parent_snapshot
            or lineage.origin_verification_content_sha256 != request.origin_verification_content_sha256
        ):
            raise ContinualRolloutError("lineage-integrity", request.group_id)

    @staticmethod
    def _require_receipt_ancestry(
        receipt: ContinualRolloutChildReceipt,
        expected_ancestor_world_branch_ids: tuple[str, ...],
    ) -> None:
        if receipt.ancestor_world_branch_ids != expected_ancestor_world_branch_ids:
            raise ContinualRolloutError("child-lineage", receipt.child_id)


__all__ = ["ContinualRolloutControl", "ContinualRolloutError"]
