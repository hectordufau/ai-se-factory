"""Testing MCP server — runs the project test suite in a worktree/repo.

The QA agent uses this to gate merges on green tests + no regressions. Output
is parsed into a structured result (passed/failed/summary) so the
eval harness can score it.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from factory.mcp_base import MCPServer, Tool


class TestingMCP(MCPServer):
    def __init__(self, repo: Path, pytest_bin: str = "pytest") -> None:
        super().__init__("testing")
        self.repo = Path(repo)
        self.pytest_bin = pytest_bin
        self.register(Tool("run_tests", "Run pytest in the repo.", self._run, ["path"]))

    def _run(self, args: dict) -> dict:
        target = args.get("path", "")
        cmd = [self.pytest_bin, "-q", "--no-header", target] if target else [self.pytest_bin, "-q", "--no-header"]
        proc = subprocess.run(cmd, cwd=str(self.repo), capture_output=True, text=True, timeout=300)
        summary = proc.stdout + proc.stderr
        # naive parse: lines like "1 passed, 1 failed"
        passed = self._count(summary, r"(\d+) passed")
        failed = self._count(summary, r"(\d+) failed")
        return {
            "exit_code": proc.returncode,
            "passed": passed,
            "failed": failed,
            "summary": summary[-2000:],
        }

    @staticmethod
    def _count(text: str, pattern: str) -> int:
        m = re.search(pattern, text)
        return int(m.group(1)) if m else 0
