"""Tests for FilesystemMCP (scoped read/write under a root)."""
import pytest

from factory.mcp_fs import FilesystemMCP
from factory.mcp_base import ToolError


def test_read_and_write_scoped(tmp_path):
    fs = FilesystemMCP(root=tmp_path)
    fs.call("write_file", {"path": "a/b.py", "content": "x=1"})
    out = fs.call("read_file", {"path": "a/b.py"})
    assert out["content"] == "x=1"
    # glob lists it
    names = [t["path"] for t in fs.call("list_files", {"pattern": "**/*.py"})["files"]]
    assert "a/b.py" in names


def test_write_outside_root_rejected(tmp_path):
    fs = FilesystemMCP(root=tmp_path)
    with pytest.raises(ToolError):
        fs.call("write_file", {"path": "../escape.py", "content": "x"})


def test_read_missing_reports_absent(tmp_path):
    fs = FilesystemMCP(root=tmp_path)
    out = fs.call("read_file", {"path": "nope.py"})
    assert out["exists"] is False
