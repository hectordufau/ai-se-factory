"""GitHub MCP server — talks to GitHub via the official client (PyGithub).

Token resolution: `GITHUB_TOKEN` env (your PAT `hectordufau`) -> injected
client. Never hard-codes secrets. In tests, a fake Github client is injected.
Tools: read_file (read repo file), open_pr (create a pull request).
"""
from __future__ import annotations

import os
from typing import Any, Optional

from factory.mcp_base import MCPServer, Tool, ToolError


class GitHubMCP(MCPServer):
    def __init__(self, repo: str, github: Any = None) -> None:
        super().__init__("github")
        self.repo = repo
        if github is None:
            token = os.environ.get("GITHUB_TOKEN")
            if not token:
                raise ToolError("GitHubMCP requires GITHUB_TOKEN env or an injected client")
            try:
                from github import Github
            except ImportError as e:
                raise ToolError("PyGithub not installed") from e
            github = Github(token)
        self._gh = github
        self.register(Tool("read_file", "Read a file from the repo.", self._read, ["path"]))
        self.register(Tool("open_pr", "Open a pull request.", self._open_pr, ["title", "body", "head", "base", "files"]))

    def _repo(self):
        return self._gh.get_repo(self.repo)

    def _read(self, args: dict) -> dict:
        try:
            content = self._repo().get_contents(args["path"])
            return {"content": content.decoded_content.decode("utf-8", "replace")}
        except Exception as e:
            raise ToolError(f"read_file failed: {e}") from e

    def _open_pr(self, args: dict) -> dict:
        repo = self._repo()
        head = args["head"]
        base = args["base"]
        # ensure the head branch exists (create from base if missing)
        try:
            repo.get_branch(head)
        except Exception:
            base_sha = repo.get_branch(base).commit.sha
            repo.create_git_ref(f"refs/heads/{head}", base_sha)
        # optionally create/update files on the new branch
        for path, content in (args.get("files") or {}).items():
            try:
                existing = repo.get_contents(path, ref=head)
                repo.update_file(
                    path, f"Add {path}", content, existing.sha, branch=head
                )
            except Exception:
                repo.create_file(path, f"Add {path}", content, branch=head)
        pr = repo.create_pull(
            title=args["title"],
            body=args.get("body", ""),
            head=head,
            base=base,
        )
        return {"number": pr.number, "html_url": pr.html_url}
