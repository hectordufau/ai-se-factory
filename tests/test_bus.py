"""Tests for the event bus (append-only JSONL) and state store."""
import json
from pathlib import Path

from factory.bus import EventBus


def test_append_and_read_in_order(tmp_path: Path):
    bus = EventBus(path=tmp_path / "events.jsonl")
    bus.publish({"type": "a", "n": 1})
    bus.publish({"type": "b", "n": 2})
    bus.publish({"type": "c", "n": 3})
    events = bus.read_all()
    assert [e["type"] for e in events] == ["a", "b", "c"]
    assert events[0]["n"] == 1 and events[2]["n"] == 3


def test_read_empty(tmp_path: Path):
    bus = EventBus(path=tmp_path / "events.jsonl")
    assert bus.read_all() == []


def test_persistence_across_instances(tmp_path: Path):
    p = tmp_path / "events.jsonl"
    bus1 = EventBus(path=p)
    bus1.publish({"type": "x"})
    bus2 = EventBus(path=p)
    assert bus2.read_all()[0]["type"] == "x"
