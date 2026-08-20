"""Tests for guardrails + HITL gate primitives."""
import pytest

from factory.guardrails import Guardrails, CircuitBreaker, Gate, GateDecision


def test_scope_check_blocks_disallowed_action():
    g = Guardrails(allowed_actions={"read", "write"}, denied_prefixes=("/prod/",))
    assert g.scope_check("read", path="/tmp/x") is True
    assert g.scope_check("delete", path="/tmp/x") is False
    assert g.scope_check("write", path="/prod/secret") is False


def test_circuit_breaker_trips():
    cb = CircuitBreaker(max_attempts=3)
    assert cb.attempt() is True
    assert cb.attempt() is True
    assert cb.attempt() is False  # tripped
    assert cb.tripped is True


def test_gate_blocks_until_approved():
    gate = Gate(name="release")
    assert gate.decide() == GateDecision.BLOCK
    gate.approve(by="human")
    assert gate.decide() == GateDecision.ALLOW


def test_gate_auto_approve_when_configured():
    gate = Gate(name="routing", auto_approve=True)
    assert gate.decide() == GateDecision.ALLOW
