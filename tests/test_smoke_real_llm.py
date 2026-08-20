"""Smoke tests against REAL LLM providers.

Skipped unless invoked with `pytest -m smoke`. These are the only tests that
actually call the network + spend tokens. They validate the adapter + a real
agent end to end on a tiny task.
"""
import pytest

from factory.agents import build_agents
from factory.agent import AgentContext
from factory.llm import build_client
from factory.model_router import ModelRouter

pytestmark = pytest.mark.smoke


@pytest.mark.asyncio
async def test_backend_agent_zen():
    """Call the real OpenCode Zen / big-pickle LLM via the backend agent."""
    client = build_client("zen")
    agents = build_agents(client, ModelRouter())
    ctx = AgentContext(requirement="Write a one-line Python function that adds two numbers.")
    artifacts = await agents["backend"].run(ctx)
    assert artifacts and artifacts[0].content.strip()
    print("\n[smoke|zen] backend output:\n", artifacts[0].content[:300])


@pytest.mark.asyncio
async def test_backend_agent_nous():
    """Call the real Hermes/Nous tencent/hy3:free LLM via the backend agent."""
    client = build_client("nous")
    agents = build_agents(client, ModelRouter())
    ctx = AgentContext(requirement="Reply with the single word: pong")
    artifacts = await agents["backend"].run(ctx)
    assert artifacts and artifacts[0].content.strip()
    print("\n[smoke|nous] backend output:\n", artifacts[0].content[:300])
