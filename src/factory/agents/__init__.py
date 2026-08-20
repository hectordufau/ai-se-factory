"""Specialized agents for the factory.

Each role binds its prompt (prompts.ROLE_PROMPTS) to an Agent instance wired
with the ModelRouter (so the right model class is selected per task type) and
the MCP toolset. The Orchestrator instantiates these via `build_agents`.
"""
from __future__ import annotations

from typing import Callable

from factory.agent import Agent, AgentContext
from factory.agents.prompts import ROLE_PROMPTS, ROLE_TASK_TYPE
from factory.guardrails import RoleScope
from factory.llm import LLMClient
from factory.model_router import ModelRouter
from factory.mcp_base import MCPServer
from factory.models import Artifact, ArtifactKind


class RoleAgent(Agent):
    """An Agent that routes its LLM calls through the ModelRouter by role."""

    def __init__(
        self,
        role: str,
        client: LLMClient,
        router: ModelRouter,
        tools: dict | None = None,
        bus=None,
    ) -> None:
        self._client = client
        self._router = router
        self._mcp: dict[str, MCPServer] = {}
        self._scope = RoleScope.for_role(role)
        self.task_type = ROLE_TASK_TYPE.get(role, "coding")
        model_class = router.select(self.task_type).model_class
        super().__init__(
            role=role,
            system_prompt=ROLE_PROMPTS.get(role, f"You are the {role} agent."),
            complete=self._complete,
            tools=tools,
            bus=bus,
            model_class=model_class,
        )

    async def _complete(self, messages, model=None, **kw):
        task_type = ROLE_TASK_TYPE.get(self.role, "coding")
        return await self._router.complete_for_task(self._client, task_type, messages, **kw)

    # --- File-writing support (Nível B): parse a <<<FILES>>> block from the
    # LLM output and persist each file via the scoped FilesystemMCP. ---
    def _parse_files(self, text: str) -> list[tuple[str, str]]:
        files: list[tuple[str, str]] = []
        marker = "<<<FILES>>>"
        if marker not in text:
            return files
        body = text.split(marker, 1)[1]
        for chunk in body.split("<<<END>>>"):
            chunk = chunk.strip()
            if not chunk:
                continue
            # format: PATH: <relpath>\n```\n<content>\n```
            if not chunk.startswith("PATH:"):
                continue
            line, _, rest = chunk.partition("\n")
            path = line[len("PATH:"):].strip()
            # strip surrounding code fences
            rest = rest.strip()
            if rest.startswith("```"):
                rest = rest[3:]
                if rest.endswith("```"):
                    rest = rest[:-3]
            files.append((path, rest.strip()))
        return files

    async def write_files(self, text: str) -> list[Artifact]:
        """Persist any files the LLM produced, via the scoped filesystem MCP."""
        if "filesystem" not in self._mcp:
            return []
        out: list[Artifact] = []
        for path, content in self._parse_files(text):
            try:
                self.call_mcp("filesystem", "write_file", {"path": path, "content": content})
                out.append(
                    Artifact(
                        kind=ArtifactKind.CODE,
                        path=path,
                        content=content,
                        agent=self.role,
                        meta={"tool": "filesystem.write"},
                    )
                )
            except Exception:
                # scope/IO errors are surfaced as failed artifacts
                out.append(
                    Artifact(
                        kind=ArtifactKind.CODE,
                        path=path,
                        content=content,
                        agent=self.role,
                        meta={"tool": "filesystem.write", "error": "write_failed"},
                    )
                )
        return out

    async def run(self, ctx: AgentContext) -> list[Artifact]:
        """Run the agent, then persist any files it produced via MCP.

        Falls back to the base Agent.run (text-only artifacts) when no
        filesystem MCP is wired in.
        """
        artifacts = await super().run(ctx)
        if "filesystem" in self._mcp:
            # re-run is cheap; we parse the last text artifact for file blocks
            last_text = next(
                (a.content for a in reversed(artifacts)
                 if a.kind in (ArtifactKind.CODE, ArtifactKind.REPORT)),
                "",
            )
            written = await self.write_files(last_text)
            artifacts.extend(written)
        return artifacts

    def available_tools(self) -> list[dict]:
        """Describe MCP tools available to this agent (for the LLM prompt)."""
        return [
            {"server": srv, "tool": t, "description": self._mcp[srv]._tools[t].description}
            for srv, mcp in self._mcp.items()
            for t in mcp.tool_names()
        ]

    def call_mcp(self, server: str, tool: str, args: dict | None = None) -> dict:
        """Invoke an MCP tool, enforcing this role's scope (guardrail)."""
        self._scope.enforce(server, tool)
        mcp = self._mcp.get(server)
        if mcp is None:
            from factory.mcp_base import ToolError

            raise ToolError(f"MCP server {server!r} not available to role {self.role!r}")
        return mcp.call(tool, args)


def build_agents(
    client: LLMClient,
    router: ModelRouter,
    mcp_bundle: dict[str, "MCPServer"] | None = None,
    bus=None,
) -> dict[str, RoleAgent]:
    """Instantiate all 8 specialized agents.

    `mcp_bundle` maps server-name -> MCPServer; every agent gets the same
    bundle here (the Orchestrator can later scope per-agent). Agent roles map
    1:1 to ROLE_PROMPTS keys.
    """
    agents = {}
    for role in ROLE_PROMPTS.keys():
        agent = RoleAgent(role, client, router, bus=bus)
        agent._mcp = mcp_bundle or {}
        agents[role] = agent
    return agents
