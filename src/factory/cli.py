"""Factory CLI — assemble the full pipeline and run a requirement end to end.

Usage:
    python -m factory run --requirement "Build a payments API"
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from factory.agents import build_agents
from factory.llm import build_client
from factory.model_router import ModelRouter
from factory.orchestrator import Orchestrator
from factory.task_dag import TaskDag


# Standard 8-agent DAG: planner -> architect -> impl -> qa -> security -> reviewer -> release
def build_dag() -> TaskDag:
    dag = TaskDag()
    dag.add("planner", deps=[], agent="planner")
    dag.add("architect", deps=["planner"], agent="architect")
    dag.add("backend", deps=["architect"], agent="backend")
    dag.add("frontend", deps=["architect"], agent="frontend")
    dag.add("database", deps=["architect"], agent="database")
    dag.add("qa", deps=["backend", "frontend", "database"], agent="qa")
    dag.add("security", deps=["backend", "frontend", "database"], agent="security")
    dag.add("reviewer", deps=["qa", "security"], agent="reviewer")
    dag.add("release", deps=["reviewer"], agent="reviewer")
    return dag


def build_pipeline(
    requirement: str,
    provider: str = "nous",
    repo_root: Optional[Path] = None,
    github_repo: Optional[str] = None,
) -> Orchestrator:
    """Assemble agents + MCP + orchestrator for a run.

    Returns an Orchestrator whose `run(requirement)` drives the DAG. The
    planner/architect/release gates are wired as HITL + required gates so a
    human must approve the architecture and the final release.
    """
    repo_root = repo_root or Path.cwd()
    from factory.guardrails import Gate
    from factory.mcp_build import build_default_mcp

    client = build_client(provider)
    router = ModelRouter()  # default model = provider default (hy3:free / big-pickle)
    mcp = build_default_mcp(fs_root=repo_root, repo=repo_root, github_repo=github_repo)
    agents = build_agents(client, router, mcp_bundle=mcp)
    gates = {
        "architect": Gate(name="architect", mandatory=True),   # approve design first
        "release": Gate(name="release", mandatory=True),        # approve before ship
    }
    required_gates = {"backend": "architect", "frontend": "architect", "database": "architect"}
    dag = build_dag()
    return Orchestrator(dag, agents, gates=gates, required_gates=required_gates)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="factory", description="AI Software Engineering Factory")
    sub = parser.add_subparsers(dest="cmd")
    run_p = sub.add_parser("run", help="Run the factory on a requirement")
    run_p.add_argument("--requirement", required=True, help="Natural-language requirement")
    run_p.add_argument("--provider", default="nous", choices=["nous", "zen"])
    run_p.add_argument("--repo", default=None, help="Repo root for MCP (default: cwd)")
    run_p.add_argument("--github-repo", default=None, help="owner/name for GitHub MCP")
    args = parser.parse_args(argv)
    if args.cmd != "run":
        parser.print_help()
        return 1
    orch = build_pipeline(
        args.requirement,
        provider=args.provider,
        repo_root=Path(args.repo) if args.repo else None,
        github_repo=args.github_repo,
    )
    import asyncio

    result = asyncio.run(orch.run(args.requirement))
    from factory.evals.eval import EvalHarness

    print(EvalHarness().report(EvalHarness().score(result)))
    return 0 if result.success else 2


if __name__ == "__main__":
    raise SystemExit(main())
