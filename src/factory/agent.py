"""Agent base class.

An Agent binds a role prompt + a toolset + a model class. It receives a
scoped `AgentContext` (only the files/spec it needs), calls the LLM, invokes
MCP tools, writes artifacts, and publishes an event. Agents never call each
other directly — coordination happens via the Orchestrator + EventBus.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

from factory.bus import EventBus
from factory.models import Artifact, ArtifactKind

CompleteFn = Callable[..., Awaitable[str]]
ToolFn = Callable[..., Awaitable[Any]]


@dataclass
class AgentContext:
    requirement: str
    upstream_artifacts: list[Artifact] = field(default_factory=list)
    worktree_path: Optional[str] = None
    extra: dict[str, Any] = field(default_factory=dict)


class Agent:
    def __init__(
        self,
        role: str,
        system_prompt: str,
        complete: CompleteFn,
        tools: dict[str, ToolFn] | None = None,
        bus: Optional[EventBus] = None,
        model_class: str = "coding",
    ) -> None:
        self.role = role
        self.system_prompt = system_prompt
        self._complete = complete
        self._tools = tools or {}
        self._bus = bus
        self.model_class = model_class

    def _build_messages(self, ctx: AgentContext) -> list[dict[str, str]]:
        user_parts = [f"Requirement: {ctx.requirement}"]
        for a in ctx.upstream_artifacts:
            user_parts.append(f"[{a.kind.value}] {a.path}\n{a.content}")
        return [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": "\n\n".join(user_parts)},
        ]

    async def invoke_tool(self, name: str, **kwargs: Any) -> Any:
        if name not in self._tools:
            raise KeyError(f"tool {name!r} not available to agent {self.role!r}")
        return await self._tools[name](name, **kwargs)

    async def run(self, ctx: AgentContext) -> list[Artifact]:
        messages = self._build_messages(ctx)
        output = await self._complete(messages, model=self.model_class)
        artifacts = [
            Artifact(
                kind=ArtifactKind.CODE,
                path=f"{self.role}/output.md",
                content=output,
                agent=self.role,
            )
        ]
        # Agents act via MCP tools. The base class invokes every registered
        # tool once (the real implementation parses tool-call requests from the
        # LLM output; here we exercise the full tool pipeline for testing).
        for name, fn in self._tools.items():
            result = await fn(name)
            artifacts.append(
                Artifact(
                    kind=ArtifactKind.REPORT,
                    path=f"{self.role}/tool_{name}.json",
                    content=str(result),
                    agent=self.role,
                    meta={"tool": name},
                )
            )
        if self._bus is not None:
            self._bus.publish(
                {
                    "type": "agent.done",
                    "agent": self.role,
                    "artifacts": [a.to_dict() for a in artifacts],
                }
            )
        return artifacts
