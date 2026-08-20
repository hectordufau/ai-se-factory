"""Tests for TestingMCP (runs pytest in a repo and parses results)."""
import subprocess
from pathlib import Path

import pytest

from factory.mcp_test import TestingMCP


def _init_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "test_x.py").write_text(
        "def test_pass():\n    assert True\n"
        "def test_fail():\n    assert False\n"
    )
    return tmp_path


def test_run_tests_reports_pass_and_fail(tmp_path):
    repo = _init_repo(tmp_path)
    t = TestingMCP(repo=repo)
    out = t.call("run_tests", {})
    assert out["exit_code"] != 0  # one test fails
    assert out["passed"] == 1
    assert out["failed"] == 1
    assert "test_fail" in out["summary"]


def test_run_single_test_file(tmp_path):
    repo = _init_repo(tmp_path)
    t = TestingMCP(repo=repo)
    out = t.call("run_tests", {"path": "test_x.py::test_pass"})
    assert out["passed"] == 1
    assert out["failed"] == 0
