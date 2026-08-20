"""Filesystem MCP server — scoped to a single worktree root.

Agents use this to read/write only within their isolated worktree, enforcing
the "scoped context" guarantee from the architecture doc.
"""
from __future__ import annotations

from pathlib import Path, PurePosixPath

from factory.mcp_base import MCPServer, Tool, ToolError


class FilesystemMCP(MCPServer):
    def __init__(self, root: Path) -> None:
        super().__init__("filesystem")
        self.root = Path(root).resolve()
        self.register(Tool("read_file", "Read a file under the root.", self._read, ["path"]))
        self.register(Tool("write_file", "Write a file under the root.", self._write, ["path", "content"]))
        self.register(Tool("list_files", "List files matching a glob.", self._list, ["pattern"]))

    def _safe(self, path: str) -> Path:
        # Resolve and ensure it stays inside self.root.
        target = (self.root / PurePosixPath(path)).resolve()
        if self.root not in target.parents and target != self.root:
            raise ToolError(f"Path {path!r} escapes the allowed root {self.root}")
        return target

    def _read(self, args: dict) -> dict:
        p = self._safe(args["path"])
        if not p.exists():
            return {"exists": False, "content": ""}
        return {"exists": True, "content": p.read_text(encoding="utf-8", errors="replace")}

    def _write(self, args: dict) -> dict:
        p = self._safe(args["path"])
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(args["content"], encoding="utf-8")
        return {"written": True, "path": str(p.relative_to(self.root))}

    def _list(self, args: dict) -> dict:
        pattern = args.get("pattern", "**/*")
        files = [str(p.relative_to(self.root)) for p in self.root.glob(pattern) if p.is_file()]
        return {"files": [{"path": f} for f in sorted(files)]}
