"""Tests for RoleAgent file-writing via scoped FilesystemMCP (Nível B)."""
import asyncio
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from factory.agents import build_agents, RoleAgent
from factory.llm import LLMClient
from factory.model_router import ModelRouter
from factory.mcp_fs import FilesystemMCP
from factory.mcp_base import ToolError
from factory.agent import AgentContext


def _make_client(text):
    c = LLMClient(base_url="x", default_model="m", api_key="k")
    async def f(m, model=None, **kw):
        return text
    c.complete = f
    return c


def test_parse_files_extracts_path_and_content():
    text = (
        "Here is the fix.\n\n<<<FILES>>>\n"
        "PATH: config/versions.py\n```\nFABRIC_VERSION = '2.5.14'\n```\n<<<END>>>\n"
    )
    dummy = RoleAgent.__new__(RoleAgent)
    files = dummy._parse_files(text)
    assert files == [("config/versions.py", "FABRIC_VERSION = '2.5.14'")]


def test_role_agent_writes_files_via_mcp(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    fs = FilesystemMCP(root)
    text = "fix\n\n<<<FILES>>>\nPATH: a.txt\n```\nhello\n```\n<<<END>>>\n"
    c = _make_client(text)
    agents = build_agents(c, ModelRouter(), mcp_bundle={"filesystem": fs})
    backend = agents["backend"]
    artifacts = asyncio.run(backend.run(AgentContext(requirement="test")))
    written = [a for a in artifacts if a.meta.get("tool") == "filesystem.write"]
    assert written, "expected a written file artifact"
    assert (root / "a.txt").read_text() == "hello"


def test_role_agent_scope_blocks_unauthorized_mcp(tmp_path):
    fs = FilesystemMCP(tmp_path)
    agents = build_agents(_make_client("x"), ModelRouter(), mcp_bundle={"filesystem": fs})
    # reviewer role cannot write via filesystem per ROLE_SCOPE
    with pytest.raises(ToolError):
        agents["reviewer"].call_mcp("filesystem", "write", {"path": "x", "content": "y"})
