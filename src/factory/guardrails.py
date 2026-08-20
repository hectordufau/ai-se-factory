"""Guardrails, circuit breaker, and HITL gates.

These enforce the safety properties the IgniteTech role demands:
- RoleScope: each role may only invoke allow-listed MCP servers/tools.
- CircuitBreaker: prevents an agent from repeating the same failure forever.
- Gate: HITL approval points (architecture, pre-release) with policy.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable


class GateDecision(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"


class GuardrailViolation(Exception):
    """Raised when an agent attempts a disallowed action."""


# Per-role MCP server access. A role only sees the servers it needs, so a
# backend agent can't open a GitHub PR, and a reviewer can't write code.
ROLE_SCOPE: dict[str, set[str]] = {
    "planner": {"docs"},
    "architect": {"docs", "filesystem", "database"},
    "backend": {"filesystem", "testing", "database", "docs"},
    "frontend": {"filesystem", "testing", "docs"},
    "database": {"database", "filesystem", "docs"},
    "qa": {"testing", "filesystem", "docs"},
    "security": {"filesystem", "docs"},
    "reviewer": {"github", "filesystem", "docs"},
}


@dataclass
class RoleScope:
    role: str
    allowed_servers: set[str] = field(default_factory=set)

    @classmethod
    def for_role(cls, role: str) -> "RoleScope":
        return cls(role=role, allowed_servers=ROLE_SCOPE.get(role, set()))

    def check(self, server: str, tool: str | None = None) -> bool:
        return server in self.allowed_servers

    def enforce(self, server: str, tool: str | None = None) -> None:
        if not self.check(server, tool):
            raise GuardrailViolation(
                f"Role {self.role!r} is not allowed to use MCP server {server!r}"
            )


@dataclass
class CircuitBreaker:
    """Bounds repeated failures per agent/work item.

    `attempt()` returns True while under the limit; once tripped it returns
    False. `record_success()` resets so intermittent success clears the fault.
    """

    max_attempts: int = 3
    attempts: int = 0

    @property
    def tripped(self) -> bool:
        return self.attempts >= self.max_attempts

    def attempt(self) -> bool:
        if self.tripped:
            return False
        self.attempts += 1
        return not self.tripped

    def record_success(self) -> None:
        self.attempts = 0

    def reset(self) -> None:
        self.attempts = 0


@dataclass
class Gate:
    """A HITL approval gate.

    `mandatory` gates must be approved before the linked task runs; optional
    gates only block the final release. `approvers` limits who may approve.
    """

    name: str
    mandatory: bool = True
    approvers: Iterable[str] = ("human", "orchestrator")
    approved: bool = False
    approved_by: str | None = None

    def approve(self, by: str = "human") -> None:
        if by not in self.approvers:
            raise GuardrailViolation(f"{by!r} is not an allowed approver for gate {self.name!r}")
        self.approved = True
        self.approved_by = by

    def decide(self) -> GateDecision:
        return GateDecision.ALLOW if self.approved else GateDecision.BLOCK
