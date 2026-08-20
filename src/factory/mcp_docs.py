"""Docs MCP server — lightweight documentation search over a local corpus.

The architect/reviewer use this to ground decisions in existing ADRs and
runbooks. A trivial substring index; a real deployment could swap in an
embeddings store without changing the tool interface.
"""
from __future__ import annotations

from pathlib import Path

from factory.mcp_base import MCPServer, Tool


class DocsMCP(MCPServer):
    def __init__(self, root: Path, globs=("**/*.md", "**/*.txt", "**/*.rst")) -> None:
        super().__init__("docs")
        self.root = Path(root)
        self.globs = globs
        self.register(Tool("search", "Search the docs corpus.", self._search, ["query"]))

    def _search(self, args: dict) -> dict:
        q = args["query"].lower()
        snippets = []
        for pattern in self.globs:
            for p in self.root.glob(pattern):
                try:
                    text = p.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                if q in text.lower():
                    idx = text.lower().find(q)
                    start = max(0, idx - 80)
                    snippets.append({"path": str(p.relative_to(self.root)), "text": text[start : start + 200]})
        return {"snippets": snippets[:10]}
