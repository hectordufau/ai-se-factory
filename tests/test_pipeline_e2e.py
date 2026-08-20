"""End-to-end integration: full 8-agent pipeline via build_pipeline, mocked LLM.

No network. Proves the CLI assembly + orchestrator + gates + eval work
together on the real DAG.
"""
from pathlib import Path
from unittest.mock import patch, MagicMock

from factory.cli import build_pipeline


async def test_full_pipeline_run_with_gates(tmp_path):
    captured = {}

    async def fake_complete(messages, model=None, **kw):
        return "artifact"

    fake_client = MagicMock()
    fake_client.complete = fake_complete

    with patch("factory.cli.build_client", return_value=fake_client):
        orch = build_pipeline("build api", repo_root=tmp_path)
        # first run: architect gate blocks implementation
        r1 = await orch.run("build api")
        # nothing past architect should be done yet
        assert orch.dag.status("backend") != "done"
        assert r1.success is False
        # human approves architecture + release
        orch.gates["architect"].approve(by="human")
        orch.gates["release"].approve(by="human")
        r2 = await orch.run("build api")
        assert r2.success is True
        assert orch.dag.is_complete()
        # eval embedded
        assert "eval" in r2.metrics
        assert r2.metrics["eval"]["tests_passed"] == 0  # no real tests ran
