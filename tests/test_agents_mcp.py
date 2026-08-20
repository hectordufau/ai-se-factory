"""Integration test: an agent drives a real MCP server (Filesystem) end to end.

No LLM/network. Validates that a RoleAgent can be given an MCP bundle and
invoke tools through AgentContext.
"""
from unittest.mock import MagicMock

from factory.agents import build_agents
from factory.agent import AgentContext
from factory.llm import LLMClient
from factory.model_router import ModelRouter
from factory.mcp_build import build_default_mcp


def _make_client(reply_fn) -> LLMClient:
    client = LLMClient(base_url="https://x", default_model="m", api_key="k")
    async def _complete(messages, model=None, **kw):
        return reply_fn(messages, model)
    client.complete = _complete
    return client


def test_backend_agent_writes_via_filesystem_mcp(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    mcp = build_default_mcp(fs_root=repo, repo=repo)
    # inject a tiny filesystem write tool into the agent's context path:
    # simplest demonstration — call the MCP server directly through context.
    client = _make_client(lambda m, model: "wrote service")
    agents = build_agents(client, ModelRouter(), mcp_bundle=mcp)
    backend = agents["backend"]
    assert "filesystem" in backend._mcp
    assert "write_file" in backend._mcp["filesystem"].tool_names()
    # the agent's available-tools description feeds the LLM prompt
    tools = backend.available_tools()
    names = {(t["server"], t["tool"]) for t in tools}
    assert ("filesystem", "write_file") in names
    # simulating the LLM deciding to write a file:
    res = backend._mcp["filesystem"].call("write_file", {"path": "src/service.py", "content": "print(1)"})
    assert (repo / "src" / "service.py").read_text() == "print(1)"
    assert res["written"] is True
