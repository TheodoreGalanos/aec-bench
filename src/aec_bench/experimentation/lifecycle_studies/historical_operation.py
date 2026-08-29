# ABOUTME: Validates captured schema-1 lifecycle operation tool contracts against their retained bytes.
# ABOUTME: Accepts historical JSON Schema metadata without binding validation to the current protocol source.

from __future__ import annotations

import ast
import hashlib
import json
from typing import Any

from aec_bench.contracts.trial_record import ArtifactReference


def validate_captured_lifecycle_operation_interaction(
    protocol: dict[str, Any],
    tool_schema: list[Any],
) -> tuple[str, str]:
    """Validate a captured operation contract without current source-code identity."""
    if set(protocol) != {"schema_version", "sha256", "tool", "tool_schema_sha256"}:
        raise ValueError("captured lifecycle operation protocol fields are malformed")
    schema_version = protocol.get("schema_version")
    protocol_sha256 = protocol.get("sha256")
    tool_schema_sha256 = protocol.get("tool_schema_sha256")
    tool = protocol.get("tool")
    if not isinstance(schema_version, str) or not schema_version.strip():
        raise ValueError("captured lifecycle operation protocol version is malformed")
    if not isinstance(protocol_sha256, str) or not isinstance(tool_schema_sha256, str):
        raise ValueError("captured lifecycle operation protocol hashes are malformed")
    ArtifactReference.validate_sha256(protocol_sha256)
    ArtifactReference.validate_sha256(tool_schema_sha256)
    if not isinstance(tool, dict) or set(tool) != {"name", "arguments"}:
        raise ValueError("captured lifecycle operation tool identity is malformed")
    tool_name = tool.get("name")
    raw_arguments = tool.get("arguments")
    if not isinstance(tool_name, str) or not tool_name.strip() or not isinstance(raw_arguments, list):
        raise ValueError("captured lifecycle operation tool identity is malformed")
    arguments = tuple(raw_arguments)
    if (
        not arguments
        or any(not isinstance(argument, str) or not argument.strip() for argument in arguments)
        or len(arguments) != len(set(arguments))
    ):
        raise ValueError("captured lifecycle operation tool arguments are malformed")
    matching_tools = [item for item in tool_schema if isinstance(item, dict) and item.get("name") == tool_name]
    if len(matching_tools) != 1 or _captured_tool_arguments(matching_tools[0]) != arguments:
        raise ValueError("captured lifecycle operation protocol does not match its tool schema")
    encoded_tool_schema = json.dumps(tool_schema, sort_keys=True, separators=(",", ":")).encode("utf-8")
    actual_tool_schema_sha256 = hashlib.sha256(encoded_tool_schema).hexdigest()
    if tool_schema_sha256 != actual_tool_schema_sha256:
        raise ValueError("captured lifecycle operation tool schema hash is inconsistent")
    return protocol_sha256, actual_tool_schema_sha256


def _captured_tool_arguments(tool: dict[str, Any]) -> tuple[str, ...]:
    has_signature = "signature" in tool
    has_parameters = "parameters" in tool
    if has_signature == has_parameters:
        raise ValueError("captured lifecycle operation tool schema representation is malformed")
    if has_signature:
        if not set(tool).issubset({"name", "signature", "description"}) or (
            "description" in tool and not isinstance(tool["description"], str)
        ):
            raise ValueError("captured lifecycle operation signature metadata is malformed")
        signature = tool["signature"]
        if not isinstance(signature, str) or not signature.strip():
            raise ValueError("captured lifecycle operation signature is malformed")
        try:
            parsed = ast.parse(f"def _captured{signature}:\n    pass\n")
        except SyntaxError as exc:
            raise ValueError("captured lifecycle operation signature is malformed") from exc
        if len(parsed.body) != 1 or not isinstance(parsed.body[0], ast.FunctionDef):
            raise ValueError("captured lifecycle operation signature is malformed")
        arguments = parsed.body[0].args
        if (
            arguments.posonlyargs
            or arguments.vararg is not None
            or arguments.kwonlyargs
            or arguments.kwarg is not None
            or arguments.defaults
            or arguments.kw_defaults
            or any(not _is_captured_string_annotation(argument.annotation) for argument in arguments.args)
        ):
            raise ValueError("captured lifecycle operation signature is malformed")
        return tuple(argument.arg for argument in arguments.args)
    parameters = tool["parameters"]
    if not set(tool).issubset({"name", "parameters", "description"}) or (
        "description" in tool and not isinstance(tool["description"], str)
    ):
        raise ValueError("captured lifecycle operation parameter metadata is malformed")
    if not isinstance(parameters, dict) or parameters.get("type") != "object":
        raise ValueError("captured lifecycle operation parameters are malformed")
    properties = parameters.get("properties")
    required = parameters.get("required")
    if (
        not isinstance(properties, dict)
        or not isinstance(required, list)
        or not set(parameters).issubset({"type", "properties", "required", "additionalProperties", "title"})
        or ("title" in parameters and not isinstance(parameters["title"], str))
        or parameters.get("additionalProperties", False) is not False
        or set(properties) != set(required)
        or any(not isinstance(item, str) for item in required)
        or any(
            not isinstance(value, dict)
            or value.get("type") != "string"
            or not set(value).issubset({"type", "title"})
            or ("title" in value and not isinstance(value["title"], str))
            for value in properties.values()
        )
    ):
        raise ValueError("captured lifecycle operation parameters are malformed")
    return tuple(required)


def _is_captured_string_annotation(annotation: ast.expr | None) -> bool:
    return (isinstance(annotation, ast.Name) and annotation.id == "str") or (
        isinstance(annotation, ast.Constant) and annotation.value == "str"
    )
