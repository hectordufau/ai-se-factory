"""Eval harness — measures whether an agentic run actually improved.

The IgniteTech role explicitly demands "automated evaluation" and "how do you
know an agent is improving?". This harness scores a `RunResult` on the
dimensions that matter for production software: did it finish, did tests pass,
were there security findings, what was the token/cost cost. It also compares
two runs to detect regressions.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Score:
    run_id: str
    success: bool
    tests_passed: int = 0
    tests_failed: int = 0
    test_pass_rate: float = 0.0
    security_findings: int = 0
    tokens: int = 0
    cost_usd: float = 0.0
    overall: float = 0.0
    notes: list[str] = field(default_factory=list)


class EvalHarness:
    def score(self, run: Any) -> Score:
        # Extract test results from QA agent tool artifacts.
        tests_passed = 0
        tests_failed = 0
        for a in run.artifacts:
            if a.meta.get("tool") == "run_tests":
                tests_passed += int(a.meta.get("passed", 0) or 0)
                tests_failed += int(a.meta.get("failed", 0) or 0)
        total = tests_passed + tests_failed
        pass_rate = (tests_passed / total) if total else (1.0 if run.success else 0.0)

        # Security findings from security agent tool artifacts.
        security_findings = 0
        for a in run.artifacts:
            if a.meta.get("tool") == "scan":
                security_findings += int(a.meta.get("findings", 0) or 0)

        tokens = int(run.metrics.get("tokens", 0) or 0)
        cost = float(run.metrics.get("cost_usd", 0.0) or 0.0)

        notes: list[str] = []
        overall = 0.0
        if run.success:
            overall = 0.65
        else:
            notes.append("run did not complete successfully")
        # test pass rate contributes up to 0.3
        overall += 0.3 * pass_rate
        # security findings penalize up to -0.3
        sec_penalty = min(0.3, 0.03 * security_findings)
        overall -= sec_penalty
        if security_findings:
            notes.append(f"{security_findings} security finding(s)")
        overall = max(0.0, min(1.0, overall))
        if overall >= 0.9 and not security_findings and tests_failed == 0:
            notes.append("production-ready")

        return Score(
            run_id=getattr(run, "run_id", ""),
            success=bool(run.success),
            tests_passed=tests_passed,
            tests_failed=tests_failed,
            test_pass_rate=round(pass_rate, 3),
            security_findings=security_findings,
            tokens=tokens,
            cost_usd=cost,
            overall=round(overall, 3),
            notes=notes,
        )

    def compare(self, runs: list[Any]) -> dict[str, Any]:
        scores = [self.score(r) for r in runs]
        if len(scores) < 2:
            return {"regression": False, "delta_overall": 0.0, "scores": [s.__dict__ for s in scores]}
        delta = scores[-1].overall - scores[0].overall
        return {
            "regression": delta < 0,
            "delta_overall": round(delta, 3),
            "scores": [s.__dict__ for s in scores],
        }

    def report(self, score: Score, fmt: str = "md") -> str:
        if fmt == "json":
            return json.dumps(score.__dict__, indent=2)
        lines = [
            "# Eval Report",
            f"- Run: `{score.run_id}`",
            f"- Success: {score.success}",
            f"- Tests: {score.tests_passed} passed / {score.tests_failed} failed (rate {score.test_pass_rate})",
            f"- Security findings: {score.security_findings}",
            f"- Tokens: {score.tokens} | Cost: ${score.cost_usd:.4f}",
            f"- **Overall: {score.overall}**",
        ]
        if score.notes:
            lines.append("- Notes: " + "; ".join(score.notes))
        return "\n".join(lines)
