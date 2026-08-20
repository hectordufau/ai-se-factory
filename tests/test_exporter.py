"""Tests for the evidence exporter (Nível 1)."""
import json

from factory.exporter import build_evidence_md, export
from factory.models import RunResult, Artifact, ArtifactKind


def _result():
    r = RunResult(requirement="build a thing", success=True)
    r.artifacts = [
        Artifact(kind=ArtifactKind.CODE, path="backend/output.md",
                 content="# Plan\nDo X", agent="backend",
                 meta={"tool": "filesystem.write"}),
        Artifact(kind=ArtifactKind.REPORT, path="qa/test_results.json",
                 content="1 passed", agent="qa",
                 meta={"tool": "run_tests", "passed": 1, "failed": 0}),
        Artifact(kind=ArtifactKind.REPORT, path="security/scan.json",
                 content="os.system", agent="security",
                 meta={"tool": "scan", "findings": 2}),
    ]
    r.events = [{"type": "agent.done", "agent": "backend"}]
    r.metrics = {"tokens": 123}
    return r


def test_build_evidence_md_contains_signals(tmp_path):
    md = build_evidence_md(_result())
    assert "Factory Run Evidence" in md
    assert "backend" in md
    assert "1 passed / 0 failed" in md
    assert "2 findings" in md
    assert "123" in md  # tokens


def test_export_writes_files(tmp_path):
    paths = export(_result(), tmp_path)
    assert (tmp_path / "EVIDENCE.md").exists()
    assert (tmp_path / "run_result.json").exists()
    data = json.loads((tmp_path / "run_result.json").read_text())
    assert data["success"] is True
    assert len(data["artifacts"]) == 3
