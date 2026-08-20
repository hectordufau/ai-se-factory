"""Append-only JSONL event bus — the audit trail for agent communication.

Agents never call each other directly; they publish events here and the
Orchestrator reads them back in order. This is the "file-based agent
communication" described in the architecture.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any


class EventBus:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()
        # create file if missing
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.touch()

    def publish(self, event: dict[str, Any]) -> None:
        """Append a single event as one JSON line."""
        with self._lock:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def read_all(self) -> list[dict[str, Any]]:
        """Return all events in insertion order."""
        if not self.path.exists():
            return []
        out: list[dict[str, Any]] = []
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
        return out
