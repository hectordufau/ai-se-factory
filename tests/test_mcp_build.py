"""Tests for DatabaseMCP, DocsMCP, and build_default_mcp aggregation."""
import pytest

from factory.mcp_db import DatabaseMCP
from factory.mcp_docs import DocsMCP
from factory.mcp_build import build_default_mcp


def test_db_mcp_query_runs_sql(tmp_path):
    import sqlite3

    db = tmp_path / "app.db"
    cx = sqlite3.connect(db)
    cx.execute("CREATE TABLE t(id INTEGER)")
    cx.execute("INSERT INTO t VALUES (1),(2)")
    cx.commit()
    cx.close()
    d = DatabaseMCP(db_path=db)
    out = d.call("query", {"sql": "SELECT count(*) FROM t"})
    assert out["rows"] == [[2]]


def test_docs_mcp_returns_snippet(tmp_path):
    (tmp_path / "adp.md").write_text("# ADR\nWe use Postgres.\n")
    docs = DocsMCP(root=tmp_path)
    out = docs.call("search", {"query": "Postgres"})
    assert "Postgres" in out["snippets"][0]["text"]


def test_build_default_mcp_contains_all_servers(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_dummy")
    fs_root = tmp_path / "repo"
    fs_root.mkdir()
    db = tmp_path / "app.db"
    db.write_text("")
    bundle = build_default_mcp(fs_root=fs_root, repo=tmp_path, db_path=db, github_repo="hectordufau/demo")
    assert set(bundle) == {"filesystem", "testing", "github", "database", "docs"}
