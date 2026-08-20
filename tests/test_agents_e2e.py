"""Phase 2 E2E test: full DAG driven by specialized RoleAgents with a mocked LLM.

No real network/LLM calls. Validates that the Fase-1 Orchestrator + Fase-2
agents + HITL gates work together end to end.
"""
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from factory.agents import build_agents
from factory.bus import EventBus
from factory.guardrails import Gate
from factory.llm import LLMClient, build_client
from factory.models import Artifact, ArtifactKind
from factory.orchestrator import Orchestrator
from factory.task_dag import TaskDag


def _make_client(reply_fn) -> LLMClient:
    """Build an LLMClient whose HTTP layer is a fake (no network, no auth)."""
    client = LLMClient(base_url="https://opencode.ai/zen/v1", default_model="big-pickle", api_key="sk-test")
    async def _complete(messages, model=None, **kw):
        return reply_fn(messages, model)
    client.complete = _complete
    return client


def _planner_reply(messages, model):
    # always return a valid DAG
    return json.dumps(
        {
            "tasks": [
                {"id": "arch", "agent": "architect", "deps": [], "description": "design"},
                {"id": "backend", "agent": "backend", "deps": ["arch"], "description": "impl"},
                {"id": "release", "agent": "reviewer", "deps": ["backend"], "description": "review"},
            ]
        }
    )


@pytest.mark.asyncio
async def test_full_factory_run_with_hitl(tmp_path):
    bus = EventBus(path=tmp_path / "e.jsonl")

    # every agent replies with a short artifact body; planner returns the DAG
    def reply(messages, model):
        role = "planner" if any("PLANNER" in m["content"] for m in messages if m["role"] == "system") else "worker"
        if role == "planner":
            return _planner_reply(messages, model)
        return f"# {role} output\ndone"

    client = _make_client(reply)
    from factory.model_router import ModelRouter

    router = ModelRouter()
    agents = build_agents(client, router, bus=bus)

    # The planner is invoked separately by the CLI/entrypoint to build the DAG.
    # Here we inject the DAG directly to test the orchestration of the rest.
    dag = TaskDag()
    dag.add("arch", deps=[], agent="architect")
    dag.add("backend", deps=["arch"], agent="backend")
    dag.add("release", deps=["backend"], agent="reviewer")

    gates = {"release": Gate(name="release", mandatory=True)}
    orch = Orchestrator(dag=dag, agents=agents, bus=bus, gates=gates)

    # First run: release blocked by HITL
    result = await orch.run(requirement="build a payments API")
    assert result.success is False
    assert gates["release"].decide().value == "block"

    # Human approves
    gates["release"].approve(by="human")
    result2 = await orch.run(requirement="build a payments API")
    assert result2.success is True
    assert dag.is_complete()
    # all 8 role artifacts? we only ran 3 roles; ensure those present
    roles_seen = {a.agent for a in result2.artifacts}
    assert {"architect", "backend", "reviewer"} <= roles_seen


@pytest.mark.asyncio
async def test_build_agents_has_all_roles():
    client = build_client("zen", client=MagicMock())
    from factory.model_router import ModelRouter

    agents = build_agents(client, ModelRouter())
    assert set(agents.keys()) == {
        "planner", "architect", "backend", "frontend",
        "database", "qa", "security", "reviewer",
    }
    # each agent carries the correct model_class via router task type
    assert agents["architect"].model_class == "reasoning"
    assert agents["backend"].model_class == "coding"
    assert agents["qa"].model_class == "coding"
