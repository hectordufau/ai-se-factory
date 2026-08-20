"""Core data models for the factory (tasks, artifacts, runs)."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
from uuid import uuid4


class TaskStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class ArtifactKind(str, Enum):
    SPEC = "spec"
    CODE = "code"
    TEST = "test"
    REPORT = "report"
    DECISION = "decision"


@dataclass
class Artifact:
    """A file or document produced by an agent."""

    kind: ArtifactKind
    path: str
    content: str = ""
    agent: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "path": self.path,
            "content": self.content,
            "agent": self.agent,
            "meta": self.meta,
        }


@dataclass
class Task:
    """A node in the work DAG."""

    id: str
    agent: str
    description: str
    deps: list[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "agent": self.agent,
            "description": self.description,
            "deps": self.deps,
            "status": self.status.value,
            "result": self.result,
        }


@dataclass
class RunResult:
    """Outcome of a full factory run."""

    run_id: str = field(default_factory=lambda: uuid4().hex)
    requirement: str = ""
    tasks: list[Task] = field(default_factory=list)
    artifacts: list[Artifact] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    success: bool = False
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "requirement": self.requirement,
            "tasks": [t.to_dict() for t in self.tasks],
            "artifacts": [a.to_dict() for a in self.artifacts],
            "events": self.events,
            "success": self.success,
            "metrics": self.metrics,
        }
