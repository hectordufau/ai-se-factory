"""Git worktree manager — isolated branches per agent task.

Each agent-task runs in its own worktree so parallel agents can't clobber each
other's files. The Orchestrator merges only after QA + Review gates pass.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Worktree:
    name: str
    path: Path
    branch: str


class WorktreeManager:
    def __init__(self, repo: Path) -> None:
        self.repo = Path(repo)

    def _run(self, args: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args],
            cwd=self.repo,
            capture_output=True,
            text=True,
            check=True,
        )

    def current_branch(self) -> str:
        out = self._run(["branch", "--show-current"])
        return out.stdout.strip() or "HEAD"

    def create(self, name: str, base: str | None = None) -> Worktree:
        base = base or self.current_branch()
        branch = f"agent/{name}"
        worktree_path = self.repo.parent / f"{self.repo.name}.wt-{name}"
        self._run(["worktree", "add", "-b", branch, str(worktree_path), base])
        return Worktree(name=name, path=worktree_path, branch=branch)

    def remove(self, wt: Worktree) -> None:
        self._run(["worktree", "remove", str(wt.path), "--force"])
        # best-effort branch cleanup
        try:
            self._run(["branch", "-D", wt.branch])
        except subprocess.CalledProcessError:
            pass

    def merge(self, wt: Worktree, target: str | None = None) -> None:
        """Merge the worktree's branch into `target` (default current branch)."""
        target = target or self.current_branch()
        self._run(["merge", "--no-ff", "-m", f"merge {wt.branch}", wt.branch])
