"""Specialized agents for the factory.

Each role binds its prompt (prompts.ROLE_PROMPTS) to an Agent instance wired
with the ModelRouter (so the right model class is selected per task type) and
the MCP toolset. The Orchestrator instantiates these via `build_agents`.
"""
from __future__ import annotations

from typing import Callable

from factory.agent import Agent, AgentContext
from factory.agents.prompts import ROLE_PROMPTS, ROLE_TASK_TYPE
from factory.llm import LLMClient
from factory.model_router import ModelRouter
from factory.mcp_base import MCPServer


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

    def available_tools(self) -> list[dict]:
        """Describe MCP tools available to this agent (for the LLM prompt)."""
        return [
            {"server": srv, "tool": t, "description": self._mcp[srv]._tools[t].description}
            for srv, mcp in self._mcp.items()
            for t in mcp.tool_names()
        ]


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
