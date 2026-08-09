# ABOUTME: Applies operation-profile algebra over task-world dictionaries.
# ABOUTME: Falls back to structured agentic orchestration requests when deterministic handles are insufficient.

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

MISSING = object()
DEFAULT_ALLOWED_ACTIONS = [
    "propose_operation_handle",
    "propose_component_transform",
    "request_schema_extension",
    "request_human_review",
]
OPERATION_AXIS_FIELDS = {
    "projection": "projection_axes",
    "difference": "difference_axes",
    "subset": "subset_axes",
    "product": "product_axes",
}


@dataclass(frozen=True)
class OperationResult:
    status: str
    mode: str
    operation: dict[str, Any]
    transformed_world: dict[str, Any] | None = None
    operation_record: dict[str, Any] | None = None
    orchestration_request: dict[str, Any] | None = None
    issues: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "mode": self.mode,
            "operation": self.operation,
            "transformed_world": self.transformed_world,
            "operation_record": self.operation_record,
            "orchestration_request": self.orchestration_request,
            "issues": self.issues,
        }


def apply_world_operation(
    world: dict[str, Any],
    operation: dict[str, Any],
) -> OperationResult:
    operation_name = operation.get("operation") or operation.get("type")
    if operation_name == "projection":
        return _apply_projection(world, operation)
    if operation_name == "difference":
        return _apply_difference(world, operation)
    if operation_name == "subset":
        return _apply_subset(world, operation)
    if operation_name == "product":
        return _apply_product(world, operation)
    return _blocked_result(
        world,
        operation,
        [{"code": "operation_not_supported", "message": f"Unsupported operation: {operation_name}"}],
    )


def validate_operation_proposal(proposal: Any) -> list[str]:
    if not isinstance(proposal, dict):
        return ["operation proposal must be a JSON object"]

    errors: list[str] = []
    if proposal.get("status") != "complete":
        errors.append("status must be 'complete'")
    if not isinstance(proposal.get("operation"), dict):
        errors.append("operation must be an object")
    for field_name in ["proposed_action", "rationale"]:
        if not _has_text(proposal.get(field_name)):
            errors.append(f"{field_name} must be a non-empty string")
    if not _is_nonempty_string_list(proposal.get("evidence_refs")):
        errors.append("evidence_refs must be a non-empty list of strings")

    confidence = proposal.get("confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, int | float) or not 0.0 <= confidence <= 1.0:
        errors.append("confidence must be a number between 0.0 and 1.0")
    return errors


def record_operation_proposal(
    world: dict[str, Any],
    proposal: dict[str, Any],
) -> dict[str, Any]:
    errors = validate_operation_proposal(proposal)
    if errors:
        raise ValueError("; ".join(errors))
    updated = copy.deepcopy(world)
    updated.setdefault("agentic_operation_proposals", []).append(copy.deepcopy(proposal))
    return updated


def operation_proposal_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": [
            "status",
            "operation",
            "proposed_action",
            "rationale",
            "evidence_refs",
            "confidence",
        ],
        "properties": {
            "status": {"const": "complete"},
            "operation": {"type": "object"},
            "proposed_action": {"enum": DEFAULT_ALLOWED_ACTIONS},
            "rationale": {"type": "string", "minLength": 1},
            "evidence_refs": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
            },
            "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "repair_targets": {"type": "array", "items": {"type": "string"}},
            "new_operation_handles": {"type": "object"},
            "world_patch": {"type": "object"},
            "requires_human_approval": {"type": "boolean"},
        },
    }


def _apply_projection(
    world: dict[str, Any],
    operation: dict[str, Any],
) -> OperationResult:
    issues, axis, handle = _validate_axis_operation(world, operation, "projection")
    if issues:
        return _blocked_result(world, operation, issues)

    assert axis is not None
    assert handle is not None
    paths = list(handle["paths"])
    missing = _missing_paths(world, paths)
    if missing:
        return _blocked_result(world, operation, [_path_missing_issue(path) for path in missing])

    projected = _base_projected_world(world, axis)
    for path in paths:
        _set_path(projected, path, copy.deepcopy(_lookup(world, path)))
    projected["operation_handles"] = {axis: copy.deepcopy(handle)}
    record = _operation_record(
        operation="projection",
        axis=axis,
        source_world_id=world.get("world_id"),
        selected_paths=paths,
    )
    _append_operation_history(projected, record)
    return OperationResult(
        status="applied",
        mode="deterministic",
        operation=copy.deepcopy(operation),
        transformed_world=projected,
        operation_record=record,
    )


