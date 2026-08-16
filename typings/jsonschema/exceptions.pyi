# ABOUTME: Types the JSON Schema exceptions inspected by the native tool gateway.
# ABOUTME: Exposes the stable message attribute used in gateway validation errors.

class SchemaError(Exception):
    message: str

class ValidationError(Exception):
    message: str
