from __future__ import annotations

from typing import Any

from picoagent.agent.tools.registry import ToolContext, ToolRegistry, ToolResult, validate_params


class SampleTool:
    name = "sample"
    description = "sample tool"
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "minLength": 2},
            "count": {"type": "integer", "minimum": 1, "maximum": 10},
            "mode": {"type": "string", "enum": ["fast", "full"]},
            "meta": {
                "type": "object",
                "properties": {
                    "tag": {"type": "string"},
                    "flags": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["tag"],
            },
        },
        "required": ["query", "count"],
    }

    async def run(self, args: dict[str, Any], context: ToolContext) -> ToolResult:
        return ToolResult(output="ok", success=True)


def test_validate_params_missing_required() -> None:
    errors = validate_params({"query": "hi"}, SampleTool.parameters)
    assert "missing required count" in "; ".join(errors)


def test_validate_params_type_and_range() -> None:
    errors = validate_params({"query": "hi", "count": 0}, SampleTool.parameters)
    assert any("count must be >= 1" in e for e in errors)

    errors = validate_params({"query": "hi", "count": "2"}, SampleTool.parameters)
    assert any("count should be integer" in e for e in errors)


def test_validate_params_enum_and_min_length() -> None:
    errors = validate_params({"query": "h", "count": 2, "mode": "slow"}, SampleTool.parameters)
    assert any("query must be at least 2 chars" in e for e in errors)
    assert any("mode must be one of" in e for e in errors)


def test_validate_params_nested_object_and_array() -> None:
    errors = validate_params(
        {
            "query": "hi",
            "count": 2,
            "meta": {"flags": [1, "ok"]},
        },
        SampleTool.parameters,
    )
    assert any("missing required meta.tag" in e for e in errors)
    assert any("meta.flags[0] should be string" in e for e in errors)


def test_registry_returns_validation_error() -> None:
    import asyncio
    from pathlib import Path

    reg = ToolRegistry()
    reg.register(SampleTool())

    result = asyncio.run(reg.run("sample", {"query": "hi"}, ToolContext(workspace_root=Path("."))))
    assert result.success is False
    assert "invalid parameters" in result.output