def _apply_difference(
    world: dict[str, Any],
    operation: dict[str, Any],
) -> OperationResult:
    issues, axis, handle = _validate_axis_operation(world, operation, "difference")
    if issues:
        return _blocked_result(world, operation, issues)

    assert axis is not None
    assert handle is not None
    paths = list(handle["paths"])
    missing = _missing_paths(world, paths)
    if missing:
        return _blocked_result(world, operation, [_path_missing_issue(path) for path in missing])

    transformed = copy.deepcopy(world)
    for path in paths:
        _delete_path(transformed, path)
    _remove_axis(transformed, axis)
    record = _operation_record(
        operation="difference",
        axis=axis,
        source_world_id=world.get("world_id"),
        removed_paths=paths,
    )
    _append_operation_history(transformed, record)
    return OperationResult(
        status="applied",
        mode="deterministic",
        operation=copy.deepcopy(operation),
        transformed_world=transformed,
        operation_record=record,
    )


def _apply_subset(
    world: dict[str, Any],
    operation: dict[str, Any],
) -> OperationResult:
    issues, axis, handle = _validate_axis_operation(world, operation, "subset")
    if issues:
        return _blocked_result(world, operation, issues)
    if "include" not in operation and "exclude" not in operation:
        return _blocked_result(
            world,
            operation,
            [{"code": "subset_selector_missing", "message": "Subset requires include or exclude."}],
        )

    assert axis is not None
    assert handle is not None
    paths = list(handle["paths"])
    missing = _missing_paths(world, paths)
    if missing:
        return _blocked_result(world, operation, [_path_missing_issue(path) for path in missing])

    transformed = copy.deepcopy(world)
    for path in paths:
        value = _lookup(transformed, path)
        restricted = _restrict_value(
            value,
            include=operation.get("include"),
            exclude=operation.get("exclude"),
        )
        if restricted is MISSING:
            return _blocked_result(
                world,
                operation,
                [
                    {
                        "code": "subset_path_not_restrictable",
                        "message": f"Path cannot be restricted as a list or object: {path}",
                        "path": path,
                    }
                ],
            )
        _set_path(transformed, path, restricted)

    record = _operation_record(
        operation="subset",
        axis=axis,
        source_world_id=world.get("world_id"),
        restricted_paths=paths,
        include=operation.get("include"),
        exclude=operation.get("exclude"),
    )
    _append_operation_history(transformed, record)
    return OperationResult(
        status="applied",
        mode="deterministic",
        operation=copy.deepcopy(operation),
        transformed_world=transformed,
        operation_record=record,
    )


def _apply_product(
    world: dict[str, Any],
    operation: dict[str, Any],
) -> OperationResult:
    issues, axis, handle = _validate_axis_operation(world, operation, "product")
    other_world = operation.get("other_world")
    if not isinstance(other_world, dict):
        issues.append({"code": "other_world_missing", "message": "Product requires other_world."})
    elif axis not in _profile_axes(other_world, "product"):
        issues.append(
            {
                "code": "other_world_axis_not_declared",
                "message": f"Other world does not declare product axis: {axis}",
                "axis": axis,
            }
        )
    if issues:
        return _blocked_result(world, operation, issues)

    assert axis is not None
    assert handle is not None
    assert isinstance(other_world, dict)
    product = {
        "world_id": f"{world.get('world_id')}__product__{other_world.get('world_id')}",
        "name": (
            f"{world.get('name', world.get('world_id'))} product {other_world.get('name', other_world.get('world_id'))}"
        ),
        "task_unit": "Product world composed from two task worlds.",
        "operation_profile": _merge_operation_profiles(
            world.get("operation_profile", {}),
            other_world.get("operation_profile", {}),
        ),
        "operation_handles": _merge_operation_handles(
            world.get("operation_handles", {}),
            other_world.get("operation_handles", {}),
        ),
        "product_components": {
            "left": copy.deepcopy(world),
            "right": copy.deepcopy(other_world),
        },
    }
    record = _operation_record(
        operation="product",
        axis=axis,
        source_world_id=world.get("world_id"),
        other_world_id=other_world.get("world_id"),
    )
    _append_operation_history(product, record)
    return OperationResult(
        status="applied",
        mode="deterministic",
        operation=_operation_without_world_payload(operation),
        transformed_world=product,
        operation_record=record,
    )


