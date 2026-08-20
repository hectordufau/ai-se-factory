"""Aggregate the default MCP server bundle for a run.

Each agent receives the subset it needs via `build_default_mcp(...)`; the
Orchestrator scopes filesystem/testing to the agent's worktree so agents
cannot read siblings' code.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from factory.mcp_base import MCPServer
from factory.mcp_db import DatabaseMCP
from factory.mcp_docs import DocsMCP
from factory.mcp_fs import FilesystemMCP
from factory.mcp_github import GitHubMCP
from factory.mcp_test import TestingMCP


def build_default_mcp(
    fs_root: Path,
    repo: Optional[Path] = None,
    github_repo: Optional[str] = None,
    db_path: Optional[Path] = None,
    docs_root: Optional[Path] = None,
    github=None,
) -> dict[str, MCPServer]:
    """Return the standard MCP server bundle keyed by name."""
    bundle = {
        "filesystem": FilesystemMCP(root=fs_root),
        "testing": TestingMCP(repo=repo or fs_root),
        "docs": DocsMCP(root=docs_root or fs_root),
    }
    if db_path is not None:
        bundle["database"] = DatabaseMCP(db_path=db_path)
    if github_repo is not None:
        try:
            bundle["github"] = GitHubMCP(repo=github_repo, github=github)
        except Exception:
            # github optional (needs token); skip if unavailable
            pass
    return bundle
