"""Orchestrator — drives the Task DAG through specialized agents.

Coordinates:
- topological scheduling (TaskDag.ready())
- per-agent scoped context (upstream artifacts only)
- HITL gates (block a task until approved)
- append-only event log (EventBus)
- collects Artifacts + builds a RunResult
"""
from __future__ import annotations

from typing import Optional

from factory.agent import AgentContext
from factory.bus import EventBus
from factory.guardrails import Gate
from factory.models import Artifact, RunResult, TaskStatus
from factory.task_dag import TaskDag


class Orchestrator:
    def __init__(
        self,
        dag: TaskDag,
        agents: dict[str, object],
        bus: Optional[EventBus] = None,
        gates: Optional[dict[str, Gate]] = None,
    ) -> None:
        self.dag = dag
        self.agents = agents
        self.bus = bus
        self.gates = gates or {}

    async def run(self, requirement: str) -> RunResult:
        result = RunResult(requirement=requirement)
        failed = False
        # topological waves
        while not self.dag.is_complete():
            ready = self.dag.ready()
            if not ready:
                # nothing ready but not complete -> deadlock/blocked gates
                break
            for task_id in sorted(ready):
                task = next(t for t in self.dag.tasks() if t.id == task_id)
                # HITL gate?
                gate = self.gates.get(task_id)
                if gate is not None and gate.decide().value == "block":
                    self.dag.mark_running(task_id)
                    if self.bus:
                        self.bus.publish({"type": "gate.blocked", "task": task_id, "gate": gate.name})
                    continue
                self.dag.mark_running(task_id)
                agent = self.agents.get(task.agent)
                if agent is None:
                    self.dag.mark_failed(task_id)
                    failed = True
                    continue
                # scoped context: only upstream (done) tasks' artifacts
                upstream: list[Artifact] = [
                    a
                    for t in self.dag.tasks()
                    if t.id in task.deps and t.status == TaskStatus.DONE
                    for a in result.artifacts
                    if a.agent == t.agent
                ]
                ctx = AgentContext(requirement=requirement, upstream_artifacts=upstream)
                try:
                    artifacts = await agent.run(ctx)
                    result.artifacts.extend(artifacts)
                    self.dag.mark_done(task_id)
                except Exception:
                    self.dag.mark_failed(task_id)
                    failed = True
        # success requires all tasks done and no failures
        result.success = (not failed) and self.dag.is_complete()
        if self.bus:
            self.bus.publish(
                {"type": "run.done", "success": result.success, "run_id": result.run_id}
            )
        return result
