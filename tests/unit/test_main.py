import pytest
from src.mcp_server import mcp


def test_mcp_tool_registration():
    """Verify that tools are correctly registered with FastMCP."""
    # FastMCP stores tools in ._tool_manager._tools (internal API, but useful for verification)
    # Or typically exposes list_tools()

    tools = mcp._tool_manager.list_tools()
    tool_names = [t.name for t in tools]

    assert "get_tasks" in tool_names
    assert "create_task" in tool_names


def test_get_tasks_metadata():
    """Verify tool metadata (description, args)."""
    tools = mcp._tool_manager.list_tools()
    tool = next(t for t in tools if t.name == "get_tasks")

    assert "工作项" in tool.description or "task" in tool.description.lower()
    # tool.parameters is the JSON Schema dict
    assert "project" in tool.parameters["properties"]
    # project is now optional (uses FEISHU_PROJECT_KEY as default)
    # so required may be empty or not include "project"
    required = tool.parameters.get("required", [])
    assert "project" not in required or required == []
