"""Evidence exporter — turn a RunResult into auditable artifacts.

The IgniteTech role demands "how do you know an agent is improving?". This
module makes every run auditable: it writes a human-readable EVIDENCE.md (per
agent: what it produced, status, eval signals) and a machine-readable
run_result.json (the full structured RunResult).
"""
from __future__ import annotations

import json
from pathlib import Path

from factory.evals.eval import EvalHarness
from factory.models import RunResult, ArtifactKind


def _evidence_rows(result: RunResult) -> list[str]:
    rows = []
    # group artifacts by producing agent
    by_agent: dict[str, list] = {}
    for a in result.artifacts:
        by_agent.setdefault(a.agent or "(unattributed)", []).append(a)

    for agent, arts in by_agent.items():
        rows.append(f"### Agent: `{agent}`")
        kinds = {}
        for a in arts:
            kinds.setdefault(a.kind.value, 0)
            kinds[a.kind.value] += 1
        rows.append(f"- artifacts: {len(arts)} ({', '.join(f'{k}={v}' for k, v in kinds.items())})")
        # evidence signals
        for a in arts:
            t = a.meta.get("tool")
            if t == "run_tests":
                rows.append(f"  - QA tests: **{a.meta.get('passed', 0)} passed / "
                            f"{a.meta.get('failed', 0)} failed**")
            elif t == "scan":
                rows.append(f"  - Security scan: **{a.meta.get('findings', 0)} findings**")
            elif t == "filesystem.write":
                status = "written" if not a.meta.get("error") else f"FAILED ({a.meta.get('error')})"
                rows.append(f"  - wrote `{a.path}` — {status}")
        # show a short content preview for code/spec artifacts
        for a in arts:
            if a.kind in (ArtifactKind.CODE, ArtifactKind.SPEC) and a.content:
                preview = a.content.strip().splitlines()[:3]
                if preview:
                    rows.append(f"  - preview: `{preview[0][:100]}`")
        rows.append("")
    return rows


def build_evidence_md(result: RunResult) -> str:
    score = EvalHarness().score(result)
    lines = [
        "# Factory Run Evidence",
        "",
        f"- **Run ID:** `{result.run_id}`",
        f"- **Requirement:** {result.requirement}",
        f"- **Success:** {result.success}",
        f"- **Overall score:** {score.overall}",
        f"- **Tokens:** {result.metrics.get('tokens', 0)}",
        f"- **Tests:** {score.tests_passed} passed / {score.tests_failed} failed",
        f"- **Security findings:** {score.security_findings}",
        "",
        "## Per-agent evidence",
        "",
    ]
    lines += _evidence_rows(result)
    lines += ["## Eval report", "", EvalHarness().report(score)]
    if result.events:
        lines += ["", "## Event log", ""]
        for ev in result.events:
            lines.append(f"- `{ev.get('type')}` {json.dumps(ev, ensure_ascii=False)}")
    return "\n".join(lines)


def export(result: RunResult, evidence_dir: str | Path) -> dict[str, str]:
    """Write EVIDENCE.md and run_result.json. Returns the written paths."""
    evidence_dir = Path(evidence_dir)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    md_path = evidence_dir / "EVIDENCE.md"
    json_path = evidence_dir / "run_result.json"
    md_path.write_text(build_evidence_md(result), encoding="utf-8")
    json_path.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return {"evidence_md": str(md_path), "run_result_json": str(json_path)}
