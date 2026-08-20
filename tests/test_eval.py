"""Tests for the EvalHarness (scores runs, detects regression, reports)."""
from factory.evals.eval import EvalHarness, Score
from factory.models import Artifact, ArtifactKind, RunResult


def _run(success=True, tests_passed=5, tests_failed=0, security_findings=0, tokens=100, cost=0.01):
    r = RunResult(requirement="build api", success=success)
    r.artifacts.append(
        Artifact(
            kind=ArtifactKind.REPORT,
            path="qa/tool_run_tests.json",
            content="",
            agent="qa",
            meta={"tool": "run_tests", "passed": tests_passed, "failed": tests_failed},
        )
    )
    r.artifacts.append(
        Artifact(
            kind=ArtifactKind.REPORT,
            path="security/tool_scan.json",
            content="",
            agent="security",
            meta={"tool": "scan", "findings": security_findings},
        )
    )
    r.metrics = {"tokens": tokens, "cost_usd": cost}
    return r


def test_score_computes_components():
    r = _run(success=True, tests_passed=5, tests_failed=0, security_findings=0)
    score = EvalHarness().score(r)
    assert score.success is True
    assert score.tests_passed == 5
    assert score.tests_failed == 0
    assert score.security_findings == 0
    assert score.test_pass_rate == 1.0
    assert score.overall > 0.9


def test_score_penalizes_failures_and_findings():
    r = _run(success=False, tests_passed=2, tests_failed=3, security_findings=4)
    score = EvalHarness().score(r)
    assert score.success is False
    assert score.test_pass_rate == 2 / 5
    assert score.security_findings == 4
    assert score.overall < 0.5


def test_compare_detects_regression():
    good = _run(success=True, tests_passed=10, tests_failed=0)
    bad = _run(success=True, tests_passed=6, tests_failed=2)
    cmp = EvalHarness().compare([good, bad])
    assert cmp["regression"] is True
    assert cmp["delta_overall"] < 0


def test_report_markdown_and_json():
    r = _run(success=True, tests_passed=5, tests_failed=0)
    h = EvalHarness()
    score = h.score(r)
    md = h.report(score, fmt="md")
    js = h.report(score, fmt="json")
    assert "Eval Report" in md
    assert "overall" in js
    assert isinstance(js, str) and "overall" in js
