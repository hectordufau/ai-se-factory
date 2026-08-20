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
from factory.evals.eval import EvalHarness
from factory.guardrails import CircuitBreaker, Gate
from factory.models import Artifact, RunResult, TaskStatus
from factory.task_dag import TaskDag


class Orchestrator:
    def __init__(
        self,
        dag: TaskDag,
        agents: dict[str, object],
        bus: Optional[EventBus] = None,
        gates: Optional[dict[str, Gate]] = None,
        # task_id -> gate that must be approved before the task may run
        required_gates: Optional[dict[str, str]] = None,
        # max retries per task before the circuit breaker trips
        max_attempts: int = 3,
    ) -> None:
        self.dag = dag
        self.agents = agents
        self.bus = bus
        self.gates = gates or {}
        self.required_gates = required_gates or {}
        self.max_attempts = max_attempts
        self._breakers: dict[str, CircuitBreaker] = {}
        self._result: Optional[RunResult] = None

    def _breaker(self, task_id: str) -> CircuitBreaker:
        if task_id not in self._breakers:
            self._breakers[task_id] = CircuitBreaker(max_attempts=self.max_attempts)
        return self._breakers[task_id]

    async def run(self, requirement: str) -> RunResult:
        # Persist the result across calls so artifacts survive HITL gate waits.
        if self._result is None:
            self._result = RunResult(requirement=requirement)
        result = self._result
        failed = False
        # topological waves
        while not self.dag.is_complete():
            ready = self.dag.ready()
            if not ready:
                break
            progressed = False
            for task_id in sorted(ready):
                task = next(t for t in self.dag.tasks() if t.id == task_id)
                # Required (mandatory) gate for this task?
                req_gate = self.required_gates.get(task_id)
                if req_gate is not None:
                    gate = self.gates.get(req_gate)
                    if gate is None or gate.decide().value == "block":
                        if self.bus:
                            self.bus.publish({"type": "gate.blocked", "task": task_id, "gate": req_gate})
                        continue
                # Direct HITL gate on the task itself?
                gate = self.gates.get(task_id)
                if gate is not None and gate.decide().value == "block":
                    if self.bus:
                        self.bus.publish({"type": "gate.blocked", "task": task_id, "gate": gate.name})
                    continue
                # Circuit breaker: stop retrying a persistently failing task.
                breaker = self._breaker(task_id)
                if breaker.tripped:
                    self.dag.mark_failed(task_id)
                    failed = True
                    progressed = True
                    if self.bus:
                        self.bus.publish({"type": "breaker.tripped", "task": task_id})
                    continue
                breaker.attempt()
                progressed = True
                self.dag.mark_running(task_id)
                agent = self.agents.get(task.agent)
                if agent is None:
                    self.dag.mark_failed(task_id)
                    failed = True
                    continue
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
                    breaker.record_success()
                except Exception:
                    # leave it not-done so the breaker can retry next wave
                    self.dag.mark_pending(task_id)
                    if self.bus:
                        self.bus.publish({"type": "task.error", "task": task_id})
            if not progressed:
                break
        result.success = (not failed) and self.dag.is_complete()
        # automated evaluation: score the run and embed it in metrics
        try:
            result.metrics["eval"] = EvalHarness().score(result).__dict__
        except Exception:
            pass
        if self.bus:
            self.bus.publish(
                {"type": "run.done", "success": result.success, "run_id": result.run_id}
            )
        return result
