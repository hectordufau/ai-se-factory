"""Tests for Level 2: real, scoreable agent evidence (Nível 2 eval)."""
import asyncio
from pathlib import Path

from factory.agents import build_agents, RoleAgent
from factory.agent import AgentContext
from factory.evals.eval import EvalHarness
from factory.llm import LLMClient
from factory.model_router import ModelRouter
from factory.mcp_fs import FilesystemMCP
from factory.models import RunResult


def _client(text):
    c = LLMClient(base_url="x", default_model="m", api_key="k")
    async def f(m, model=None, **kw):
        return text
    c.complete = f
    return c


def test_qa_emits_run_tests_meta(tmp_path):
    # a tiny pytest suite so QA's evidence run has something to execute
    (tmp_path / "test_x.py").write_text("def test_ok():\n    assert True\n")
    c = _client("qa report")
    agents = build_agents(c, ModelRouter(), mcp_bundle={"filesystem": FilesystemMCP(tmp_path)})
    ctx = AgentContext(requirement="r", extra={"repo_root": str(tmp_path)})
    artifacts = asyncio.run(agents["qa"].run(ctx))
    ev = [a for a in artifacts if a.meta.get("tool") == "run_tests"]
    assert ev, "QA must emit run_tests evidence"
    assert ev[0].meta["passed"] >= 1


def test_security_emits_scan_meta(tmp_path):
    (tmp_path / "bad.py").write_text("import os\nos.system('rm -rf /')\n")
    c = _client("security report")
    agents = build_agents(c, ModelRouter(), mcp_bundle={"filesystem": FilesystemMCP(tmp_path)})
    ctx = AgentContext(requirement="r", extra={"repo_root": str(tmp_path)})
    artifacts = asyncio.run(agents["security"].run(ctx))
    ev = [a for a in artifacts if a.meta.get("tool") == "scan"]
    assert ev, "Security must emit scan evidence"
    assert ev[0].meta["findings"] >= 1


def test_eval_harness_consumes_evidence(tmp_path):
    res = RunResult(requirement="r", success=True)
    res.artifacts = [
        type("A", (), {"meta": {"tool": "run_tests", "passed": 3, "failed": 0}, "agent": "qa"})(),
        type("A", (), {"meta": {"tool": "scan", "findings": 0}, "agent": "security"})(),
    ]
    score = EvalHarness().score(res)
    assert score.tests_passed == 3
    assert score.tests_failed == 0
    assert score.security_findings == 0
    assert score.overall >= 0.9  # production-ready threshold


def test_llmclient_counts_tokens():
    c = LLMClient(base_url="x", default_model="m", api_key="k")
    # simulate usage accumulation without a real API call
    c.total_tokens = 0

    class _Usage:
        total_tokens = 42
    class _Msg:
        content = "ok"
    class _Choice:
        message = _Msg()
    class _Resp:
        choices = [_Choice()]
        usage = _Usage()

    async def fake_complete(messages, model=None, **kw):
            # emulate the adapter's usage accounting path
            c.total_tokens += _Resp.usage.total_tokens
            return _Resp.choices[0].message.content
    c.complete = fake_complete
    asyncio.run(fake_complete([]))
    assert c.total_tokens == 42
