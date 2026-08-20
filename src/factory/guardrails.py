"""Guardrails, circuit breaker, and HITL gates.

These enforce the safety properties the IgniteTech role demands:
- scope_check: agents only perform allow-listed actions on allow-listed paths.
- CircuitBreaker: prevents an agent from repeating the same failure forever.
- Gate: HITL approval points (architecture, pre-release).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable


class GateDecision(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"


@dataclass
class Guardrails:
    allowed_actions: set[str] = field(default_factory=lambda: {"read", "write", "test"})
    denied_prefixes: tuple[str, ...] = ("/prod/", "/secrets/")

    def scope_check(self, action: str, path: str = "") -> bool:
        if action not in self.allowed_actions:
            return False
        for denied in self.denied_prefixes:
            if path.startswith(denied):
                return False
        return True


@dataclass
class CircuitBreaker:
    max_attempts: int = 3
    attempts: int = 0

    @property
    def tripped(self) -> bool:
        return self.attempts >= self.max_attempts

    def attempt(self) -> bool:
        """Return True if another attempt is allowed; else trip and return False."""
        if self.tripped:
            return False
        self.attempts += 1
        return not self.tripped

    def reset(self) -> None:
        self.attempts = 0


@dataclass
class Gate:
    name: str
    auto_approve: bool = False
    approved: bool = False
    approved_by: str | None = None

    def approve(self, by: str = "human") -> None:
        self.approved = True
        self.approved_by = by

    def decide(self) -> GateDecision:
        if self.auto_approve or self.approved:
            return GateDecision.ALLOW
        return GateDecision.BLOCK
