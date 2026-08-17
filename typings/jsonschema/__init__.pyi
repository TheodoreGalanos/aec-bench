# ABOUTME: Supplies the typed JSON Schema validator surface used by the native tool gateway.
# ABOUTME: Keeps strict type checking independent of the optional third-party stub package.

from collections.abc import Mapping
from typing import Any, ClassVar

class Draft202012Validator:
    META_SCHEMA: ClassVar[Mapping[str, Any]]

    def __init__(self, schema: Mapping[str, Any]) -> None: ...
    @classmethod
    def check_schema(cls, schema: Mapping[str, Any]) -> None: ...
    def validate(self, instance: object) -> None: ...
