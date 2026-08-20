"""Tests for refined guardrails: role scope, circuit breaker, gate policy."""
import pytest

from factory.guardrails import (
    CircuitBreaker,
    Gate,
    GateDecision,
    GuardrailViolation,
    RoleScope,
)


def test_role_scope_allows_and_denies():
    backend = RoleScope.for_role("backend")
    assert backend.check("filesystem")
    assert not backend.check("github")
    backend.enforce("filesystem")
    with pytest.raises(GuardrailViolation):
        backend.enforce("github")


def test_reviewer_can_open_github_pr():
    reviewer = RoleScope.for_role("reviewer")
    assert reviewer.check("github")
    reviewer.enforce("github", "open_pr")


def test_circuit_breaker_trips_and_resets():
    cb = CircuitBreaker(max_attempts=2)
    assert cb.attempt() is True
    assert cb.attempt() is False  # now tripped
    assert cb.tripped is True
    assert cb.attempt() is False
    cb.record_success()
    assert cb.tripped is False
    assert cb.attempt() is True


def test_gate_mandatory_blocks_until_approved():
    gate = Gate(name="arch", mandatory=True)
    assert gate.decide() == GateDecision.BLOCK
    gate.approve(by="human")
    assert gate.decide() == GateDecision.ALLOW


def test_gate_rejects_unauthorized_approver():
    gate = Gate(name="release", approvers=("human",))
    with pytest.raises(GuardrailViolation):
        gate.approve(by="agent-x")
