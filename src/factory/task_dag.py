"""Topological task scheduler for the factory DAG.

Each task declares its dependencies; `ready()` returns tasks whose deps are
all DONE (parallel-eligible). Detects cycles before scheduling.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from factory.models import Task, TaskStatus


class CycleError(Exception):
    """Raised when the DAG contains a dependency cycle."""


@dataclass
class TaskDag:
    _tasks: dict[str, Task] = field(default_factory=dict)

    def add(self, id: str, deps: Optional[list[str]] = None, agent: str = "", description: str = "") -> Task:
        if id in self._tasks:
            raise KeyError(f"task {id!r} already exists")
        task = Task(id=id, agent=agent, description=description, deps=list(deps or []))
        self._tasks[id] = task
        return task

    def _check_cycles(self) -> None:
        """DFS cycle detection over the dependency graph."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {tid: WHITE for tid in self._tasks}

        def visit(nid: str) -> None:
            color[nid] = GRAY
            for dep in self._tasks[nid].deps:
                if dep not in self._tasks:
                    continue  # missing dep treated as external/already-satisfied
                if color[dep] == GRAY:
                    raise CycleError(f"dependency cycle detected at {nid!r} -> {dep!r}")
                if color[dep] == WHITE:
                    visit(dep)
            color[nid] = BLACK

        for tid in self._tasks:
            if color[tid] == WHITE:
                visit(tid)

    def ready(self) -> set[str]:
        """Return ids of tasks whose dependencies are all DONE and that are not
        themselves DONE/RUNNING. Raises CycleError if a cycle exists."""
        self._check_cycles()
        out: set[str] = set()
        for tid, task in self._tasks.items():
            if task.status in (TaskStatus.DONE, TaskStatus.RUNNING, TaskStatus.FAILED):
                continue
            if all(
                (dep not in self._tasks) or self._tasks[dep].status == TaskStatus.DONE
                for dep in task.deps
            ):
                out.add(tid)
        return out

    def mark_done(self, id: str) -> None:
        if id not in self._tasks:
            raise KeyError(id)
        self._tasks[id].status = TaskStatus.DONE

    def mark_running(self, id: str) -> None:
        if id not in self._tasks:
            raise KeyError(id)
        self._tasks[id].status = TaskStatus.RUNNING

    def mark_failed(self, id: str) -> None:
        if id not in self._tasks:
            raise KeyError(id)
        self._tasks[id].status = TaskStatus.FAILED

    def mark_pending(self, id: str) -> None:
        if id not in self._tasks:
            raise KeyError(id)
        self._tasks[id].status = TaskStatus.PENDING

    def status(self, id: str) -> TaskStatus:
        if id not in self._tasks:
            raise KeyError(id)
        return self._tasks[id].status

    def is_complete(self) -> bool:
        return all(t.status == TaskStatus.DONE for t in self._tasks.values())

    def tasks(self) -> list[Task]:
        return list(self._tasks.values())
