"""Tests for GitHubMCP using a fake Github client (no network)."""
import pytest

from factory.mcp_github import GitHubMCP
from factory.mcp_base import ToolError


class _FakeRepo:
    def __init__(self):
        self.commits = []
        self.prs = []
        self.files = {"README.md": "hello"}

    def get_contents(self, path):
        if path in self.files:
            return type("C", (), {"decoded_content": self.files[path].encode()})()
        raise Exception("404")

    def create_pull(self, title, body, head, base):
        self.prs.append({"title": title, "head": head, "base": base})
        return type("PR", (), {"number": len(self.prs), "html_url": f"https://github.com/x/y/pull/{len(self.prs)}"})()


class _FakeGithub:
    def __init__(self, token=""):
        self._repos = {}

    def get_repo(self, full_name):
        if full_name not in self._repos:
            self._repos[full_name] = _FakeRepo()
        return self._repos[full_name]


def test_read_file_and_open_pr():
    gh = GitHubMCP(repo="hectordufau/demo", github=_FakeGithub())
    out = gh.call("read_file", {"path": "README.md"})
    assert out["content"] == "hello"
    pr = gh.call("open_pr", {"title": "feat", "body": "b", "head": "feat/x", "base": "main"})
    assert pr["number"] == 1
    assert pr["html_url"].endswith("/pull/1")


def test_missing_token_raises_if_no_client(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    # no github client passed and no token -> refuse (don't crash)
    with pytest.raises(ToolError):
        GitHubMCP(repo="hectordufau/demo")