def _validate_axis_operation(
    world: dict[str, Any],
    operation: dict[str, Any],
    operation_name: str,
) -> tuple[list[dict[str, Any]], str | None, dict[str, Any] | None]:
    axis = operation.get("axis")
    issues: list[dict[str, Any]] = []
    if not _has_text(axis):
        issues.append({"code": "axis_missing", "message": "Operation requires a non-empty axis."})
        return issues, None, None

    axes = _profile_axes(world, operation_name)
    if axis not in axes:
        issues.append(
            {
                "code": "axis_not_declared",
                "message": f"Axis is not declared for {operation_name}: {axis}",
                "axis": axis,
                "declared_axes": axes,
            }
        )

    handles = world.get("operation_handles", {})
    handle = handles.get(axis) if isinstance(handles, dict) else None
    if not isinstance(handle, dict):
        issues.append(
            {
                "code": "operation_handle_missing",
                "message": f"No operation handle declared for axis: {axis}",
                "axis": axis,
            }
        )
        return issues, str(axis), None

    paths = handle.get("paths")
    if not _is_nonempty_string_list(paths):
        issues.append(
            {
                "code": "operation_handle_paths_missing",
                "message": f"Operation handle has no paths: {axis}",
                "axis": axis,
            }
        )
        return issues, str(axis), None
    return issues, str(axis), handle


def _blocked_result(
    world: dict[str, Any],
    operation: dict[str, Any],
    issues: list[dict[str, Any]],
) -> OperationResult:
    return OperationResult(
        status="needs_orchestration",
        mode="agentic_orchestration",
        operation=_operation_without_world_payload(operation),
        transformed_world=None,
        issues=issues,
        orchestration_request=_orchestration_request(world, operation, issues),
    )


def _orchestration_request(
    world: dict[str, Any],
    operation: dict[str, Any],
    issues: list[dict[str, Any]],
) -> dict[str, Any]:
    profile = world.get("operation_profile", {})
    orchestration = profile.get("agentic_orchestration", {}) if isinstance(profile, dict) else {}
    allowed_actions = orchestration.get("allowed_actions", DEFAULT_ALLOWED_ACTIONS)
    if not _is_nonempty_string_list(allowed_actions):
        allowed_actions = DEFAULT_ALLOWED_ACTIONS
    handles = world.get("operation_handles", {})
    return {
        "reason": "deterministic_operation_blocked",
        "operation": _operation_without_world_payload(operation),
        "issues": copy.deepcopy(issues),
        "available_axes": _available_axes(world),
        "available_handles": sorted(handles) if isinstance(handles, dict) else [],
        "allowed_actions": list(allowed_actions),
        "guidance": orchestration.get(
            "guidance",
            "Use explicit handles when possible; otherwise propose a bounded schema or component repair.",
        ),
        "proposal_schema": operation_proposal_schema(),
    }


def _base_projected_world(world: dict[str, Any], axis: str) -> dict[str, Any]:
    world_id = world.get("world_id", "world")
    projected = {
        "world_id": f"{world_id}.projection.{axis}",
        "name": f"{world.get('name', world_id)} projection: {axis}",
        "task_unit": world.get("task_unit"),
        "operation_profile": {
            "projection_axes": [axis],
            "extension_policy": world.get("operation_profile", {}).get("extension_policy"),
        },
    }
    if "aboutme" in world:
        projected["aboutme"] = copy.deepcopy(world["aboutme"])
    return {key: value for key, value in projected.items() if value is not None}


