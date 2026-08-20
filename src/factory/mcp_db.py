"""Database MCP server — read-only query execution (SQLite by default).

The DB agent / architect use this to inspect schema and validate data access
patterns. Writes are out of scope for the agent (safety): only SELECT/PRAGMA.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

from factory.mcp_base import MCPServer, Tool, ToolError


class DatabaseMCP(MCPServer):
    def __init__(self, db_path: Path, read_only: bool = True) -> None:
        super().__init__("database")
        self.db_path = Path(db_path)
        self.register(Tool("query", "Run a read-only SQL query.", self._query, ["sql"]))
        self._read_only = read_only

    def _query(self, args: dict) -> dict:
        sql = args["sql"].strip().lower()
        if self._read_only and not (sql.startswith("select") or sql.startswith("pragma") or sql.startswith("with")):
            raise ToolError("DatabaseMCP is read-only; only SELECT/PRAGMA/WITH allowed")
        try:
            cx = sqlite3.connect(str(self.db_path))
            cur = cx.execute(args["sql"])
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description] if cur.description else []
            cx.close()
            return {"columns": cols, "rows": [list(r) for r in rows]}
        except Exception as e:
            raise ToolError(f"query failed: {e}") from e
