"""Tests for the Orchestrator driving the DAG through fake agents + gates."""
import pytest

from factory.orchestrator import Orchestrator
from factory.guardrails import Gate, GateDecision
from factory.models import Artifact, ArtifactKind


def _make_agent(role, bus, produce):
    """Build a minimal fake Agent-like object compatible with the orchestrator."""
    from factory.agent import AgentContext

    class _FakeAgent:
        def __init__(self):
            self.role = role
            self.model_class = "coding"

        async def run(self, ctx: AgentContext):
            return produce(role, ctx)

    return _FakeAgent()


@pytest.mark.asyncio
async def test_orchestrator_runs_dag_in_order(tmp_path):
    from factory.task_dag import TaskDag

    bus = __import__("factory.bus", fromlist=["EventBus"]).EventBus(path=tmp_path / "e.jsonl")
    dag = TaskDag()
    dag.add("plan", deps=[], agent="planner")
    dag.add("impl", deps=["plan"], agent="backend")

    order = []

    def produce(role, ctx):
        order.append(role)
        return [Artifact(kind=ArtifactKind.CODE, path=f"{role}/o.md", content="x", agent=role)]

    agents = {
        "planner": _make_agent("planner", bus, produce),
        "backend": _make_agent("backend", bus, produce),
    }
    orch = Orchestrator(dag=dag, agents=agents, bus=bus, gates={})

    result = await orch.run(requirement="build X")
    assert result.success is True
    assert order == ["planner", "backend"]  # topological order
    assert dag.is_complete()


@pytest.mark.asyncio
async def test_orchestrator_blocks_on_hitl_gate(tmp_path):
    from factory.task_dag import TaskDag

    bus = __import__("factory.bus", fromlist=["EventBus"]).EventBus(path=tmp_path / "e.jsonl")
    dag = TaskDag()
    dag.add("plan", deps=[], agent="planner")
    dag.add("release", deps=["plan"], agent="reviewer")

    def produce(role, ctx):
        return [Artifact(kind=ArtifactKind.CODE, path=f"{role}/o.md", content="x", agent=role)]

    agents = {
        "planner": _make_agent("planner", bus, produce),
        "reviewer": _make_agent("reviewer", bus, produce),
    }
    # release gate is BLOCKED (not approved) by default
    gates = {"release": Gate(name="release", mandatory=True)}
    orch = Orchestrator(dag=dag, agents=agents, bus=bus, gates=gates)
    result = await orch.run(requirement="X")
    # planner ran, release blocked -> run not successful
    assert result.success is False
    assert gates["release"].decide() == GateDecision.BLOCK
    # after approval, a re-run would pass
    gates["release"].approve(by="human")
    assert gates["release"].decide() == GateDecision.ALLOW