def _profile_axes(world: dict[str, Any], operation_name: str) -> list[str]:
    field_name = OPERATION_AXIS_FIELDS[operation_name]
    profile = world.get("operation_profile", {})
    if not isinstance(profile, dict):
        return []
    value = profile.get(field_name, [])
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _available_axes(world: dict[str, Any]) -> dict[str, list[str]]:
    return {operation: _profile_axes(world, operation) for operation in OPERATION_AXIS_FIELDS}


def _missing_paths(world: dict[str, Any], paths: list[str]) -> list[str]:
    return [path for path in paths if _lookup(world, path) is MISSING]


def _path_missing_issue(path: str) -> dict[str, Any]:
    return {
        "code": "handle_path_missing",
        "message": f"Operation handle path is missing from world: {path}",
        "path": path,
    }


def _operation_record(**payload: Any) -> dict[str, Any]:
    return {"mode": "deterministic", **{key: value for key, value in payload.items() if value is not None}}


def _append_operation_history(world: dict[str, Any], record: dict[str, Any]) -> None:
    world.setdefault("operation_history", []).append(copy.deepcopy(record))


def _remove_axis(world: dict[str, Any], axis: str) -> None:
    handles = world.get("operation_handles")
    if isinstance(handles, dict):
        handles.pop(axis, None)
    profile = world.get("operation_profile")
    if not isinstance(profile, dict):
        return
    for field_name in OPERATION_AXIS_FIELDS.values():
        axes = profile.get(field_name)
        if isinstance(axes, list):
            profile[field_name] = [item for item in axes if item != axis]


def _restrict_value(
    value: Any,
    *,
    include: Any = None,
    exclude: Any = None,
) -> Any:
    include_set = set(include) if isinstance(include, list) else None
    exclude_set = set(exclude) if isinstance(exclude, list) else set()
    if isinstance(value, list):
        return [item for item in value if (include_set is None or item in include_set) and item not in exclude_set]
    if isinstance(value, dict):
        return {
            key: copy.deepcopy(item)
            for key, item in value.items()
            if (include_set is None or key in include_set) and key not in exclude_set
        }
    return MISSING


def _merge_operation_profiles(
    left: dict[str, Any],
    right: dict[str, Any],
) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for field_name in OPERATION_AXIS_FIELDS.values():
        merged[field_name] = sorted(set(_string_list(left.get(field_name))) | set(_string_list(right.get(field_name))))
    extension_policy = left.get("extension_policy") or right.get("extension_policy")
    if extension_policy:
        merged["extension_policy"] = extension_policy
    if "agentic_orchestration" in left or "agentic_orchestration" in right:
        merged["agentic_orchestration"] = copy.deepcopy(
            left.get("agentic_orchestration") or right.get("agentic_orchestration")
        )
    return merged


def _merge_operation_handles(
    left: dict[str, Any],
    right: dict[str, Any],
) -> dict[str, Any]:
    merged = copy.deepcopy(right)
    merged.update(copy.deepcopy(left))
    return merged


def _operation_without_world_payload(operation: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(operation)
    if "other_world" in result:
        other = result["other_world"]
        result["other_world_id"] = other.get("world_id") if isinstance(other, dict) else None
        result.pop("other_world", None)
    return result


def _lookup(data: dict[str, Any], path: str) -> Any:
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return MISSING
        current = current[part]
    return current


def _set_path(data: dict[str, Any], path: str, value: Any) -> None:
    current: Any = data
    parts = path.split(".")
    for part in parts[:-1]:
        if not isinstance(current, dict):
            return
        current = current.setdefault(part, {})
    if isinstance(current, dict):
        current[parts[-1]] = value


def _delete_path(data: dict[str, Any], path: str) -> None:
    current: Any = data
    parts = path.split(".")
    for part in parts[:-1]:
        if not isinstance(current, dict) or part not in current:
            return
        current = current[part]
    if isinstance(current, dict):
        current.pop(parts[-1], None)


def _is_nonempty_string_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(item, str) and item for item in value)


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _has_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())
