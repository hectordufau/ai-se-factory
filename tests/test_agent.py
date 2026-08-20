"""Tests for the Agent base class using fakes (no real LLM)."""
from unittest.mock import AsyncMock

import pytest

from factory.agent import Agent, AgentContext
from factory.bus import EventBus
from factory.models import Artifact, ArtifactKind


class FakeTool:
    def __init__(self):
        self.calls = []

    async def run(self, name: str, **kwargs):
        self.calls.append((name, kwargs))
        return f"ran:{name}"


@pytest.mark.asyncio
async def test_agent_emits_artifact_and_event(tmp_path):
    bus = EventBus(path=tmp_path / "events.jsonl")

    async def fake_complete(messages, model=None, **kw):
        # echo the last user message as the "code" artifact content
        last = [m for m in messages if m["role"] == "user"][-1]["content"]
        return f"# generated\n{last}"

    tool = FakeTool()
    agent = Agent(
        role="backend",
        system_prompt="You are a backend engineer.",
        complete=fake_complete,
        tools={"echo": tool.run},
        bus=bus,
    )
    ctx = AgentContext(requirement="build payments API", upstream_artifacts=[])
    artifacts = await agent.run(ctx)

    assert len(artifacts) >= 1
    assert any(a.kind == ArtifactKind.CODE for a in artifacts)
    # event published to the bus
    events = bus.read_all()
    assert any(e["type"] == "agent.done" and e["agent"] == "backend" for e in events)
    assert tool.calls  # tool was invoked


@pytest.mark.asyncio
async def test_agent_uses_scoped_context(tmp_path):
    bus = EventBus(path=tmp_path / "events.jsonl")

    async def fake_complete(messages, model=None, **kw):
        # the agent should only see its own system + scoped user context
        assert messages[0]["role"] == "system"
        assert "backend" in messages[0]["content"]
        return "ok"

    agent = Agent(role="backend", system_prompt="backend", complete=fake_complete, tools={}, bus=bus)
    ctx = AgentContext(requirement="x", upstream_artifacts=[])
    await agent.run(ctx)
