"""Tests for the MCP base protocol (Tool + MCPServer)."""
import pytest

from factory.mcp_base import MCPServer, Tool, ToolError


def test_tool_call_invokes_handler():
    called = {}

    def _handler(args):
        called["args"] = args
        return {"ok": True, "echo": args.get("x")}

    tool = Tool(name="echo", description="echo", handler=_handler)
    assert tool.name == "echo"
    res = tool.run({"x": 1})
    assert res == {"ok": True, "echo": 1}
    assert called["args"] == {"x": 1}


def test_server_dispatches_by_name():
    srv = MCPServer(name="test")

    def a(args):
        return {"v": "a"}

    def b(args):
        return {"v": "b"}

    srv.register(Tool("a", "desc", a))
    srv.register(Tool("b", "desc", b))
    assert srv.call("a", {}) == {"v": "a"}
    assert srv.call("b", {}) == {"v": "b"}
    assert set(srv.tool_names()) == {"a", "b"}


def test_server_unknown_tool_raises():
    srv = MCPServer(name="test")
    with pytest.raises(ToolError):
        srv.call("missing", {})
