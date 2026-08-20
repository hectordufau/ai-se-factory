"""E2E tests for guardrails wired into the Orchestrator + RoleAgent.

No LLM/network: agents are fakes that optionally raise or attempt illegal MCP.
"""
from unittest.mock import MagicMock

import pytest

from factory.agents import build_agents
from factory.agent import AgentContext
from factory.bus import EventBus
from factory.guardrails import Gate, GateDecision, GuardrailViolation
from factory.llm import LLMClient
from factory.model_router import ModelRouter
from factory.orchestrator import Orchestrator
from factory.task_dag import TaskDag


def _make_client(reply_fn) -> LLMClient:
    client = LLMClient(base_url="https://x", default_model="m", api_key="k")
    async def _complete(messages, model=None, **kw):
        return reply_fn(messages, model)
    client.complete = _complete
    return client


def _dag_two():
    dag = TaskDag()
    dag.add("architect", deps=[], agent="architect")
    dag.add("backend", deps=["architect"], agent="backend")
    return dag


async def test_required_gate_blocks_coding_until_approved():
    dag = _dag_two()
    agents = build_agents(_make_client(lambda m, model: "ok"), ModelRouter())
    gates = {"architect": Gate(name="architect", mandatory=True)}
    orch = Orchestrator(dag, agents, gates=gates, required_gates={"backend": "architect"})
    res1 = await orch.run("build api")
    # backend cannot run until arch gate approved
    assert dag.status("backend") != "done"
    assert res1.success is False
    gates["architect"].approve(by="human")
    res2 = await orch.run("build api")
    assert res2.success is True
    assert dag.is_complete()


async def test_role_scope_blocks_illegal_mcp_call():
    agents = build_agents(_make_client(lambda m, model: "ok"), ModelRouter())
    backend = agents["backend"]
    # backend is not allowed to use github MCP
    with pytest.raises(GuardrailViolation):
        backend.call_mcp("github", "open_pr", {"title": "x", "body": "", "head": "h", "base": "main"})


async def test_circuit_breaker_fails_persistent_error_task():
    dag = _dag_two()
    # only backend crashes; architect succeeds -> backend should trip breaker
    def maybe_boom(m, model):
        # the orchestrator calls complete with model class; we can't see role
        # directly, so crash only on the 2nd+ call (backend runs after arch).
        maybe_boom.calls += 1
        if maybe_boom.calls >= 2:
            raise RuntimeError("agent crashed")
        return "ok"

    maybe_boom.calls = 0
    agents = build_agents(_make_client(maybe_boom), ModelRouter())
    orch = Orchestrator(dag, agents, max_attempts=2)
    res = await orch.run("build api")
    # architect ok, backend eventually fails via breaker
    assert dag.status("backend") == "failed"
    assert res.success is False
