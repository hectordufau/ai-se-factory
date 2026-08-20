"""MCP (Model Context Protocol) base layer for the factory.

An MCPServer exposes a set of named `Tool`s an agent may invoke. This is a
lightweight, in-process implementation of the MCP *concept* (tools + resources
+ scoped context) that the IgniteTech role explicitly requires. Each server is
scoped (e.g. a filesystem server rooted at a worktree) so agents only touch
what they are allowed to.

Real MCP transports (stdio/HTTP) can be added later; the agent-facing
interface (`server.call(name, args)`) stays identical.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


class ToolError(Exception):
    """Raised when an MCP tool call fails or is not permitted."""


@dataclass
class Tool:
    name: str
    description: str
    handler: Callable[[dict], dict]
    # Optional allow-list of argument keys; if set, unknown keys are rejected.
    allowed_args: Optional[list[str]] = None

    def run(self, args: dict) -> dict:
        if self.allowed_args is not None:
            for k in args:
                if k not in self.allowed_args:
                    raise ToolError(f"Tool {self.name!r} does not accept arg {k!r}")
        return self.handler(args or {})


class MCPServer:
    __test__ = False  # prevent pytest from collecting server classes as test cases

    def __init__(self, name: str) -> None:
        self.name = name
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def tool_names(self) -> list[str]:
        return sorted(self._tools)

    def call(self, name: str, args: Optional[dict] = None) -> dict:
        tool = self._tools.get(name)
        if tool is None:
            raise ToolError(f"Unknown tool {name!r} on server {self.name!r}")
        return tool.run(args or {})
