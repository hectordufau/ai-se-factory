"""Tests for WorktreeManager — real git worktree operations in a temp repo."""
import subprocess
from pathlib import Path

import pytest

from factory.worktree import WorktreeManager


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=path, check=True)
    (path / "README.md").write_text("# test\n")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=path, check=True)


def test_create_and_remove(tmp_path: Path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    wm = WorktreeManager(repo)
    wt = wm.create("feat-a")
    try:
        assert wt.path.exists()
        assert (wt.path / "README.md").exists()
        # worktree listed by git
        out = subprocess.run(["git", "worktree", "list"], cwd=repo, capture_output=True, text=True, check=True)
        assert str(wt.path) in out.stdout
    finally:
        wm.remove(wt)
    out = subprocess.run(["git", "worktree", "list"], cwd=repo, capture_output=True, text=True, check=True)
    assert str(wt.path) not in out.stdout


def test_create_writes_file_and_merge(tmp_path: Path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    wm = WorktreeManager(repo)
    wt = wm.create("feat-b")
    try:
        (wt.path / "feature.txt").write_text("hello")
        subprocess.run(["git", "add", "."], cwd=wt.path, check=True)
        subprocess.run(["git", "commit", "-qm", "add feature"], cwd=wt.path, check=True)
        wm.merge(wt, target="main" if _has_main(repo) else "master")
        # file should now exist on base branch
        base = "main" if _has_main(repo) else "master"
        content = subprocess.run(
            ["git", "show", f"{base}:feature.txt"], cwd=repo, capture_output=True, text=True
        )
        assert content.stdout == "hello"
    finally:
        wm.remove(wt)


def _has_main(repo: Path) -> bool:
    out = subprocess.run(["git", "branch", "--show-current"], cwd=repo, capture_output=True, text=True)
    return out.stdout.strip() == "main"
