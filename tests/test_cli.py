"""Tests for the factory CLI pipeline assembly (no network)."""
from pathlib import Path
from unittest.mock import patch, MagicMock

from factory.cli import build_dag, build_pipeline


def test_build_dag_has_8_agents_and_release_dep():
    dag = build_dag()
    ids = {t.id for t in dag.tasks()}
    assert ids == {
        "planner", "architect", "backend", "frontend",
        "database", "qa", "security", "reviewer", "release",
    }
    # release depends on reviewer
    release = next(t for t in dag.tasks() if t.id == "release")
    assert "reviewer" in release.deps


def test_build_pipeline_wires_gates_and_required_gates():
    fake_client = MagicMock()
    with patch("factory.cli.build_client", return_value=fake_client):
        orch = build_pipeline("build api", provider="nous", repo_root=Path("/tmp"))
    # architect + release gates present
    assert "architect" in orch.gates and "release" in orch.gates
    # backend/frontend/database require architect approval before running
    assert orch.required_gates["backend"] == "architect"
    assert orch.required_gates["frontend"] == "architect"
