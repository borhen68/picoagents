from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


@dataclass(slots=True)
class ToolResult:
    output: str
    success: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ToolContext:
    workspace_root: Path
    session_id: str | None = None


class Tool(Protocol):
    name: str
    description: str
    parameters: dict[str, Any]

    async def run(self, args: dict[str, Any], context: ToolContext) -> ToolResult:
        ...


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise KeyError(f"unknown tool: {name}")
        return self._tools[name]

    def names(self) -> list[str]:
        return sorted(self._tools)

    def docs(self) -> dict[str, str]:
        return {name: tool.description for name, tool in self._tools.items()}

    async def run(self, name: str, args: dict[str, Any], context: ToolContext) -> ToolResult:
        tool = self.get(name)
        schema = getattr(tool, "parameters", None)
        if isinstance(schema, dict):
            errors = validate_params(args, schema)
            if errors:
                return ToolResult(
                    output=f"invalid parameters for tool '{name}': " + "; ".join(errors),
                    success=False,
                    metadata={"validation_errors": errors},
                )
        return await tool.run(args, context)


_TYPE_MAP: dict[str, Any] = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "array": list,
    "object": dict,
}


def validate_params(params: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    root = dict(schema)
    root.setdefault("type", "object")
    if root.get("type") != "object":
        return [f"schema root must be object, got {root.get('type')!r}"]
    return _validate(params, root, "")


def _validate(value: Any, schema: dict[str, Any], path: str) -> list[str]:
    type_name = schema.get("type")
    label = path or "parameter"
    errors: list[str] = []

    if type_name in _TYPE_MAP and not isinstance(value, _TYPE_MAP[type_name]):
        return [f"{label} should be {type_name}"]

    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{label} must be one of {schema['enum']}")

    if type_name in ("integer", "number"):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{label} must be >= {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{label} must be <= {schema['maximum']}")

    if type_name == "string":
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"{label} must be at least {schema['minLength']} chars")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append(f"{label} must be at most {schema['maxLength']} chars")

    if type_name == "object":
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"missing required {path + '.' + key if path else key}")
        for key, sub_value in value.items():
            if key in props:
                errors.extend(_validate(sub_value, props[key], path + "." + key if path else key))

    if type_name == "array" and "items" in schema:
        for idx, item in enumerate(value):
            child_path = f"{path}[{idx}]" if path else f"[{idx}]"
            errors.extend(_validate(item, schema["items"], child_path))

    return errors
